"""
Deterministic rule engine.

This component compares parsed claim facts against visual observations. It does
not inspect files or call models, which keeps every decision path explainable.
"""

from typing import Any


class RuleEngine:
    """Applies the challenge's strict claim verification rules."""

    def __init__(self, low_confidence_threshold: float = 0.50, review_threshold: float = 0.80):
        self.low_confidence_threshold = low_confidence_threshold
        self.review_threshold = review_threshold

    def evaluate(
        self,
        parser_result: dict[str, str],
        vision_result: dict[str, Any],
        evidence_result: dict[str, Any],
    ) -> dict[str, Any]:
        claimed_damage_type = parser_result.get("claimed_damage_type", "unknown")
        claimed_object_part = parser_result.get("claimed_object_part", "unknown")
        visible_damage_type = self._normalize(vision_result.get("damage_type"), "unknown")
        visible_object_part = self._normalize(vision_result.get("object_part"), "unknown")
        damage_visible = self._to_bool(vision_result.get("damage_visible", False))
        confidence = self._to_float(vision_result.get("confidence", 0.0))

        risk_flags = []

        # Decision path 1: insufficient evidence prevents any conclusion.
        if not evidence_result.get("evidence_standard_met", False):
            status = "not_enough_information"
            mismatch_type = "evidence_insufficient"
            risk_flags.append("evidence_insufficient")
            justification = evidence_result.get(
                "evidence_standard_met_reason",
                "Evidence standard was not met.",
            )

        # Decision path 2: no visible damage contradicts the claim.
        elif not damage_visible:
            status = "contradicted"
            mismatch_type = "damage_not_visible"
            risk_flags.append("damage_not_visible")
            justification = "No visible damage was detected in the submitted images."

        # Decision path 3: a different visible damage type contradicts the claim.
        elif self._damage_conflict(claimed_damage_type, visible_damage_type):
            status = "contradicted"
            mismatch_type = "claim_mismatch"
            risk_flags.append("claim_mismatch")
            justification = (
                f"Claimed damage is {claimed_damage_type}, but visible damage is "
                f"{visible_damage_type}."
            )

        # Decision path 4: damage on a different claimed part contradicts the claim.
        elif self._parts_conflict(claimed_object_part, visible_object_part):
            status = "contradicted"
            mismatch_type = "object_part_mismatch"
            risk_flags.append("object_part_mismatch")
            justification = (
                f"Claimed part is {claimed_object_part}, but visible damage is on "
                f"{visible_object_part}."
            )

        # Decision path 5: low confidence blocks automated support.
        elif confidence < self.low_confidence_threshold:
            status = "not_enough_information"
            mismatch_type = "low_confidence"
            risk_flags.append("low_confidence")
            justification = (
                f"Confidence {confidence:.2f} is below the "
                f"{self.low_confidence_threshold:.2f} threshold."
            )

        # Decision path 6: matching damage, matching part, sufficient evidence, and confidence.
        else:
            status = "supported"
            mismatch_type = "none"
            justification = (
                f"Claimed {claimed_damage_type} on {claimed_object_part}. "
                f"Visible {visible_damage_type} on {visible_object_part}. "
                f"Evidence standard satisfied with confidence {confidence:.2f}."
            )

        return {
            "claim_status": status,
            "justification": justification,
            "claimed_damage_type": claimed_damage_type,
            "claimed_object_part": claimed_object_part,
            "visible_damage_type": visible_damage_type,
            "visible_object_part": visible_object_part,
            "confidence": confidence,
            "review_candidate": self.low_confidence_threshold <= confidence < self.review_threshold,
            "mismatch_type": mismatch_type,
            "risk_flags": risk_flags,
        }

    COMPATIBLE_DAMAGE_TYPES = {
        ("glass_shatter", "crack"),
        ("crack", "glass_shatter"),
        ("stain", "water_damage"),
        ("water_damage", "stain"),
    }

    def _damage_conflict(self, claimed_damage_type: str, visible_damage_type: str) -> bool:
        if claimed_damage_type in ("", None):
            return False
        if claimed_damage_type == "unknown":
            return visible_damage_type not in ("", None, "unknown")
        if claimed_damage_type == visible_damage_type:
            return False
        if (claimed_damage_type, visible_damage_type) in self.COMPATIBLE_DAMAGE_TYPES:
            return False
        return True

    def _parts_conflict(self, claimed_object_part: str, visible_object_part: str) -> bool:
        if claimed_object_part in ("", None, "unknown"):
            return False
        if visible_object_part in ("", None, "unknown"):
            return True
        return claimed_object_part != visible_object_part

    def _normalize(self, value: Any, default: str) -> str:
        if value is None:
            return default
        value = str(value).strip().lower()
        return value or default

    def _to_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "visible")
        if isinstance(value, (int, float)):
            return value > 0
        return False

    def _to_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
