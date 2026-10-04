"""Tests for V2Critic — Phase 8"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from code.v2.critic.v2_critic import V2Critic
from code.v2.models.consensus import ConsensusReport
from code.v2.models.conversation import ConversationReport
from code.v2.models.decision import V2Decision
from code.v2.models.fraud import FraudReport


class TestV2Critic:
    def setup_method(self):
        self.critic = V2Critic()

    def test_clean_decision_passes(self):
        decision = V2Decision(claim_status="supported", issue_type="dent", evidence_standard_met=True, confidence=0.85, severity="medium")
        fraud = FraudReport()
        conversation = ConversationReport()
        consensus = ConsensusReport(agreement_score=0.9, confidence=0.85, uncertainty=0.0, models_succeeded=2, unanimous=True)
        result, issues = self.critic.review(decision, fraud, conversation, consensus)
        assert result == "PASS"

    def test_supported_without_evidence(self):
        decision = V2Decision(claim_status="supported", issue_type="dent", evidence_standard_met=False, confidence=0.85)
        fraud = FraudReport()
        conversation = ConversationReport()
        consensus = ConsensusReport(agreement_score=0.9, confidence=0.85, uncertainty=0.1, models_succeeded=2)
        result, issues = self.critic.review(decision, fraud, conversation, consensus)
        assert result == "REVIEW_REQUIRED"
        assert any("without_evidence" in i for i in issues)

    def test_high_fraud_with_supported(self):
        decision = V2Decision(claim_status="supported", issue_type="dent", evidence_standard_met=True)
        fraud = FraudReport(overall_fraud_score=0.8, high_risk=True)
        conversation = ConversationReport()
        consensus = ConsensusReport(agreement_score=0.5, confidence=0.5, uncertainty=0.5, models_succeeded=1)
        result, issues = self.critic.review(decision, fraud, conversation, consensus)
        assert result == "REVIEW_REQUIRED"

    def test_retracted_claim(self):
        decision = V2Decision(claim_status="supported", issue_type="dent", evidence_standard_met=True)
        fraud = FraudReport()
        conversation = ConversationReport(has_retraction=True)
        consensus = ConsensusReport(agreement_score=0.9, confidence=0.85, uncertainty=0.1, models_succeeded=2)
        result, issues = self.critic.review(decision, fraud, conversation, consensus)
        assert result == "REVIEW_REQUIRED"
