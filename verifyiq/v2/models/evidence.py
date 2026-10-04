from dataclasses import dataclass, field


@dataclass
class EvidenceRecommendation:
    missing_type: str
    description: str
    priority: str = "medium"


@dataclass
class EvidenceReport:
    evidence_standard_met: bool = False
    reason: str | None = None
    relevant_image_count: int = 0
    valid_image: bool = False
    recommendations: list[EvidenceRecommendation] = field(default_factory=list)
