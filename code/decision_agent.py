"""
Final decision agent.

This is the only component that produces the final output row returned to
`main.py` and ultimately written to `output.csv`.
"""

from typing import Any

from output_validator import OutputValidator
from severity_engine import SeverityEngine


class DecisionAgent:
    """Combines parser, vision, evidence, rule, risk, and severity outputs."""

    def __init__(self, validator: OutputValidator, severity_engine: SeverityEngine):
        self.validator = validator
        self.severity_engine = severity_engine

    def build_output_row(
        self,
        claim_row: dict[str, str],
        parser_result: dict[str, str],
        vision_result: dict[str, Any],
        evidence_result: dict[str, Any],
        rule_result: dict[str, Any],
        risk_result: list[str],
    ) -> dict[str, str]:
        risk_flags = risk_result
        risk_flags = self._merge_flags(risk_flags, rule_result, vision_result)

        status = rule_result.get("claim_status", "not_enough_information")
        severity = self.severity_engine.determine(
            vision_result.get("damage_type", "unknown"),
            claim_row.get("user_claim", ""),
            claim_row.get("claim_object", "").lower(),
            risk_flags,
        )
        justification = self._reasoning_trace(parser_result, vision_result, evidence_result, rule_result, risk_flags)

        row = {
            "user_id": claim_row.get("user_id", ""),
            "image_paths": claim_row.get("image_paths", ""),
            "user_claim": claim_row.get("user_claim", ""),
            "claim_object": claim_row.get("claim_object", "").lower(),
            "evidence_standard_met": "true" if evidence_result.get("evidence_standard_met", False) else "false",
            "evidence_standard_met_reason": evidence_result.get("evidence_standard_met_reason", evidence_result.get("reason", "")),
            "risk_flags": ";".join(risk_flags) if risk_flags else "none",
            "issue_type": vision_result.get("damage_type", "unknown"),
            "object_part": vision_result.get("object_part", "unknown"),
            "claim_status": status,
            "claim_status_justification": justification,
            "supporting_image_ids": ";".join(vision_result.get("supporting_images", [])) or "none",
            "valid_image": "true" if evidence_result.get("valid_image", False) else "false",
            "severity": severity,
        }
        return self.validator.validate(row)

    def fallback_output(self, claim_row: dict[str, str], error_message: str) -> dict[str, str]:
        return self.validator.validate({
            "user_id": claim_row.get("user_id", "unknown"),
            "image_paths": claim_row.get("image_paths", ""),
            "user_claim": claim_row.get("user_claim", ""),
            "claim_object": claim_row.get("claim_object", "unknown"),
            "evidence_standard_met": "false",
            "evidence_standard_met_reason": f"Processing error: {error_message[:100]}",
            "risk_flags": "manual_review_required",
            "issue_type": "unknown",
            "object_part": "unknown",
            "claim_status": "not_enough_information",
            "claim_status_justification": "Automated processing failed; manual review required.",
            "supporting_image_ids": "none",
            "valid_image": "false",
            "severity": "unknown",
        })

    def _merge_flags(
        self,
        risk_flags: list[str],
        rule_result: dict[str, Any],
        vision_result: dict[str, Any],
    ) -> list[str]:
        internal = {"evidence_insufficient", "low_confidence", "object_part_mismatch"}
        flags = {flag for flag in risk_flags if flag and flag != "none" and flag not in internal}

        if rule_result.get("review_candidate"):
            flags.add("manual_review_required")
        if vision_result.get("conflicting_images"):
            flags.add("manual_review_required")
            flags.add("claim_mismatch")

        return sorted(flags)

    def _reasoning_trace(
        self,
        parser_result: dict[str, str],
        vision_result: dict[str, Any],
        evidence_result: dict[str, Any],
        rule_result: dict[str, Any],
        risk_flags: list[str],
    ) -> str:
        supporting = vision_result.get("supporting_images", [])
        supporting_text = ", ".join(supporting) if supporting else "none"
        risks = ";".join(risk_flags) if risk_flags else "none"
        return (
            f"Claimed {parser_result.get('claimed_damage_type', 'unknown')} on "
            f"{parser_result.get('claimed_object_part', 'unknown')}. "
            f"Visible {vision_result.get('damage_type', 'unknown')} on "
            f"{vision_result.get('object_part', 'unknown')} in supporting images: {supporting_text}. "
            f"Evidence standard {'satisfied' if evidence_result.get('evidence_standard_met') else 'not satisfied'}. "
            f"Confidence {rule_result.get('confidence', 0.0):.2f}. "
            f"Rule decision: {rule_result.get('justification', '')} "
            f"Risk flags: {risks}."
        )
