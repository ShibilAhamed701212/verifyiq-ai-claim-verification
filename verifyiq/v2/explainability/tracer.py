from verifyiq.v2.models.confidence import ConfidenceReport
from verifyiq.v2.models.consensus import ConsensusReport
from verifyiq.v2.models.conversation import ConversationReport
from verifyiq.v2.models.decision import DecisionTrace, V2Decision
from verifyiq.v2.models.evidence import EvidenceReport
from verifyiq.v2.models.fraud import FraudReport


class DecisionTracer:
    """Generates structured explainability traces for every decision."""

    def trace(self, decision: V2Decision, consensus: ConsensusReport,
               fraud: FraudReport, conversation: ConversationReport,
               evidence: EvidenceReport, confidence: ConfidenceReport) -> V2Decision:
        trace = DecisionTrace()

        # Why supported
        if decision.claim_status == "supported":
            trace.why_supported.append(f"Damage type '{decision.issue_type}' observed in images")
            trace.why_supported.append(f"Object part '{decision.object_part}' matches claimed part")
            if not fraud.high_risk:
                trace.why_supported.append("No significant fraud signals detected")
            if consensus.agreement_score > 0.7:
                trace.why_supported.append(f"Model agreement: {consensus.agreement_score:.0%}")
        else:
            trace.why_contradicted.append(f"Claim status: {decision.claim_status}")
            if not evidence.evidence_standard_met:
                trace.why_contradicted.append(f"Evidence insufficient: {evidence.reason or 'unknown reason'}")
            if fraud.high_risk:
                trace.why_contradicted.append(f"Fraud risk: {fraud.overall_fraud_score:.0%}")
            if conversation.has_retraction:
                trace.why_contradicted.append("Claim was retracted in conversation")

        # Evidence trace
        trace.evidence_trace.append(f"Models consulted: {consensus.models_used}")
        trace.evidence_trace.append(f"Models succeeded: {consensus.models_succeeded}")
        trace.evidence_trace.append(f"Evidence standard met: {evidence.evidence_standard_met}")
        if evidence.recommendations:
            for rec in evidence.recommendations:
                trace.evidence_trace.append(f"Missing: {rec.description}")

        # Confidence trace
        trace.confidence_trace.append(f"Model confidence: {confidence.breakdown.model_confidence}")
        trace.confidence_trace.append(f"Agreement boost: {confidence.breakdown.agreement_contribution}")
        trace.confidence_trace.append(f"Fraud penalty: {confidence.breakdown.fraud_penalty}")
        trace.confidence_trace.append(f"Evidence adjustment: {confidence.breakdown.evidence_boost}")
        trace.confidence_trace.append(f"Routing: {confidence.routing}")

        # Fraud trace
        for flag in fraud.flags:
            trace.fraud_trace.append(f"Fraud flag: {flag}")
        if not fraud.flags:
            trace.fraud_trace.append("No fraud flags raised")

        # Decision trace
        trace.decision_trace.append(f"Final status: {decision.claim_status}")
        trace.decision_trace.append(f"Final confidence: {confidence.final_confidence}")
        trace.decision_trace.append(f"Routing: {confidence.routing}")

        # Build justification
        lines = []
        if trace.why_supported:
            lines.append("Supported because: " + "; ".join(trace.why_supported))
        if trace.why_contradicted:
            label = ("Contradicted because" if decision.claim_status == "contradicted"
                     else "Not supported because")
            lines.append(f"{label}: " + "; ".join(trace.why_contradicted))
        lines.append(f"Confidence: {confidence.final_confidence:.2f} ({confidence.routing})")
        if fraud.flags:
            lines.append(f"Fraud flags: {', '.join(fraud.flags)}")

        decision.trace = trace
        decision.justification = " | ".join(lines)
        return decision
