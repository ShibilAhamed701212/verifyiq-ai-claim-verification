from dataclasses import dataclass, field


@dataclass
class ModelDisagreement:
    field: str
    values: dict[str, str]
    severity: str = "low"


@dataclass
class ConsensusReport:
    agreement_score: float
    confidence: float
    uncertainty: float
    conflicting_models: list[str] = field(default_factory=list)
    disagreements: list[ModelDisagreement] = field(default_factory=list)
    models_used: int = 0
    models_succeeded: int = 0
    unanimous: bool = False
