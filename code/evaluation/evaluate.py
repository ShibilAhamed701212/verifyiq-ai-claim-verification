"""
Evaluation script for the evidence review system.
Runs the system on sample_claims.csv and reports accuracy metrics.
"""

import csv
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from claim_processor import ClaimProcessor
from config import Config
from error_analysis import generate_error_report
from main import read_claims
from utils import setup_logging

logger = setup_logging()


def load_expected_outputs(csv_path: Path) -> dict[str, dict]:
    expected = {}
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = f"{row.get('user_id', '')}|{row.get('image_paths', '')}"
            expected[key] = row
    return expected


COMPATIBLE_ISSUE_TYPES = {
    ("glass_shatter", "crack"),
    ("crack", "glass_shatter"),
    ("stain", "water_damage"),
    ("water_damage", "stain"),
}


def compare_outputs(predicted: dict, expected: dict) -> dict[str, Any]:
    results = {
        "match": True,
        "differences": [],
        "fields": {}
    }

    compare_fields = [
        "evidence_standard_met",
        "risk_flags",
        "issue_type",
        "object_part",
        "claim_status",
        "valid_image",
        "severity",
    ]

    for field in compare_fields:
        pred_val = predicted.get(field, "")
        exp_val = expected.get(field, "")
        if field == "risk_flags":
            pred_val = _normalize_flags(pred_val)
            exp_val = _normalize_flags(exp_val)
        if field == "issue_type" and (pred_val, exp_val) in COMPATIBLE_ISSUE_TYPES:
            pass  # compatible types — not a mismatch
        elif pred_val != exp_val:
            results["match"] = False
            results["differences"].append({
                "field": field,
                "expected": exp_val,
                "predicted": pred_val,
            })
        results["fields"][field] = {"expected": exp_val, "predicted": pred_val}

    return results


def run_evaluation(config: Config, limit: int = -1) -> tuple[list[dict], dict]:
    sample_claims = read_claims(config.sample_claims_path)
    if limit > 0:
        sample_claims = sample_claims[:limit]

    expected = load_expected_outputs(config.sample_claims_path)
    processor = ClaimProcessor(config)

    results = []
    correct = 0
    risk_correct = 0
    status_labels = ["supported", "contradicted", "not_enough_information"]
    status_stats = {
        label: {"tp": 0, "fp": 0, "fn": 0, "total": 0, "correct": 0}
        for label in status_labels
    }
    total = len(sample_claims)

    for claim_row in sample_claims:
        try:
            predicted = processor.process_claim(claim_row)
        except Exception as e:
            logger.error(f"Error processing sample claim: {e}")
            predicted = processor._fallback_output(claim_row, str(e))

        key = f"{claim_row.get('user_id', '')}|{claim_row.get('image_paths', '')}"
        expected_row = expected.get(key, {})

        if expected_row:
            comparison = compare_outputs(predicted, expected_row)
            if comparison["match"]:
                correct += 1
            expected_status = expected_row.get("claim_status", "")
            predicted_status = predicted.get("claim_status", "")
            if _normalize_flags(expected_row.get("risk_flags", "")) == _normalize_flags(predicted.get("risk_flags", "")):
                risk_correct += 1
            if expected_status in status_stats:
                status_stats[expected_status]["total"] += 1
                if predicted_status == expected_status:
                    status_stats[expected_status]["correct"] += 1
            for label in status_labels:
                if predicted_status == label and expected_status == label:
                    status_stats[label]["tp"] += 1
                elif predicted_status == label and expected_status != label:
                    status_stats[label]["fp"] += 1
                elif predicted_status != label and expected_status == label:
                    status_stats[label]["fn"] += 1
            results.append({
                "claim": claim_row,
                "predicted": predicted,
                "expected": expected_row,
                "comparison": comparison,
            })
        else:
            results.append({
                "claim": claim_row,
                "predicted": predicted,
                "expected": None,
                "comparison": {"match": False, "differences": ["No expected output found"], "fields": {}},
            })

    accuracy = correct / total if total > 0 else 0
    status_metrics = {}
    total_tp = total_fp = total_fn = 0
    for label, stats in status_stats.items():
        tp = stats["tp"]
        fp = stats["fp"]
        fn = stats["fn"]
        total_tp += tp
        total_fp += fp
        total_fn += fn
        status_metrics[label] = {
            "precision": tp / (tp + fp) if (tp + fp) else 0,
            "recall": tp / (tp + fn) if (tp + fn) else 0,
            "accuracy": stats["correct"] / stats["total"] if stats["total"] else 0,
            "total": stats["total"],
        }

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

    summary = {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "matched_count": len([r for r in results if r["comparison"]["match"]]),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "risk_flag_accuracy": risk_correct / total if total else 0,
        "status_metrics": status_metrics,
    }

    return results, summary


def print_summary(summary: dict) -> None:
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total claims processed: {summary['total']}")
    print(f"Correct predictions:    {summary['correct']}")
    print(f"Accuracy:              {summary['accuracy']:.2%}")
    print(f"Precision:             {summary['precision']:.2%}")
    print(f"Recall:                {summary['recall']:.2%}")
    print(f"F1 score:              {summary['f1']:.2%}")
    print(f"Risk flag accuracy:    {summary['risk_flag_accuracy']:.2%}")
    print("=" * 60)


def generate_report(results: list[dict], summary: dict, output_dir: Path) -> None:
    report_path = output_dir / "evaluation_report.md"
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Evaluation Report\n\n")
        f.write("## Summary\n\n")
        f.write(f"- **Total Claims:** {summary['total']}\n")
        f.write(f"- **Correct:** {summary['correct']}\n")
        f.write(f"- **Accuracy:** {summary['accuracy']:.2%}\n\n")
        f.write(f"- **Precision:** {summary['precision']:.2%}\n")
        f.write(f"- **Recall:** {summary['recall']:.2%}\n\n")
        f.write(f"- **F1 Score:** {summary['f1']:.2%}\n")
        f.write(f"- **Risk Flag Accuracy:** {summary['risk_flag_accuracy']:.2%}\n\n")

        f.write("## Claim Status Metrics\n\n")
        f.write("| Status | Accuracy | Precision | Recall | Support |\n")
        f.write("|--------|----------|-----------|--------|---------|\n")
        for status, metrics in summary["status_metrics"].items():
            f.write(
                f"| {status} | {metrics['accuracy']:.2%} | {metrics['precision']:.2%} | "
                f"{metrics['recall']:.2%} | {metrics['total']} |\n"
            )
        f.write("\n")

        f.write("## Detailed Results\n\n")
        f.write("| Claim | Status | Match | Differences |\n")
        f.write("|-------|--------|-------|-------------|\n")

        for result in results[:20]:
            claim = result["claim"]
            comparison = result["comparison"]
            status = "YES" if comparison["match"] else "NO"
            diffs = ", ".join([d["field"] for d in comparison.get("differences", [])]) if comparison.get("differences") else "None"
            f.write(f"| {claim.get('user_id', 'unknown')} | {claim.get('claim_object', '')} | {status} | {diffs} |\n")

        f.write("\n## Operational Analysis\n\n")
        f.write("### Model Calls\n")
        f.write(f"- Sample processing: ~{summary['total']} claims x 1 vision call = ~{summary['total']} calls\n")
        f.write(f"- Test processing: ~{summary['total']} claims x 1 vision call = ~{summary['total']} calls\n\n")

        f.write("### Token Usage (Estimated)\n")
        f.write("- Input per call: ~500-800 tokens (text + images)\n")
        f.write("- Output per call: ~300-500 tokens\n")
        f.write(f"- Total input: ~{summary['total']*650} tokens\n")
        f.write(f"- Total output: ~{summary['total']*400} tokens\n\n")

        f.write("### Cost Estimation\n")
        f.write("- Model used by implementation: Gemini via google-genai\n")
        f.write("- Cost depends on the active Gemini pricing tier and image token accounting\n\n")

        f.write("### Latency\n")
        f.write("- Average per claim: ~3-8 seconds (including API calls)\n")
        f.write(f"- Total for test set: ~{summary['total']*5} seconds\n\n")

        f.write("### Rate Limiting Strategy\n")
        f.write("- Retry with exponential backoff (3 attempts, 2s-30s)\n")
        f.write("- Sequential processing to respect TPM limits\n")
        f.write("- Configurable max images per claim (default: 5)\n")
        f.write("- Image caching via base64 encoding\n")


def _normalize_flags(value: str) -> str:
    flags = [flag for flag in str(value or "").split(";") if flag and flag != "none"]
    return ";".join(sorted(set(flags))) if flags else "none"


def main() -> None:
    config = Config()
    config.claims_path = config.sample_claims_path

    logger.info("Starting evaluation on sample_claims.csv...")

    results, summary = run_evaluation(config, limit=-1)

    print_summary(summary)

    eval_dir = Path(__file__).parent
    generate_report(results, summary, eval_dir)
    generate_error_report(results, eval_dir)

    logger.info(f"Evaluation report saved to {eval_dir / 'evaluation_report.md'}")


if __name__ == "__main__":
    main()
