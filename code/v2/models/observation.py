from dataclasses import dataclass, field


@dataclass
class PerImageAssessment:
    image_path: str
    damage_visible: bool = False
    damage_type: str = "unknown"
    object_part: str = "unknown"
    confidence: float = 0.0
    is_clear: bool = False
    angle_sufficient: bool = False
    lighting_adequate: bool = False
    issues: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class Observation:
    model_name: str
    provider: str
    success: bool
    assessments: list[PerImageAssessment] = field(default_factory=list)
    raw_response: str | None = None
    error: str | None = None
    latency_ms: float = 0.0
    degraded: bool = False


@dataclass
class ObservationReport:
    observations: list[Observation] = field(default_factory=list)
    all_failed: bool = True
    primary_model: str | None = None
