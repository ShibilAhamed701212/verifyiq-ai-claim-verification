"""Tests for Confidence Calibrator — Phase 6"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from code.v2.confidence.calibrator import ConfidenceCalibrator
from code.v2.models.consensus import ConsensusReport
from code.v2.models.conversation import ConversationReport
from code.v2.models.evidence import EvidenceReport
from code.v2.models.fraud import FraudReport


class TestConfidenceCalibrator:
    def setup_method(self):
        self.calibrator = ConfidenceCalibrator()

    def test_high_confidence_auto(self):
        consensus = ConsensusReport(agreement_score=1.0, confidence=0.95, uncertainty=0.0, unanimous=True, models_used=2, models_succeeded=2)
        fraud = FraudReport()
        evidence = EvidenceReport(evidence_standard_met=True)
        conversation = ConversationReport()
        result = self.calibrator.calibrate(consensus, fraud, evidence, conversation)
        assert result.routing == "auto"
        assert result.final_confidence > 0.90

    def test_low_confidence_evidence_request(self):
        consensus = ConsensusReport(agreement_score=0.3, confidence=0.3, uncertainty=0.7, models_used=2, models_succeeded=1)
        fraud = FraudReport(overall_fraud_score=0.8, high_risk=True)
        evidence = EvidenceReport(evidence_standard_met=False)
        conversation = ConversationReport()
        result = self.calibrator.calibrate(consensus, fraud, evidence, conversation)
        assert result.routing == "evidence_request"

    def test_fraud_penalty(self):
        consensus = ConsensusReport(agreement_score=1.0, confidence=0.9, uncertainty=0.0, unanimous=True, models_used=1, models_succeeded=1)
        fraud = FraudReport(overall_fraud_score=0.9, high_risk=True)
        evidence = EvidenceReport(evidence_standard_met=True)
        conversation = ConversationReport()
        result = self.calibrator.calibrate(consensus, fraud, evidence, conversation)
        assert result.final_confidence < 0.9

    def test_conversation_penalty(self):
        consensus = ConsensusReport(agreement_score=1.0, confidence=0.9, uncertainty=0.0, unanimous=True, models_used=1, models_succeeded=1)
        fraud = FraudReport()
        evidence = EvidenceReport(evidence_standard_met=True)
        conversation = ConversationReport(has_retraction=True, has_contradictions=True)
        result = self.calibrator.calibrate(consensus, fraud, evidence, conversation)
        assert result.final_confidence < 0.9
