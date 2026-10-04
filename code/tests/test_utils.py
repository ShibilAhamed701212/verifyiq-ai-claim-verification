"""Tests for utility functions."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import extract_claim_text


class TestExtractClaimText(unittest.TestCase):

    def test_single_line_customer_support_extracts_last_customer(self):
        conversation = (
            "Customer: Hi, I found a dent on my car. "
            "| Support: Can you describe it? "
            "| Customer: It is on the rear bumper."
        )
        result = extract_claim_text(conversation)
        self.assertEqual("It is on the rear bumper.", result)

    def test_empty_returns_empty(self):
        self.assertEqual("", extract_claim_text(""))
        self.assertEqual("", extract_claim_text(None))

    def test_no_prefix_returns_full_text(self):
        text = "Just a plain message without prefixes."
        self.assertEqual(text, extract_claim_text(text))

    def test_multi_line_user_agent_format(self):
        conversation = "User: I have a crack on my screen.\nAgent: Can you send a photo?\nUser: Here it is."
        result = extract_claim_text(conversation)
        self.assertIn("I have a crack on my screen.", result)
        self.assertIn("Here it is.", result)
        self.assertNotIn("Can you send a photo?", result)

    def test_pipe_format_without_customer_returns_last_segment(self):
        conversation = "Something happened. | Another thing. | Last thing."
        result = extract_claim_text(conversation)
        self.assertEqual("Last thing.", result)

    def test_pipe_format_single_segment_returns_it(self):
        conversation = "Just one segment."
        result = extract_claim_text(conversation)
        self.assertEqual("Just one segment.", result)


if __name__ == "__main__":
    unittest.main()
