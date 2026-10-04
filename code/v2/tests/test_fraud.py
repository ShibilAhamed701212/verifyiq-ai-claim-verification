"""Tests for Fraud Engine — Phase 3"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from code.v2.fraud.behavioral_fraud import BehavioralFraudDetector
from code.v2.fraud.image_fraud import ImageFraudDetector
from code.v2.fraud.metadata_fraud import MetadataFraudDetector


class TestImageFraud:
    def setup_method(self):
        self.detector = ImageFraudDetector()

    def test_empty_images(self):
        r = self.detector.check([])
        assert r.fraud_score == 0.0

    def test_no_fraud_normal(self):
        r = self.detector.check([])
        assert len(r.flags) == 0

    def test_nonexistent_path(self):
        r = self.detector.check(["nonexistent.jpg"])
        assert r.fraud_score == 0.0

class TestMetadataFraud:
    def setup_method(self):
        self.detector = MetadataFraudDetector()

    def test_empty_images(self):
        r = self.detector.check([])
        assert r.fraud_score == 0.0

    def test_nonexistent_path(self):
        r = self.detector.check(["nonexistent.jpg"])
        assert r.fraud_score == 0.0

class TestBehavioralFraud:
    def setup_method(self):
        self.detector = BehavioralFraudDetector()

    def test_empty_user(self):
        r = self.detector.check("unknown_user", "dent", [])
        assert r.fraud_score == 0.0

    def test_no_history(self):
        r = self.detector.check("new_user", "dent", [])
        assert r.repeated_claims == 0
