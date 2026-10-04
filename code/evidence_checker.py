"""
Semantic evidence checker.

Evidence requirements are natural-language review standards. This checker maps
those descriptions to deterministic image-quality and part-visibility checks.
"""

from pathlib import Path
from typing import Any

from utils import safe_csv_read


class EvidenceChecker:
    """Validates whether the submitted observations satisfy semantic requirements."""

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.requirements: list[dict[str, str]] = []
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        self.requirements = []
        for row in safe_csv_read(self.csv_path):
            self.requirements.append({
                "requirement_id": row.get("requirement_id", "").strip(),
                "claim_object": row.get("claim_object", "").strip().lower(),
                "applies_to": row.get("applies_to", "").strip().lower(),
                "text": row.get("minimum_image_evidence", "").strip(),
            })
        self._loaded = True

    def evaluate(
        self,
        claim_object: str,
        parser_result: dict[str, str],
        vision_result: dict[str, Any],
        total_images: int,
    ) -> dict[str, Any]:
        self.load()
        requirement = self._select_requirement(
            claim_object,
            parser_result.get("claimed_damage_type", "unknown"),
            parser_result.get("claimed_object_part", "unknown"),
        )

        if total_images == 0:
            return self._result(False, "No images were submitted.", requirement, False)

        assessments = vision_result.get("per_image_assessments", [])
        claimed_part = parser_result.get("claimed_object_part", "unknown")
        vision_part = vision_result.get("object_part", "unknown")
        # Use the part most likely visible: prefer vision's detected part over parser's claimed part
        check_part = vision_part if vision_part not in ("", None, "unknown", "none") else claimed_part
        relevant = self._relevant_assessments(assessments, check_part)
        part_unclear = vision_part in ("", None, "unknown", "none") and claimed_part not in ("", None, "unknown")

        clear = any(self._quality_ok(a) for a in relevant)
        angle_ok = any(a.get("angle_sufficient", False) for a in relevant)
        unobstructed = any(not a.get("is_cropped", False) for a in relevant)

        notes = (vision_result.get("notes") or "").lower()
        is_non_original = "non-original" in notes

        missing = []
        if not clear:
            missing.append("image quality is insufficient")
        if not angle_ok:
            missing.append("angle is insufficient")
        if not unobstructed:
            missing.append("relevant view is cropped or obstructed")

        valid = clear and unobstructed and not is_non_original

        if missing:
            return self._result(False, f"Requirement not met: {'; '.join(missing)}.", requirement, valid)
        if part_unclear and not clear:
            return self._result(False, "Required image quality not met.", requirement, valid)

        return self._result(True, "Requirement met: image quality is sufficient for evaluation.", requirement, valid)

    def _select_requirement(self, claim_object: str, damage_type: str, object_part: str) -> dict[str, str]:
        claim_object = (claim_object or "").lower()
        damage_text = (damage_type or "").replace("_", " ")
        part_text = (object_part or "").replace("_", " ")
        candidates = [r for r in self.requirements if r["claim_object"] in (claim_object, "all")]

        for req in candidates:
            applies_to = req["applies_to"]
            if damage_text and damage_text != "unknown" and damage_text in applies_to:
                return req
            if part_text and part_text != "unknown" and part_text in applies_to:
                return req

        for req in candidates:
            if req["applies_to"] == "reviewability":
                return req

        return {
            "requirement_id": "DEFAULT_REVIEWABILITY",
            "claim_object": claim_object or "all",
            "applies_to": "reviewability",
            "text": "Images should clearly show the claimed object and relevant part.",
        }

    def _relevant_assessments(self, assessments: list[dict[str, Any]], claimed_part: str) -> list[dict[str, Any]]:
        if not assessments:
            return []
        if not claimed_part or claimed_part == "unknown":
            return assessments
        relevant = []
        for assessment in assessments:
            parts = [str(part).lower() for part in assessment.get("affected_parts", [])]
            if claimed_part in parts:
                relevant.append(assessment)
        return relevant or assessments

    def _part_visible(
        self,
        claimed_part: str,
        vision_result: dict[str, Any],
        relevant: list[dict[str, Any]],
    ) -> bool:
        if not claimed_part or claimed_part == "unknown":
            return bool(relevant)
        if vision_result.get("object_part") == claimed_part:
            return True
        for assessment in relevant:
            parts = [str(part).lower() for part in assessment.get("affected_parts", [])]
            if claimed_part in parts:
                return True
        return False

    def _quality_ok(self, assessment: dict[str, Any]) -> bool:
        return assessment.get("is_clear", False) and assessment.get("image_quality", "unknown") in ("good", "adequate")

    def _result(self, met: bool, reason: str, requirement: dict[str, str], valid_image: bool) -> dict[str, Any]:
        requirement_text = requirement.get("text", "")
        full_reason = f"{reason} Requirement considered: {requirement_text}".strip()
        return {
            "evidence_standard_met": met,
            "reason": full_reason,
            "evidence_standard_met_reason": full_reason,
            "requirement_text": requirement_text,
            "valid_image": valid_image,
        }
