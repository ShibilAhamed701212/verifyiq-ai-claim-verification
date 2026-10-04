"""Tests for rule engine decision path ordering."""

import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "code"))

from rule_engine import RuleEngine


class TestRuleEngineOrdering(unittest.TestCase):

    def setUp(self):
        self.engine = RuleEngine()

    def test_evidence_insufficient_overrides_no_damage(self):
        result = self.engine.evaluate(
            parser_result={
                "claimed_damage_type": "crack",
                "claimed_object_part": "headlight",
            },
            vision_result={
                "damage_visible": False,
                "damage_type": "none",
                "object_part": "unknown",
                "confidence": 0.9,
            },
            evidence_result={
                "evidence_standard_met": False,
                "reason": "Image does not show the headlight.",
            },
        )
        self.assertEqual("not_enough_information", result["claim_status"])

    def test_evidence_sufficient_no_damage_contradicted(self):
        result = self.engine.evaluate(
            parser_result={
                "claimed_damage_type": "dent",
                "claimed_object_part": "door",
            },
            vision_result={
                "damage_visible": False,
                "damage_type": "none",
                "object_part": "door",
                "confidence": 0.9,
            },
            evidence_result={
                "evidence_standard_met": True,
                "reason": "Door is clearly visible with no damage.",
            },
        )
        self.assertEqual("contradicted", result["claim_status"])

    def test_part_mismatch_contradicted(self):
        result = self.engine.evaluate(
            parser_result={
                "claimed_damage_type": "scratch",
                "claimed_object_part": "front_bumper",
            },
            vision_result={
                "damage_visible": True,
                "damage_type": "scratch",
                "object_part": "rear_bumper",
                "confidence": 0.9,
            },
            evidence_result={
                "evidence_standard_met": True,
                "reason": "Visible.",
            },
        )
        self.assertEqual("contradicted", result["claim_status"])

    def test_type_mismatch_not_enough(self):
        result = self.engine.evaluate(
            parser_result={
                "claimed_damage_type": "scratch",
                "claimed_object_part": "hood",
            },
            vision_result={
                "damage_visible": True,
                "damage_type": "dent",
                "object_part": "hood",
                "confidence": 0.9,
            },
            evidence_result={
                "evidence_standard_met": True,
                "reason": "Visible.",
            },
        )
        self.assertEqual("contradicted", result["claim_status"])

    def test_supported(self):
        result = self.engine.evaluate(
            parser_result={
                "claimed_damage_type": "dent",
                "claimed_object_part": "hood",
            },
            vision_result={
                "damage_visible": True,
                "damage_type": "dent",
                "object_part": "hood",
                "confidence": 0.9,
            },
            evidence_result={
                "evidence_standard_met": True,
                "reason": "Visible.",
            },
        )
        self.assertEqual("supported", result["claim_status"])

    # --- Compatible damage types ---

    def test_glass_shatter_compatible_with_crack(self):
        result = self.engine.evaluate(
            parser_result={
                "claimed_damage_type": "glass_shatter",
                "claimed_object_part": "screen",
            },
            vision_result={
                "damage_visible": True,
                "damage_type": "crack",
                "object_part": "screen",
                "confidence": 0.9,
            },
            evidence_result={
                "evidence_standard_met": True,
                "reason": "Visible.",
            },
        )
        self.assertEqual("supported", result["claim_status"])

    def test_crack_compatible_with_glass_shatter(self):
        result = self.engine.evaluate(
            parser_result={
                "claimed_damage_type": "crack",
                "claimed_object_part": "screen",
            },
            vision_result={
                "damage_visible": True,
                "damage_type": "glass_shatter",
                "object_part": "screen",
                "confidence": 0.9,
            },
            evidence_result={
                "evidence_standard_met": True,
                "reason": "Visible.",
            },
        )
        self.assertEqual("supported", result["claim_status"])

    def test_stain_compatible_with_water_damage(self):
        result = self.engine.evaluate(
            parser_result={
                "claimed_damage_type": "stain",
                "claimed_object_part": "keyboard",
            },
            vision_result={
                "damage_visible": True,
                "damage_type": "water_damage",
                "object_part": "keyboard",
                "confidence": 0.9,
            },
            evidence_result={
                "evidence_standard_met": True,
                "reason": "Visible.",
            },
        )
        self.assertEqual("supported", result["claim_status"])

    def test_water_damage_compatible_with_stain(self):
        result = self.engine.evaluate(
            parser_result={
                "claimed_damage_type": "water_damage",
                "claimed_object_part": "keyboard",
            },
            vision_result={
                "damage_visible": True,
                "damage_type": "stain",
                "object_part": "keyboard",
                "confidence": 0.9,
            },
            evidence_result={
                "evidence_standard_met": True,
                "reason": "Visible.",
            },
        )
        self.assertEqual("supported", result["claim_status"])


if __name__ == "__main__":
    unittest.main()
