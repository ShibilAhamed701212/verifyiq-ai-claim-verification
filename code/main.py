"""
Primary orchestrator for the Multi-Modal Evidence Review System.
Reads claim data, processes each claim via the multi-modal engine,
and writes the final output CSV.
"""

import csv
from pathlib import Path
from typing import Any

from claim_processor import ClaimProcessor
from config import Config
from submission_critic import validate_output_rows
from utils import ensure_output_dir, setup_logging

logger = setup_logging()


def read_claims(csv_path: Path) -> list[dict[str, str]]:
    claims = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims.append(row)
    logger.info(f"Loaded {len(claims)} claims from {csv_path}")
    return claims


def write_output(output_path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
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

    ensure_output_dir(output_path.parent)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            cleaned = {field: row.get(field, "") for field in fieldnames}
            writer.writerow(cleaned)

    logger.info(f"Wrote {len(rows)} rows to {output_path}")


def main() -> None:
    config = Config()

    logger.info("=" * 60)
    logger.info("Multi-Modal Evidence Review System")
    logger.info("=" * 60)

    claims = read_claims(config.claims_path)
    processor = ClaimProcessor(config)

    results = []
    for idx, claim_row in enumerate(claims, start=1):
        logger.info(f"Processing claim {idx}/{len(claims)} (user: {claim_row['user_id']})")
        try:
            result = processor.process_claim(claim_row)
            results.append(result)
        except Exception as e:
            logger.error(f"Error processing claim {idx}: {e}", exc_info=True)
            fallback = {
                "user_id": claim_row.get("user_id", "unknown"),
                "image_paths": claim_row.get("image_paths", ""),
                "user_claim": claim_row.get("user_claim", ""),
                "claim_object": claim_row.get("claim_object", "unknown"),
                "evidence_standard_met": "false",
                "evidence_standard_met_reason": f"Processing error: {str(e)[:100]}",
                "risk_flags": "manual_review_required",
                "issue_type": "unknown",
                "object_part": "unknown",
                "claim_status": "not_enough_information",
                "claim_status_justification": "Automated processing failed; manual review required.",
                "supporting_image_ids": "none",
                "valid_image": "false",
                "severity": "unknown",
            }
            results.append(fallback)

    results = validate_output_rows(results)

    write_output(config.output_path, results)

    logger.info("=" * 60)
    logger.info("Processing complete. Output written to %s", config.output_path)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
