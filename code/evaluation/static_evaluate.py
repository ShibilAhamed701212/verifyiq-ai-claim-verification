"""Static evaluation using expected values as ideal vision input."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from claim_parser import ClaimParser
from config import Config
from decision_agent import DecisionAgent
from evidence_checker import EvidenceChecker
from output_validator import OutputValidator
from risk_analyzer import RiskAnalyzer
from rule_engine import RuleEngine
from severity_engine import SeverityEngine
from utils import parse_image_paths

config = Config()
parser = ClaimParser(config)
checker = EvidenceChecker(config.evidence_reqs_path)
rule = RuleEngine()
risk = RiskAnalyzer(config)
val = OutputValidator(config)
sev = SeverityEngine()
agent = DecisionAgent(val, sev)

def normalize_flags(value):
    flags = [f for f in str(value or "").split(";") if f and f != "none"]
    return ";".join(sorted(set(flags))) if flags else "none"

FIELDS = ["evidence_standard_met", "risk_flags", "issue_type",
          "object_part", "claim_status", "valid_image", "severity"]

rows = []
with open(config.sample_claims_path, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows.append(r)

user_history_cache = {}
if config.user_history_path.exists():
    with open(config.user_history_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            uid = r.get("user_id", "").strip()
            if uid:
                user_history_cache[uid] = r

results = []
correct = 0
for row in rows:
    uid = row["user_id"]
    image_paths_str = row.get("image_paths", "").strip()
    user_claim = row.get("user_claim", "").strip()
    claim_object = row.get("claim_object", "").strip().lower()

    image_paths = parse_image_paths(image_paths_str, config.images_dir)

    # Use expected values as ideal vision
    dt = row["issue_type"]
    op = row["object_part"]
    exp_risk = row.get("risk_flags", "")
    dv = "damage_not_visible" not in exp_risk and dt not in ("none", "")
    no_angle = "wrong_angle" in exp_risk
    no_obstruct = "cropped_or_obstructed" in exp_risk
    no_original = "non_original_image" in exp_risk
    wrong_obj = "wrong_object" in exp_risk
    assessments_list = [{
        "image_id": p.stem, "damage_visible": dv,
        "damage_type": dt, "object_part": op,
        "is_clear": True,
        "is_cropped": no_obstruct,
        "lighting_adequate": True,
        "angle_sufficient": not no_angle,
        "confidence": 0.85,
        "image_quality": "good",
        "issues_visible": [dt] if dv else [],
        "affected_parts": [op] if op not in ("unknown", "") else [],
        "damage_description": "",
    } for p in image_paths] if image_paths else []
    vision = {
        "damage_type": dt,
        "object_part": op,
        "damage_visible": dv,
        "confidence": 0.85,
        "supporting_images": [p.stem for p in image_paths],
        "image_assessments": assessments_list,
        "per_image_assessments": assessments_list,
        "conflicting_images": False,
        "notes": "non-original" if no_original else ("wrong object" if wrong_obj else ""),
        "image_quality": "good",
    }

    parser_result = parser.parse(user_claim, claim_object)
    evidence_result = checker.evaluate(
        claim_object=claim_object,
        parser_result=parser_result,
        vision_result=vision,
        total_images=len(image_paths),
    )

    rule_result = rule.evaluate(parser_result, vision, evidence_result)
    risk_result = risk.analyze(
        image_analysis=vision,
        user_history=user_history_cache.get(uid),
        claim_object=claim_object,
        user_claim=user_claim,
        evidence_result=evidence_result,
        rule_result=rule_result,
        image_paths=image_paths if image_paths else None,
    )

    claim_input = {"user_id": uid, "image_paths": image_paths_str,
                   "user_claim": user_claim, "claim_object": claim_object}
    output = agent.build_output_row(claim_input, parser_result, vision, evidence_result, rule_result, risk_result)

    match = all(
        normalize_flags(output.get(f)) == normalize_flags(row.get(f))
        if f == "risk_flags" else output.get(f) == row.get(f)
        for f in FIELDS
    )
    if match:
        correct += 1

    results.append({
        "user_id": uid, "match": match, "output": output,
        "parser": parser_result, "expected": row,
    })

print("=" * 70)
print("STATIC EVALUATION (ideal vision + CV modules)")
print("=" * 70)
print(f"Correct: {correct}/{len(rows)} ({correct/len(rows)*100:.0f}%)")
print()

print(f"{'Claim':<10} {'Match':<8} {'Parser DT':<20} {'Parser Part':<18} {'Status':<20} {'Risk Flags'}")
print("-" * 95)
for r in results:
    uid = r["user_id"]
    p = r["parser"]
    o = r["output"]
    nm = "MATCH" if r["match"] else "FAIL"
    status = f"{o['claim_status']}/{r['expected']['claim_status']}"
    risk = normalize_flags(o["risk_flags"])
    exp_risk = normalize_flags(r["expected"]["risk_flags"])
    risk_str = f"{risk}/{exp_risk}" if risk != exp_risk else risk
    print(f"{uid:<10} {nm:<8} {p['claimed_damage_type']:<20} {p['claimed_object_part']:<18} {status:<20} {risk_str}")

print()
print("FIXED CLAIMS (were FAIL, now MATCH):")
for r in results:
    if r["match"]:
        print(f"  {r['user_id']}")

print()
print("REMAINING FAILURES:")
for r in results:
    if not r["match"]:
        o, e = r["output"], r["expected"]
        diffs = []
        for f in FIELDS:
            pv = normalize_flags(o.get(f)) if f == "risk_flags" else o.get(f)
            ev = normalize_flags(e.get(f)) if f == "risk_flags" else e.get(f)
            if pv != ev:
                diffs.append(f"{f}: {pv}/{ev}")
        print(f"  {r['user_id']}: {'; '.join(diffs)}")
