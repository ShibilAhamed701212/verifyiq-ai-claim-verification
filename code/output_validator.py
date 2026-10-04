"""
Output schema and enum validation with consistency checks.
"""

import logging
from typing import Any

from config import Config

logger = logging.getLogger("evidence_review.output_validator")


class OutputValidator:
    """Ensures no invalid enum values reach output.csv and catches contradictions."""

    FIELDNAMES = [
        "user_id",
        "image_paths",
        "user_claim",
        "claim_object",
        "evidence_standard_met",
        "evidence_standard_met_reason",
        "risk_flags",
        "issue_type",
        "object_part",
        "claim_status",
        "claim_status_justification",
        "supporting_image_ids",
        "valid_image",
        "severity",
    ]

    def __init__(self, config: Config):
        self.config = config

    def validate(self, row: dict[str, Any]) -> dict[str, str]:
        cleaned = {field: str(row.get(field, "")) for field in self.FIELDNAMES}

        if cleaned["claim_object"] not in self.config.ALLOWED_OBJECT_PARTS:
            cleaned["claim_object"] = "car" if not cleaned["claim_object"] else cleaned["claim_object"]

        if cleaned["issue_type"] not in self.config.ALLOWED_ISSUE_TYPES:
            cleaned["issue_type"] = "unknown"

        allowed_parts = self.config.ALLOWED_OBJECT_PARTS.get(cleaned["claim_object"], {"unknown"})
        if cleaned["object_part"] not in allowed_parts:
            cleaned["object_part"] = "unknown"

        if cleaned["claim_status"] not in self.config.ALLOWED_CLAIM_STATUS:
            cleaned["claim_status"] = "not_enough_information"

        if cleaned["severity"] not in self.config.ALLOWED_SEVERITY:
            cleaned["severity"] = "unknown"

        for bool_field in ("evidence_standard_met", "valid_image"):
            cleaned[bool_field] = "true" if str(cleaned[bool_field]).lower() in ("true", "yes", "y", "1") else "false"

        flags = [f for f in cleaned["risk_flags"].split(";") if f]
        valid_flags = [f for f in flags if f in self.config.ALLOWED_RISK_FLAGS and f != "none"]
        cleaned["risk_flags"] = ";".join(sorted(set(valid_flags))) if valid_flags else "none"

        if not cleaned["supporting_image_ids"]:
            cleaned["supporting_image_ids"] = "none"

        return self._consistency_check(cleaned)

    def _consistency_check(self, row: dict[str, str]) -> dict[str, str]:
        status = row.get("claim_status", "")
        issue_type = row.get("issue_type", "")
        flags = self._parse_flags(row.get("risk_flags", ""))
        changed = False

        if status == "supported" and issue_type in ("none", "unknown", ""):
            row["claim_status"] = "contradicted" if issue_type == "none" else "not_enough_information"
            row["claim_status_justification"] = (
                row.get("claim_status_justification", "")
                + f" [Consistency: status={status} incompatible with issue_type={issue_type}]"
            )
            logger.info(f"Consistency fix: user={row.get('user_id')} status={status}->{row['claim_status']} (issue={issue_type})")
            changed = True

        if status == "contradicted" and row.get("issue_type", "unknown") not in ("none", "unknown", ""):
            if row.get("evidence_standard_met", "false").lower() != "true":
                row["claim_status"] = "not_enough_information"
                row["claim_status_justification"] = (
                    row.get("claim_status_justification", "")
                    + " [Consistency: contradicted but evidence not met]"
                )
                logger.info(f"Consistency fix: user={row.get('user_id')} contradicted->not_enough_information (evidence not met)")
                changed = True

        critical = {"possible_manipulation", "non_original_image", "user_history_risk"}
        if flags & critical and "manual_review_required" not in flags:
            flags.add("manual_review_required")
            row["risk_flags"] = ";".join(sorted(flags))
            changed = True

        if changed:
            pass
        return row

    def _parse_flags(self, raw: str) -> set[str]:
        return {f.strip() for f in raw.split(";") if f.strip() and f.strip() != "none"}
