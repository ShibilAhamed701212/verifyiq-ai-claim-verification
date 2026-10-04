from code.v2.models.consensus import ConsensusReport
from code.v2.models.conversation import ConversationReport
from code.v2.models.decision import V2Decision
from code.v2.models.fraud import FraudReport


class V2Critic:
    """Post-processing consistency checks for V2 decisions.

    Checks: status consistency, severity consistency, object consistency,
    evidence consistency, fraud consistency.
    Returns: PASS or REVIEW_REQUIRED with reasons.
    """

    def review(self, decision: V2Decision, fraud: FraudReport,
                conversation: ConversationReport, consensus: ConsensusReport) -> tuple[str, list[str]]:
        issues = []

        # Status consistency
        if decision.claim_status == "supported" and decision.issue_type in ("none", "unknown"):
            issues.append("supported_with_invalid_issue")
        if decision.claim_status == "supported" and not decision.evidence_standard_met:
            issues.append("supported_without_evidence")
        if decision.claim_status == "contradicted" and decision.issue_type == "unknown":
            issues.append("contradicted_with_unknown_type")

        # Fraud consistency
        if fraud.high_risk and decision.claim_status == "supported":
            issues.append("high_fraud_with_supported_verdict")
        if fraud.overall_fraud_score > 0.5 and "manual_review_required" not in decision.risk_flags:
            issues.append("high_fraud_without_manual_review")

        # Conversation consistency
        if conversation.has_retraction and decision.claim_status == "supported":
            issues.append("retracted_claim_with_supported_verdict")
        if conversation.has_contradictions and decision.claim_status == "supported":
            issues.append("contradictory_claim_with_supported_verdict")

        # Consensus consistency
        if consensus.agreement_score < 0.5 and decision.claim_status != "not_enough_information":
            issues.append("low_agreement_with_definitive_verdict")
        if consensus.models_succeeded == 0 and not decision.risk_flags:
            issues.append("all_models_failed_without_risk_flags")

        # Severity consistency
        if decision.severity == "high" and decision.confidence < 0.5:
            issues.append("high_severity_with_low_confidence")

        if issues:
            return "REVIEW_REQUIRED", issues
        return "PASS", []
