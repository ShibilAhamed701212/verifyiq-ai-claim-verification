"""Tests for EvidenceRecommender — Phase 4"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from code.v2.evidence.recommender import EvidenceRecommender
from code.v2.models.evidence import EvidenceReport


class TestEvidenceRecommender:
    def setup_method(self):
        self.recommender = EvidenceRecommender()

    def test_evidence_met_no_recommendations(self):
        report = EvidenceReport(evidence_standard_met=True)
        result = self.recommender.recommend(report)
        assert len(result.recommendations) == 0

    def test_not_met_gets_recommendations(self):
        report = EvidenceReport(evidence_standard_met=False, reason="no clear images")
        result = self.recommender.recommend(report)
        assert len(result.recommendations) > 0

    def test_multiple_recommendations(self):
        report = EvidenceReport(evidence_standard_met=False, reason="blurry image, bad lighting")
        result = self.recommender.recommend(report)
        assert len(result.recommendations) >= 2

    def test_default_recommendation(self):
        report = EvidenceReport(evidence_standard_met=False, reason="unknown")
        result = self.recommender.recommend(report)
        assert len(result.recommendations) > 0
