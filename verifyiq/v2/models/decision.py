from dataclasses import dataclass, field


@dataclass
class DecisionTrace:
    why_supported: list[str] = field(default_factory=list)
    why_contradicted: list[str] = field(default_factory=list)
    evidence_trace: list[str] = field(default_factory=list)
    confidence_trace: list[str] = field(default_factory=list)
    fraud_trace: list[str] = field(default_factory=list)
    decision_trace: list[str] = field(default_factory=list)


@dataclass
class V2Decision:
    claim_status: str = "not_enough_information"
    issue_type: str = "unknown"
    object_part: str = "unknown"
    severity: str = "unknown"
    confidence: float = 0.0
    risk_flags: list[str] = field(default_factory=list)
    supporting_image_ids: list[str] = field(default_factory=list)
    valid_image: bool = False
    evidence_standard_met: bool = False
    justification: str = ""
    trace: DecisionTrace = field(default_factory=DecisionTrace)
