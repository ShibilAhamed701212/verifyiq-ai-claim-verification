import re
from code.v2.models.conversation import ConversationAnomaly, ConversationReport


class ConversationAnalyzer:
    """Detects contradictions, negation, retractions, uncertainty, sarcasm, changing claims."""

    NEGATION_WORDS = {"no", "not", "never", "don't", "doesn't", "didn't", "won't", "can't", "couldn't", "shouldn't", "isn't", "aren't", "wasn't", "weren't", "haven't", "hasn't", "hadn't"}
    UNCERTAINTY_WORDS = {"maybe", "perhaps", "possibly", "probably", "might", "could be", "not sure", "i think", "i believe", "seems like", "looks like", "approximately", "roughly", "about"}
    RETRACTION_PATTERNS = [
        r"actually.*(?:no|not|never|changed my mind)",
        r"on second thought",
        r"scratch that",
        r"ignore that",
        r"upon (?:further|closer) (?:inspection|review|examination)",
        r"take that back",
        r"reconsider",
        r"correction:?",
        r"^(?:sorry|my bad|my mistake)",
        r"let me (?:rephrase|correct|clarify)",
        r"i (?:spoke|said) too soon",
    ]
    SARASM_INDICATORS = {
        "great", "awesome", "fantastic", "wonderful", "brilliant", "perfect",
        "amazing", "incredible", "excellent", "love it", "just great",
    }

    def analyze(self, claim_text: str) -> ConversationReport:
        report = ConversationReport()
        if not claim_text:
            return report

        text_lower = claim_text.lower()

        # Negation detection
        words = text_lower.split()
        negation_phrases = [w for w in words if w in self.NEGATION_WORDS]
        if negation_phrases:
            report.has_negation = True
            report.anomalies.append(ConversationAnomaly(
                anomaly_type="negation",
                description=f"Negation detected: {', '.join(negation_phrases[:3])}",
                severity="medium",
            ))

        # Uncertainty detection
        uncertainty_hits = [p for p in self.UNCERTAINTY_WORDS if p in text_lower]
        if uncertainty_hits:
            report.has_uncertainty = True
            report.anomalies.append(ConversationAnomaly(
                anomaly_type="uncertainty",
                description=f"Uncertain language: {', '.join(uncertainty_hits[:3])}",
                severity="medium",
            ))

        # Retraction detection
        for pattern in self.RETRACTION_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                report.has_retraction = True
                report.anomalies.append(ConversationAnomaly(
                    anomaly_type="claim_retraction",
                    description=f"Claim retracted: '{match.group()}'",
                    severity="high",
                    span=(match.start(), match.end()),
                ))
                break

        # Sarcasm detection
        sarasam_hits = [w for w in self.SARASM_INDICATORS if w in text_lower]
        if sarasam_hits:
            report.has_sarcasm = True
            report.anomalies.append(ConversationAnomaly(
                anomaly_type="sarcasm",
                description=f"Possible sarcasm: '{', '.join(sarasam_hits[:3])}'",
                severity="low",
            ))

        # Contradiction detection: look for "A but not A" patterns
        damage_claim_pattern = r"(dent|scratch|crack|shatter|break|tear|water|stain|crush)"
        claims_found = set(re.findall(damage_claim_pattern, text_lower))
        negated_claims = set()
        for claim in claims_found:
            neg_pattern = rf"(no |not |never |didn't |isn't |wasn't ){claim}"
            if re.search(neg_pattern, text_lower):
                negated_claims.add(claim)

        if claims_found and negated_claims and not (claims_found - negated_claims):
            report.has_contradictions = True
            report.anomalies.append(ConversationAnomaly(
                anomaly_type="conversation_conflict",
                description=f"Claimed {', '.join(claims_found)} then negated all",
                severity="high",
            ))

        # Changing claims: multiple different damage types mentioned
        if len(claims_found) > 1:
            report.has_changing_claims = True
            report.anomalies.append(ConversationAnomaly(
                anomaly_type="changing_claims",
                description=f"Multiple damage types: {', '.join(claims_found)}",
                severity="medium",
            ))

        # Build risk flags
        if report.has_retraction:
            report.risk_flags.append("claim_retraction")
        if report.has_contradictions:
            report.risk_flags.append("conversation_conflict")
        if report.has_uncertainty:
            report.risk_flags.append("uncertain_claim")
        if report.has_sarcasm:
            report.risk_flags.append("possible_sarcasm")

        return report
