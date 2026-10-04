"""Tests for DecisionTracer — Phase 9"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from code.v2.explainability.tracer import DecisionTracer
from code.v2.models.confidence import ConfidenceBreakdown, ConfidenceReport
from code.v2.models.consensus import ConsensusReport
from code.v2.models.conversation import ConversationReport
from code.v2.models.decision import V2Decision
from code.v2.models.evidence import EvidenceReport
from code.v2.models.fraud import FraudReport


class TestDecisionTracer:
    def setup_method(self):
        self.tracer = DecisionTracer()

    def test_supported_trace(self):
        decision = V2Decision(claim_status="supported", issue_type="dent", evidence_standard_met=True)
        consensus = ConsensusReport(agreement_score=0.9, confidence=0.85, uncertainty=0.0, models_used=2, models_succeeded=2, unanimous=True)
        fraud = FraudReport(flags=[], overall_fraud_score=0.0)
        conversation = ConversationReport()
        evidence = EvidenceReport(evidence_standard_met=True)
        confidence = ConfidenceReport(final_confidence=0.88, routing="auto", breakdown=ConfidenceBreakdown())
        result = self.tracer.trace(decision, consensus, fraud, conversation, evidence, confidence)
        assert len(result.trace.why_supported) > 0
        assert "supported" in result.justification.lower()

    def test_contradicted_trace(self):
        decision = V2Decision(claim_status="contradicted", issue_type="unknown", evidence_standard_met=False)
        consensus = ConsensusReport(agreement_score=0.3, confidence=0.2, uncertainty=0.7, models_used=1, models_succeeded=0)
        fraud = FraudReport(overall_fraud_score=0.6, high_risk=True, flags=["image_reuse"])
        conversation = ConversationReport(has_retraction=True)
        evidence = EvidenceReport(evidence_standard_met=False, reason="no clear images")
        confidence = ConfidenceReport(final_confidence=0.25, routing="evidence_request", breakdown=ConfidenceBreakdown())
        result = self.tracer.trace(decision, consensus, fraud, conversation, evidence, confidence)
        assert len(result.trace.why_contradicted) > 0
        assert len(result.trace.fraud_trace) > 0
