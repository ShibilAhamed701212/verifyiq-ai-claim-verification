"""Tests for ConversationAnalyzer — Phase 5"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from code.v2.conversation.analyzer import ConversationAnalyzer


class TestConversationAnalyzer:
    def setup_method(self):
        self.analyzer = ConversationAnalyzer()

    def test_empty_text(self):
        r = self.analyzer.analyze("")
        assert r.has_contradictions is False

    def test_negation_detection(self):
        r = self.analyzer.analyze("There is no dent on the bumper")
        assert r.has_negation is True

    def test_uncertainty_detection(self):
        r = self.analyzer.analyze("I think there might be a scratch")
        assert r.has_uncertainty is True

    def test_retraction_detection(self):
        r = self.analyzer.analyze("Actually no, I changed my mind about the damage")
        assert r.has_retraction is True

    def test_sarcasm_detection(self):
        r = self.analyzer.analyze("Great, another perfect delivery. The box is just awesome.")
        assert r.has_sarcasm is True

    def test_mixed_anomalies(self):
        r = self.analyzer.analyze("I think there's a dent. Actually no, upon further inspection, just great packaging.")
        assert r.has_uncertainty or r.has_retraction or r.has_sarcasm

    def test_no_anomalies_clean_text(self):
        r = self.analyzer.analyze("There is a dent on the rear bumper from the accident yesterday")
        assert r.has_negation is False
        assert r.has_retraction is False

    def test_risk_flags_populated(self):
        r = self.analyzer.analyze("Actually no, I take that back. Perhaps there is no damage.")
        assert len(r.risk_flags) > 0
