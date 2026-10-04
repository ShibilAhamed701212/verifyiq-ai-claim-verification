"""
Vision observation extractor using Google Gemini.

The vision model extracts facts only. Deterministic downstream modules make
claim-status, risk, and severity decisions.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from config import Config
from google import genai
from google.genai import types
from utils import get_image_id_from_path

logger = logging.getLogger("evidence_review.vision")


class GeminiVisionClient:

    def __init__(self, config: Config):
        self.config = config
        self.client = None
        self.model = config.vision_model
        self.cache_dir = None
        api_key = config.api_key or os.environ.get("GEMINI_API_KEY")
        if api_key:
            try:
                self.client = genai.Client(api_key=api_key)
            except Exception as e:
                logger.warning(f"Gemini client init failed: {e}")

    def _init_cache(self) -> None:
        if self.cache_dir is not None:
            return
        self.cache_dir = Path(self.config.base_dir).parent / ".gemini_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Gemini cache enabled at {self.cache_dir}")

    def _cache_key(self, image_paths: list[Path], user_claim: str, claim_object: str) -> str:
        import hashlib
        parts = [str(p.resolve()) for p in sorted(image_paths, key=lambda x: str(x))]
        parts.append(user_claim[:200])
        parts.append(claim_object)
        parts.append(self.model)
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _cache_load(self, key: str) -> dict[str, Any]:
        if self.cache_dir is None:
            return None
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.info(f"Cache HIT for {key}")
            return data
        except Exception as e:
            logger.warning(f"Cache read failed for {key}: {e}")
        return None

    def _cache_save(self, key: str, analysis: dict[str, Any]) -> None:
        if self.cache_dir is None:
            return
        path = self.cache_dir / f"{key}.json"
        try:
            path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Cache write failed for {key}: {e}")

    def analyze_images(
        self,
        image_paths: list[Path],
        user_claim: str,
        claim_object: str,
        object_parts: list[str],
    ) -> dict[str, Any]:
        if self.client is None:
            return self._empty_analysis("Gemini client not available (no API key).")
        if not image_paths:
            return self._empty_analysis("No images provided.")

        self._init_cache()
        cache_key = self._cache_key(image_paths, user_claim, claim_object)
        cached = self._cache_load(cache_key)
        if cached is not None:
            return cached

        from prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

        prompt = USER_PROMPT_TEMPLATE.format(
            claim_object=claim_object,
            user_claim=user_claim[:500],
            image_count=len(image_paths),
            object_parts=", ".join(object_parts),
        )
        parts = [types.Part.from_text(text=f"{SYSTEM_PROMPT}\n\n{prompt}")]

        for img_path in image_paths[:self.config.max_images_per_claim]:
            if not img_path.exists():
                logger.warning(f"Image not found: {img_path}")
                continue
            try:
                parts.append(types.Part.from_bytes(data=img_path.read_bytes(), mime_type=self._get_mime(img_path)))
            except Exception as e:
                logger.error(f"Failed to read image {img_path}: {e}")

        for attempt in range(5):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=types.Content(role="user", parts=parts),
                    config=types.GenerateContentConfig(
                        temperature=self.config.temperature,
                        response_mime_type="application/json",
                    ),
                )
                time.sleep(2)
                result = self._parse_response(response, image_paths)
                self._cache_save(cache_key, result)
                return result
            except Exception as e:
                err_str = str(e)
                if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                    wait = 2 ** attempt * 5
                    logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt + 1}/5)")
                    time.sleep(wait)
                    continue
                logger.error(f"Gemini API call failed: {e}")
                return self._empty_analysis(f"API error: {str(e)[:100]}")

        return self._empty_analysis("API rate limit exceeded after retries")

    def _parse_response(self, response, image_paths: list[Path]) -> dict[str, Any]:
        text = response.text if hasattr(response, "text") and response.text else ""
        if not text:
            return self._empty_analysis("Empty response from Gemini")

        try:
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r"\{[\s\S]*\}", text)
                json_str = json_match.group(0) if json_match else text
            analysis = json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            return self._empty_analysis(f"JSON parsing error: {str(e)[:100]}")

        return self._normalize_analysis(analysis, image_paths)

    def _normalize_analysis(self, analysis: dict[str, Any], image_paths: list[Path]) -> dict[str, Any]:
        image_ids = [get_image_id_from_path(p) for p in image_paths]
        raw = analysis.get("per_image_assessments", analysis.get("image_assessments", []))
        raw = raw if isinstance(raw, list) else []

        assessments = []
        for idx, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            image_id = item.get("image_id") or (image_ids[idx] if idx < len(image_ids) else "")
            damage_type = self._enum(item.get("damage_type") or self._first(item.get("issues_visible")), "unknown")
            object_part = self._enum(item.get("object_part") or self._first(item.get("affected_parts")), "unknown")
            is_clear = self._to_bool(item.get("is_clear", True))
            is_cropped = self._to_bool(item.get("is_cropped", False))
            lighting = self._to_bool(item.get("lighting_adequate", True))
            angle = self._to_bool(item.get("angle_sufficient", True))
            damage_visible = self._to_bool(item.get("damage_visible", damage_type not in ("none", "unknown")))

            if image_id not in image_ids:
                continue

            assessments.append({
                "image_id": image_id,
                "damage_visible": damage_visible,
                "damage_type": damage_type,
                "object_part": object_part,
                "image_quality": self._quality_label(item.get("image_quality"), is_clear, is_cropped, lighting, angle),
                "is_clear": is_clear,
                "is_cropped": is_cropped,
                "lighting_adequate": lighting,
                "angle_sufficient": angle,
                "issues_visible": item.get("issues_visible", [damage_type] if damage_visible else ["none"]),
                "affected_parts": item.get("affected_parts", [object_part] if object_part != "unknown" else []),
                "damage_description": item.get("damage_description", ""),
                "confidence": self._to_float(item.get("confidence", analysis.get("confidence", 0.0))),
            })

        aggregate = self._aggregate(analysis, assessments, image_ids)
        aggregate["per_image_assessments"] = assessments

        # Backward-compatible aliases for existing helpers and reports.
        aggregate["image_assessments"] = assessments
        aggregate["overall_issue_type"] = aggregate["damage_type"]
        aggregate["overall_object_part"] = aggregate["object_part"]
        aggregate["supporting_image_ids"] = aggregate["supporting_images"]
        return aggregate

    def _aggregate(self, analysis: dict[str, Any], assessments: list[dict[str, Any]], image_ids: list[str]) -> dict[str, Any]:
        clear_damage = [
            a for a in assessments
            if a["damage_visible"] and a["is_clear"] and a["angle_sufficient"]
        ]
        any_damage = [a for a in assessments if a["damage_visible"]]
        evidence_pool = clear_damage or any_damage

        damage_visible = bool(evidence_pool)
        damage_type = self._majority(evidence_pool, "damage_type") if damage_visible else "none"
        object_part = self._majority(evidence_pool, "object_part") if damage_visible else self._enum(analysis.get("object_part"), "unknown")
        supporting = [
            a["image_id"] for a in evidence_pool
            if a["image_id"] in image_ids and a["damage_type"] == damage_type
        ]
        if not supporting and isinstance(analysis.get("supporting_images"), list):
            supporting = [img for img in analysis["supporting_images"] if img in image_ids]

        confidence_values = [a["confidence"] for a in evidence_pool if a["confidence"] > 0]
        confidence = sum(confidence_values) / len(confidence_values) if confidence_values else self._to_float(analysis.get("confidence"))

        return {
            "damage_visible": damage_visible,
            "damage_type": damage_type or "unknown",
            "object_part": object_part or "unknown",
            "image_quality": self._aggregate_quality(assessments),
            "supporting_images": supporting,
            "confidence": confidence,
            "notes": analysis.get("notes", ""),
            "conflicting_images": self._has_conflicts(assessments),
        }

    def _majority(self, assessments: list[dict[str, Any]], field: str) -> str:
        counts: dict[str, int] = {}
        for assessment in assessments:
            value = self._enum(assessment.get(field), "unknown")
            if value != "unknown":
                counts[value] = counts.get(value, 0) + 1
        if not counts:
            return "unknown"
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    def _aggregate_quality(self, assessments: list[dict[str, Any]]) -> str:
        if not assessments:
            return "unknown"
        strong = sum(1 for a in assessments if a["is_clear"] and a["angle_sufficient"] and a["lighting_adequate"])
        if strong >= max(1, len(assessments) // 2):
            return "good"
        if any(a["is_clear"] for a in assessments):
            return "adequate"
        return "poor"

    def _has_conflicts(self, assessments: list[dict[str, Any]]) -> bool:
        damage = {a["damage_type"] for a in assessments if a["damage_visible"] and a["damage_type"] != "unknown"}
        parts = {a["object_part"] for a in assessments if a["damage_visible"] and a["object_part"] != "unknown"}
        return len(damage) > 1 or len(parts) > 1

    def _quality_label(self, value: Any, is_clear: bool, is_cropped: bool, lighting: bool, angle: bool) -> str:
        if not is_clear or is_cropped or not lighting:
            return "poor"
        if not angle:
            return "adequate"
        value = self._enum(value, "good")
        return value if value in {"good", "adequate", "poor", "unknown"} else "good"

    def _first(self, values: Any) -> str:
        if isinstance(values, list) and values:
            return str(values[0])
        return "unknown"

    def _enum(self, value: Any, default: str) -> str:
        if value is None:
            return default
        value = str(value).strip().lower()
        return value or default

    def _to_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "y", "clear", "good", "1", "adequate", "sufficient")
        if isinstance(value, (int, float)):
            return value > 0
        return False

    def _to_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _empty_analysis(self, reason: str) -> dict[str, Any]:
        return {
            "damage_visible": False,
            "damage_type": "unknown",
            "object_part": "unknown",
            "image_quality": "unknown",
            "supporting_images": [],
            "confidence": 0.0,
            "notes": f"Analysis failed: {reason}",
            "conflicting_images": False,
            "per_image_assessments": [],
            "image_assessments": [],
            "overall_issue_type": "unknown",
            "overall_object_part": "unknown",
            "supporting_image_ids": [],
        }

    def _get_mime(self, path: Path) -> str:
        ext = path.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        return mime_map.get(ext, "image/jpeg")


def analyze_images(
    image_paths: list[Path],
    user_claim: str,
    claim_object: str,
    config: Config,
) -> dict[str, Any]:
    client = GeminiVisionClient(config)
    object_parts = list(config.ALLOWED_OBJECT_PARTS.get(claim_object, ["unknown"]))
    return client.analyze_images(image_paths, user_claim, claim_object, object_parts)
