from dataclasses import dataclass, field


@dataclass
class ImageFraudResult:
    duplicate_images: list[str] = field(default_factory=list)
    phash_matches: list[tuple[str, str, float]] = field(default_factory=list)
    is_screenshot: bool = False
    is_photo_of_photo: bool = False
    screenshot_confidence: float = 0.0
    fraud_score: float = 0.0
    flags: list[str] = field(default_factory=list)


@dataclass
class MetadataFraudResult:
    has_exif: bool = False
    editing_software: str | None = None
    has_editing: bool = False
    timestamp_mismatch: bool = False
    camera_mismatch: list[str] = field(default_factory=list)
    fraud_score: float = 0.0
    flags: list[str] = field(default_factory=list)


@dataclass
class BehavioralFraudResult:
    repeated_claims: int = 0
    image_reuse_count: int = 0
    escalation_pattern: bool = False
    claim_frequency_anomaly: bool = False
    fraud_score: float = 0.0
    flags: list[str] = field(default_factory=list)


@dataclass
class FraudReport:
    image_fraud: ImageFraudResult = field(default_factory=ImageFraudResult)
    metadata_fraud: MetadataFraudResult = field(default_factory=MetadataFraudResult)
    behavioral_fraud: BehavioralFraudResult = field(default_factory=BehavioralFraudResult)
    overall_fraud_score: float = 0.0
    high_risk: bool = False
    flags: list[str] = field(default_factory=list)
