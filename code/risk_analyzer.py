"""
Risk flag and severity analysis.
"""

from pathlib import Path
from typing import Any

from config import Config
from utils import normalize_text


class RiskAnalyzer:

    def __init__(self, config: Config):
        self.config = config
        self._blur_detector = None
        self._crop_detector = None
        self._text_detector = None
        self._object_validator = None

    def _lazy_init_cv(self):
        if self._blur_detector is not None:
            return
        from cv.blur_detector import BlurDetector
        from cv.crop_detector import CropDetector
        from cv.object_validator import ObjectValidator
        from cv.text_detector import TextDetector
        self._blur_detector = BlurDetector()
        self._crop_detector = CropDetector()
        self._text_detector = TextDetector()
        self._object_validator = ObjectValidator()

    def analyze(
        self,
        image_analysis: dict[str, Any],
        user_history: dict[str, Any] | None,
        claim_object: str,
        user_claim: str,
        evidence_result: dict[str, Any] | None = None,
        rule_result: dict[str, Any] | None = None,
        image_paths: list[Path] | None = None,
    ) -> list[str]:
        risk_flags: set[str] = set()
        evidence_result = evidence_result or {}
        rule_result = rule_result or {}

        image_assessments = image_analysis.get("image_assessments", [])
        for assessment in image_assessments:
            if not assessment.get("is_clear", True):
                risk_flags.add("blurry_image")
            if assessment.get("is_cropped", False):
                risk_flags.add("cropped_or_obstructed")
            if not assessment.get("lighting_adequate", True):
                risk_flags.add("low_light_or_glare")
            if not assessment.get("angle_sufficient", True):
                risk_flags.add("wrong_angle")

        confidence = self._to_float(rule_result.get("confidence", image_analysis.get("confidence", 0.0)))
        if confidence < 0.50:
            risk_flags.add("manual_review_required")

        mismatch_type = rule_result.get("mismatch_type")
        if mismatch_type == "object_part_mismatch":
            risk_flags.add("wrong_object_part")
        elif mismatch_type == "claim_mismatch":
            risk_flags.add("claim_mismatch")
        elif mismatch_type == "damage_not_visible":
            risk_flags.add("damage_not_visible")
        elif mismatch_type == "evidence_insufficient":
            if "wrong_angle" not in risk_flags:
                risk_flags.add("manual_review_required")

        for flag in rule_result.get("risk_flags", []):
            risk_flags.add(flag)

        if image_analysis.get("conflicting_images", False):
            risk_flags.add("claim_mismatch")
            risk_flags.add("manual_review_required")

        notes = image_analysis.get("notes", "").lower()

        if image_analysis.get("damage_type", image_analysis.get("overall_issue_type")) in ("none", "unknown"):
            if self._user_claimed_damage(user_claim) and "wrong object" not in notes:
                risk_flags.add("damage_not_visible")
        if any(word in notes for word in ["photoshopped", "edited", "manipulated", "altered"]):
            risk_flags.add("possible_manipulation")
        if any(word in notes for word in ["screenshot", "stock photo", "stock image", "template", "non-original"]):
            risk_flags.add("non_original_image")
        if "wrong object" in notes:
            risk_flags.add("wrong_object")

        if user_history:
            history_flags = user_history.get("history_flags", "")
            if "user_history_risk" in (history_flags or ""):
                risk_flags.add("user_history_risk")
            if "manual_review_required" in (history_flags or ""):
                risk_flags.add("manual_review_required")

            last_90_days = int(user_history.get("last_90_days_claim_count", 0))
            if last_90_days > 3:
                risk_flags.add("user_history_risk")

            rejected = int(user_history.get("rejected_claim", 0))
            if rejected > 2:
                risk_flags.add("user_history_risk")

        if confidence < 0.5:
            risk_flags.add("manual_review_required")

        if "text" in notes or "label" in notes:
            risk_flags.add("text_instruction_present")

        # --- Deterministic CV module overrides ---
        if image_paths:
            self._lazy_init_cv()
            image_paths_list = [Path(p) if isinstance(p, str) else p for p in image_paths]

            # Blur detection overrides Gemini is_clear
            blur_results = self._blur_detector.has_blurry_images(image_paths_list)
            any_blurry = any(r["is_blurry"] for r in blur_results)
            if any_blurry:
                risk_flags.add("blurry_image")
            # Do NOT remove vision-based flags — CV only adds signals

            # Crop detection
            crop_results = self._crop_detector.has_cropped_images(image_paths_list)
            any_cropped = any(r["is_cropped"] for r in crop_results)
            if any_cropped:
                risk_flags.add("cropped_or_obstructed")

            # OCR text detection
            text_results = self._text_detector.has_text_images(image_paths_list)
            any_text = any(r["contains_text"] for r in text_results)
            if any_text:
                risk_flags.add("text_instruction_present")

            # Wrong object detection
            obj_results = self._object_validator.find_wrong_objects(image_paths_list, claim_object)
            any_wrong = any(r["wrong_object"] for r in obj_results)
            if any_wrong:
                risk_flags.add("wrong_object")
                risk_flags.add("manual_review_required")

        if "claim_mismatch" in risk_flags and "user_history_risk" in risk_flags:
            risk_flags.add("manual_review_required")
        if "user_history_risk" in risk_flags:
            risk_flags.add("manual_review_required")

        internal_flags = {"evidence_insufficient", "low_confidence", "object_part_mismatch"}
        risk_flags = {f for f in risk_flags if f not in internal_flags}

        if not risk_flags:
            return ["none"]

        return sorted(risk_flags)

    def _user_claimed_damage(self, user_claim: str) -> bool:
        if not user_claim:
            return False
        text = normalize_text(user_claim)
        damage_keywords = [
            "dent", "scratch", "crack", "shatter", "broken", "missing",
            "torn", "crushed", "water damage", "stain", "damage", "issue",
            "defect", "problem", "not working", "faulty"
        ]
        return any(kw in text for kw in damage_keywords)

    def _to_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
