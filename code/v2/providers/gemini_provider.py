from code.config import Config
from code.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from code.v2.models.observation import Observation, ObservationReport, PerImageAssessment
from code.v2.providers.base import VisionProvider

MAX_IMAGES = 5


def _to_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "yes", "1"):
            return True
        if lowered in ("false", "no", "0"):
            return False
    return default


def build_prompt(claim_text: str, claim_object: str, image_count: int) -> str:
    """Same task prompt and JSON schema the V1 vision analyzer sends."""
    parts = sorted(Config.ALLOWED_OBJECT_PARTS.get(claim_object, {"unknown"}))
    prompt = USER_PROMPT_TEMPLATE.format(
        claim_object=claim_object,
        user_claim=claim_text[:500],
        image_count=image_count,
        object_parts=", ".join(parts),
    )
    return f"{SYSTEM_PROMPT}\n\n{prompt}"


class GeminiProvider(VisionProvider):
    """Gemini vision provider. Reuses V1's prompt and JSON schema."""

    PROVIDER_NAME = "gemini"

    def __init__(self, model_name: str = "gemini-2.0-flash", config: dict | None = None):
        super().__init__(model_name, config)

    def _api_key(self) -> str | None:
        import os
        return self.config.get("api_key") or os.environ.get("GEMINI_API_KEY")

    def _check_availability(self) -> bool:
        return bool(self._api_key())

    def analyze(self, image_paths: list[str], claim_text: str, claim_object: str) -> ObservationReport:
        try:
            import json
            import re
            import time

            from google import genai
            from PIL import Image

            api_key = self._api_key()
            if not api_key:
                return ObservationReport(all_failed=True)
            client = genai.Client(api_key=api_key)
            start = time.time()

            # Keep only images that actually load, so the i-th assessment in the
            # reply lines up with the i-th image sent.
            sent_paths: list[str] = []
            images = []
            for p in image_paths[:MAX_IMAGES]:
                try:
                    with Image.open(p) as img:
                        images.append(img.copy())
                    sent_paths.append(p)
                except Exception:
                    pass

            contents = [build_prompt(claim_text, claim_object, len(sent_paths)), *images]
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config={"temperature": 0.0, "response_mime_type": "application/json"},
            )

            assessments = []
            text = (getattr(response, "text", None) or "").strip()
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                per_image = data.get("per_image_assessments") or data.get("image_assessments") or []
                for i, img_path in enumerate(sent_paths):
                    img_data = per_image[i] if i < len(per_image) and isinstance(per_image[i], dict) else {}
                    if not img_data:
                        continue
                    assessments.append(PerImageAssessment(
                        image_path=img_path,
                        damage_visible=_to_bool(img_data.get("damage_visible"), False),
                        damage_type=img_data.get("damage_type", "unknown"),
                        object_part=img_data.get("object_part", "unknown"),
                        confidence=float(img_data.get("confidence", 0.0)),
                        is_clear=_to_bool(img_data.get("is_clear"), False),
                        angle_sufficient=_to_bool(img_data.get("angle_sufficient"), False),
                        lighting_adequate=_to_bool(img_data.get("lighting_adequate"), False),
                    ))

            elapsed = (time.time() - start) * 1000
            obs = Observation(
                model_name=self.model_name,
                provider=self.PROVIDER_NAME,
                success=bool(assessments),
                assessments=assessments,
                latency_ms=elapsed,
            )
            return ObservationReport(observations=[obs], all_failed=not assessments, primary_model=self.model_name)

        except Exception as e:
            obs = Observation(
                model_name=self.model_name,
                provider=self.PROVIDER_NAME,
                success=False,
                error=str(e)[:200],
                degraded=True,
            )
            return ObservationReport(observations=[obs], all_failed=True)
