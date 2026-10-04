"""
Error analysis report generation for sample evaluation.
"""

from pathlib import Path


def classify_error(differences: list[dict[str, str]]) -> str:
    fields = {diff.get("field") for diff in differences if isinstance(diff, dict)}
    if "issue_type" in fields:
        return "damage type mismatch"
    if "object_part" in fields:
        return "object part mismatch"
    if "evidence_standard_met" in fields or "valid_image" in fields:
        return "evidence issue"
    if "risk_flags" in fields:
        return "risk flag issue"
    if "claim_status" in fields:
        return "confidence issue"
    return "other"


def generate_error_report(results: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "error_report.md"

    grouped: dict[str, list[dict]] = {}
    for result in results:
        comparison = result.get("comparison", {})
        if comparison.get("match"):
            continue
        differences = comparison.get("differences", [])
        category = classify_error(differences)
        grouped.setdefault(category, []).append(result)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Error Analysis Report\n\n")
        total_errors = sum(len(items) for items in grouped.values())
        f.write(f"- **Total wrong predictions:** {total_errors}\n\n")

        for category, items in grouped.items():
            f.write(f"## {category.title()}\n\n")
            f.write("| Claim ID | Expected | Predicted | Reason |\n")
            f.write("|----------|----------|-----------|--------|\n")
            for item in items:
                claim = item.get("claim", {})
                expected = item.get("expected", {}) or {}
                predicted = item.get("predicted", {}) or {}
                differences = item.get("comparison", {}).get("differences", [])
                reason = ", ".join(
                    diff.get("field", "unknown") for diff in differences if isinstance(diff, dict)
                ) or "No expected output found"
                f.write(
                    f"| {claim.get('user_id', 'unknown')} | "
                    f"{expected.get('claim_status', 'missing')} | "
                    f"{predicted.get('claim_status', 'missing')} | {reason} |\n"
                )
            f.write("\n")
