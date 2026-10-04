from verifyiq.v2.models.evidence import EvidenceRecommendation, EvidenceReport


class EvidenceRecommender:
    """Adds specific missing evidence recommendations when evidence_standard_met=False."""

    RECOMMENDATIONS = {
        "no_clear_image": EvidenceRecommendation(
            missing_type="clear_image",
            description="A clear, well-lit image showing the damaged area",
            priority="high",
        ),
        "wrong_angle": EvidenceRecommendation(
            missing_type="second_angle",
            description="Image from a different angle to confirm damage extent",
            priority="medium",
        ),
        "missing_close_up": EvidenceRecommendation(
            missing_type="close_up",
            description="A close-up image of the specific damage area",
            priority="high",
        ),
        "missing_side": EvidenceRecommendation(
            missing_type="side_view",
            description="Side or profile view showing depth of damage",
            priority="medium",
        ),
        "missing_interior": EvidenceRecommendation(
            missing_type="interior_view",
            description="Interior image if damage may affect internal components",
            priority="low",
        ),
        "low_confidence": EvidenceRecommendation(
            missing_type="additional_angle",
            description="Additional image from a different angle to increase confidence",
            priority="medium",
        ),
        "blurry": EvidenceRecommendation(
            missing_type="sharp_image",
            description="A sharp, in-focus image replacing the blurry one",
            priority="high",
        ),
        "bad_lighting": EvidenceRecommendation(
            missing_type="better_lighting",
            description="Image with adequate lighting to reveal damage clearly",
            priority="medium",
        ),
    }

    def recommend(self, evidence_report: EvidenceReport) -> EvidenceReport:
        if evidence_report.evidence_standard_met:
            return evidence_report

        reason = (evidence_report.reason or "").lower()

        if "clear" in reason or "quality" in reason:
            evidence_report.recommendations.append(self.RECOMMENDATIONS["no_clear_image"])
        if "angle" in reason or "perspective" in reason:
            evidence_report.recommendations.append(self.RECOMMENDATIONS["wrong_angle"])
        if "close" in reason or "detail" in reason:
            evidence_report.recommendations.append(self.RECOMMENDATIONS["missing_close_up"])
        if "side" in reason or "profile" in reason:
            evidence_report.recommendations.append(self.RECOMMENDATIONS["missing_side"])
        if "blur" in reason:
            evidence_report.recommendations.append(self.RECOMMENDATIONS["blurry"])
        if "light" in reason or "dark" in reason or "exposure" in reason:
            evidence_report.recommendations.append(self.RECOMMENDATIONS["bad_lighting"])

        # Default recommendation if nothing specific
        if not evidence_report.recommendations:
            evidence_report.recommendations.append(self.RECOMMENDATIONS["no_clear_image"])
            evidence_report.recommendations.append(self.RECOMMENDATIONS["missing_close_up"])

        return evidence_report
