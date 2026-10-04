"""Tests for risk flag allowed values."""

import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "code"))

from config import Config
from risk_analyzer import RiskAnalyzer


class TestRiskFlagsAllowed(unittest.TestCase):

    ALLOWED = {
        "blurry_image", "cropped_or_obstructed",
        "low_light_or_glare", "wrong_angle", "wrong_object",
        "wrong_object_part", "damage_not_visible", "claim_mismatch",
        "possible_manipulation", "non_original_image",
        "text_instruction_present", "user_history_risk",
        "manual_review_required",
    }

    def setUp(self):
        self.config = Config()
        self.analyzer = RiskAnalyzer(self.config)

    def test_config_allowed_flags_match_problem_statement(self):
        extra = self.config.ALLOWED_RISK_FLAGS - self.ALLOWED - {"none"}
        self.assertEqual(set(), extra,
            f"Config has non-standard flags: {extra}")

    def test_evidence_insufficient_mapped(self):
        result = self.analyzer.analyze(
            image_analysis={},
            user_history=None,
            claim_object="car",
            user_claim="",
            evidence_result={"evidence_standard_met": False},
            rule_result={
                "mismatch_type": "evidence_insufficient",
                "risk_flags": [],
                "confidence": 0.9,
            },
        )
        self.assertNotIn("evidence_insufficient", result)
        self.assertIn("manual_review_required", result)

    def test_low_confidence_mapped(self):
        result = self.analyzer.analyze(
            image_analysis={"confidence": 0.3},
            user_history=None,
            claim_object="car",
            user_claim="",
            evidence_result={"evidence_standard_met": True},
            rule_result={
                "mismatch_type": "none",
                "risk_flags": [],
                "confidence": 0.3,
            },
        )
        self.assertNotIn("low_confidence", result)
        self.assertIn("manual_review_required", result)

    def test_object_part_mismatch_mapped(self):
        result = self.analyzer.analyze(
            image_analysis={},
            user_history=None,
            claim_object="car",
            user_claim="",
            evidence_result={"evidence_standard_met": True},
            rule_result={
                "mismatch_type": "object_part_mismatch",
                "risk_flags": [],
                "confidence": 0.9,
            },
        )
        self.assertNotIn("object_part_mismatch", result)
        self.assertIn("wrong_object_part", result)


if __name__ == "__main__":
    unittest.main()
