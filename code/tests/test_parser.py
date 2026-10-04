"""Tests for claim parser improvements."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from claim_parser import ClaimParser
from config import Config


class TestClaimParser(unittest.TestCase):

    def setUp(self):
        self.parser = ClaimParser(Config())

    # --- Customer-only filtering ---
    def test_customer_only_keeps_all_customer_messages(self):
        text = "Customer: My laptop hinge broke. | Support: What happened? | Customer: It fell from the table."
        result = self.parser.parse(text, "laptop")
        self.assertEqual(result["claimed_object_part"], "hinge")

    def test_agent_text_does_not_add_false_keywords(self):
        text = "Customer: My screen is fine. | Support: Is the hinge damaged too? | Customer: No, just the screen."
        result = self.parser.parse(text, "laptop")
        self.assertEqual(result["claimed_object_part"], "screen")

    # --- Hinge before screen ---
    def test_laptop_hinge_before_screen(self):
        text = "Customer: The hinge area has broken and the screen wobbles."
        result = self.parser.parse(text, "laptop")
        self.assertEqual(result["claimed_object_part"], "hinge")

    def test_laptop_screen_still_detected(self):
        text = "Customer: My screen has a crack."
        result = self.parser.parse(text, "laptop")
        self.assertEqual(result["claimed_object_part"], "screen")

    # --- Package seal before side ---
    def test_package_seal_before_side(self):
        text = "Customer: Seal wali side phati hui thi."
        result = self.parser.parse(text, "package")
        self.assertEqual(result["claimed_object_part"], "seal")

    def test_package_side_still_detected(self):
        text = "Customer: The side of the box is crushed."
        result = self.parser.parse(text, "package")
        self.assertEqual(result["claimed_object_part"], "package_side")

    # --- Negation handling ---
    def test_negated_hinge_skipped(self):
        text = "Customer: Not the hinge. The issue is the screen."
        result = self.parser.parse(text, "laptop")
        self.assertEqual(result["claimed_object_part"], "screen")

    def test_negated_keyboard_skipped(self):
        text = "Customer: Not the keyboard or hinge. It is the screen."
        result = self.parser.parse(text, "laptop")
        self.assertEqual(result["claimed_object_part"], "screen")

    def test_non_negated_keyword_matches(self):
        text = "Customer: The hinge is broken."
        result = self.parser.parse(text, "laptop")
        self.assertEqual(result["claimed_object_part"], "hinge")

    # --- Damage type ---
    def test_stain_detected(self):
        text = "Customer: There is a stain on the keyboard."
        result = self.parser.parse(text, "laptop")
        self.assertEqual(result["claimed_damage_type"], "stain")

    def test_water_damage_detected(self):
        text = "Customer: Water damage on the package side."
        result = self.parser.parse(text, "package")
        self.assertEqual(result["claimed_damage_type"], "water_damage")


if __name__ == "__main__":
    unittest.main()
