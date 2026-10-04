"""VerifyIQ V2 Pipeline — initialize and run with degraded observation (no API key needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    from verifyiq.v2.pipeline import V2Pipeline

    print("Initializing V2Pipeline (no API keys — will use degraded observation)...")
    pipeline = V2Pipeline({"providers": {}})

    claim_text = (
        "Customer: I noticed a crack on my windshield after a "
        "small stone hit it while driving."
    )
    claim_object = "car"
    image_paths = []
    user_id = "example_user"

    print(f"\nProcessing claim: {claim_text[:70]}...")
    print(f"Object: {claim_object}")
    print(f"Images: {image_paths}")
    print()

    decision = pipeline.process(
        claim_text=claim_text,
        claim_object=claim_object,
        image_paths=image_paths,
        user_id=user_id,
    )

    print("V2Decision result:")
    print(f"  claim_status:         {decision.claim_status}")
    print(f"  issue_type:           {decision.issue_type}")
    print(f"  object_part:          {decision.object_part}")
    print(f"  severity:             {decision.severity}")
    print(f"  confidence:           {decision.confidence:.3f}")
    print(f"  evidence_standard_met: {decision.evidence_standard_met}")
    print(f"  valid_image:          {decision.valid_image}")
    print(f"  risk_flags:           {decision.risk_flags}")
    print(f"  supporting_image_ids: {decision.supporting_image_ids}")
    print(f"  justification:        {decision.justification[:120]}...")
    print()

    if not decision.risk_flags:
        print("Note: No risk flags — all observations were degraded (expected without API keys).")
    print("V2Pipeline completed without raising (degraded-by-design).")


if __name__ == "__main__":
    main()
