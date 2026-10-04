from verifyiq.v2.models.confidence import ConfidenceBreakdown, ConfidenceReport
from verifyiq.v2.models.consensus import ConsensusReport
from verifyiq.v2.models.conversation import ConversationReport
from verifyiq.v2.models.evidence import EvidenceReport
from verifyiq.v2.models.fraud import FraudReport


class ConfidenceCalibrator:
    """Combines multiple signals into calibrated final confidence.

    Routing:
      > 0.90 → auto
      0.75-0.90 → fast review
      0.50-0.75 → manual review
      < 0.50 → evidence request
    """

    def calibrate(self, consensus: ConsensusReport, fraud: FraudReport,
                   evidence: EvidenceReport, conversation: ConversationReport) -> ConfidenceReport:
        model_conf = consensus.confidence
        agreement = consensus.agreement_score

        # Start with model confidence as baseline
        base = model_conf if model_conf > 0 else 0.3

        # Boost from agreement
        agreement_boost = agreement * 0.15

        # Penalize fraud
        fraud_penalty = fraud.overall_fraud_score * 0.3

        # Boost from evidence
        evidence_boost = 0.1 if evidence.evidence_standard_met else -0.1

        # Penalize conversation issues
        conv_penalty = 0.0
        if conversation.has_retraction:
            conv_penalty += 0.2
        if conversation.has_contradictions:
            conv_penalty += 0.15
        if conversation.has_uncertainty:
            conv_penalty += 0.1

        final = base + agreement_boost - fraud_penalty + evidence_boost - conv_penalty
        final = max(0.0, min(1.0, final))

        if final > 0.90:
            routing = "auto"
        elif final > 0.75:
            routing = "fast_review"
        elif final > 0.50:
            routing = "manual_review"
        else:
            routing = "evidence_request"

        breakdown = ConfidenceBreakdown(
            model_confidence=round(model_conf, 4),
            agreement_contribution=round(agreement_boost, 4),
            fraud_penalty=round(fraud_penalty, 4),
            evidence_boost=round(evidence_boost, 4),
            conversation_penalty=round(conv_penalty, 4),
        )

        return ConfidenceReport(
            final_confidence=round(final, 4),
            routing=routing,
            breakdown=breakdown,
        )
