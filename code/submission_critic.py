"""Post-processing validation and consistency checking for output rows."""

import logging

logger = logging.getLogger("evidence_review.critic")

REQUIRED_FIELDS = {
    "user_id", "image_paths", "user_claim", "claim_object",
    "evidence_standard_met", "evidence_standard_met_reason",
    "risk_flags", "issue_type", "object_part", "claim_status",
    "claim_status_justification", "supporting_image_ids", "valid_image", "severity",
}

RISK_FLAGS_THAT_ALLOW_UNKNOWN = {
    "manual_review_required", "non_original_image", "possible_manipulation",
}


def validate_output_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Post-process output rows: check for missing fields, contradictions, unknowns without flags."""
    fixed = 0
    for row in rows:
        original = dict(row)

        _ensure_required_fields(row)
        if _fix_unknown_without_review_flag(row):
            fixed += 1
        if _fix_contradiction_detected_supported_with_no_damage(row):
            fixed += 1
        if _fix_contradiction_supported_with_conflict(row):
            fixed += 1
        if _fix_missing_manual_review(row):
            fixed += 1

        if row != original:
            logger.info(f"Critic fixed row {row.get('user_id', '?')}: {_diff(original, row)}")
    return rows


def _ensure_required_fields(row: dict[str, str]) -> None:
    for field in REQUIRED_FIELDS:
        if field not in row or not row[field]:
            row[field] = row.get(field, "")


def _fix_unknown_without_review_flag(row: dict[str, str]) -> bool:
    """If issue_type or severity is unknown, ensure manual_review_required flag is set."""
    flags = _parse_flags(row.get("risk_flags", ""))
    if not flags.intersection(RISK_FLAGS_THAT_ALLOW_UNKNOWN):
        issue_unknown = row.get("issue_type", "") in ("unknown", "")
        severity_unknown = row.get("severity", "") in ("unknown", "")
        part_unknown = row.get("object_part", "") in ("unknown", "")
        status_unknown = row.get("claim_status", "") == "not_enough_information"

        if (issue_unknown or severity_unknown or part_unknown) and not status_unknown:
            flags.add("manual_review_required")
            row["risk_flags"] = ";".join(sorted(flags))
            return True
    return False


def _fix_contradiction_detected_supported_with_no_damage(row: dict[str, str]) -> bool:
    evidence_met = row.get("evidence_standard_met", "").lower() == "true"
    status = row.get("claim_status", "")
    issue_type = row.get("issue_type", "")

    if status == "supported" and issue_type == "none":
        row["claim_status"] = "contradicted"
        row["claim_status_justification"] = row.get("claim_status_justification", "") + " [Critic: supported but damage=none → contradicted]"
        return True

    if status == "supported" and issue_type in ("unknown", ""):
        row["claim_status"] = "not_enough_information"
        row["claim_status_justification"] = row.get("claim_status_justification", "") + " [Critic: supported but damage=unknown → not_enough_information]"
        return True

    if status == "contradicted" and issue_type not in ("none", "unknown"):
        if not evidence_met:
            row["claim_status"] = "not_enough_information"
            row["claim_status_justification"] = row.get("claim_status_justification", "") + " [Critic: contradicted with damage_type but evidence not met]"
            return True

    return False


def _fix_contradiction_supported_with_conflict(row: dict[str, str]) -> bool:
    status = row.get("claim_status", "")
    flags = _parse_flags(row.get("risk_flags", ""))
    if status == "supported" and "claim_mismatch" in flags:
        row["claim_status"] = "contradicted"
        row["claim_status_justification"] = row.get("claim_status_justification", "") + " [Critic: supported but has claim_mismatch flag]"
        return True
    return False


def _fix_missing_manual_review(row: dict[str, str]) -> bool:
    flags = _parse_flags(row.get("risk_flags", ""))
    if not flags:
        return False
    critical = {"possible_manipulation", "non_original_image", "user_history_risk"}
    if flags & critical and "manual_review_required" not in flags:
        flags.add("manual_review_required")
        row["risk_flags"] = ";".join(sorted(flags))
        return True
    return False


def _parse_flags(raw: str) -> set[str]:
    return {f.strip() for f in raw.split(";") if f.strip() and f.strip() != "none"}


def _diff(original: dict[str, str], updated: dict[str, str]) -> str:
    changes = []
    for k in REQUIRED_FIELDS:
        if original.get(k) != updated.get(k):
            changes.append(f"{k}: {original.get(k)!r} -> {updated.get(k)!r}")
    return "; ".join(changes)
