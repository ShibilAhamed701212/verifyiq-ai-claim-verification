"""
Configuration and constants for the evidence review system.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    """Central configuration for the system."""

    # --- Paths ---
    base_dir: Path = Path(__file__).parent.parent / "dataset"
    claims_path: Path = base_dir / "claims.csv"
    sample_claims_path: Path = base_dir / "sample_claims.csv"
    user_history_path: Path = base_dir / "user_history.csv"
    evidence_reqs_path: Path = base_dir / "evidence_requirements.csv"
    images_dir: Path = base_dir
    output_path: Path = Path(__file__).parent.parent / "output.csv"

    # --- Vision LLM Settings ---
    vision_model: str = "gemini-3.1-flash-lite-preview"
    api_key: str | None = None
    max_tokens: int = 800
    temperature: float = 0.0
    vision_api_timeout: int = 60

    # --- Processing ---
    max_images_per_claim: int = 5
    image_support_threshold: float = 0.5

    # --- Evaluation ---
    evaluation_samples_limit: int = -1

    ALLOWED_ISSUE_TYPES = {
        "dent", "scratch", "crack", "glass_shatter", "broken_part",
        "missing_part", "torn_packaging", "crushed_packaging",
        "water_damage", "stain", "none", "unknown"
    }

    ALLOWED_OBJECT_PARTS = {
        "car": {"front_bumper", "rear_bumper", "door", "hood", "windshield",
                "side_mirror", "headlight", "taillight", "fender",
                "quarter_panel", "body", "unknown"},
        "laptop": {"screen", "keyboard", "trackpad", "hinge", "lid",
                   "corner", "port", "base", "body", "unknown"},
        "package": {"box", "package_corner", "package_side", "seal",
                    "label", "contents", "item", "unknown"},
    }

    ALLOWED_CLAIM_STATUS = {"supported", "contradicted", "not_enough_information"}
    ALLOWED_SEVERITY = {"none", "low", "medium", "high", "unknown"}
    ALLOWED_RISK_FLAGS = {
        "blurry_image", "cropped_or_obstructed", "low_light_or_glare",
        "wrong_angle", "wrong_object", "wrong_object_part",
        "damage_not_visible", "claim_mismatch", "possible_manipulation",
        "non_original_image", "text_instruction_present",
        "user_history_risk", "manual_review_required",
        "none"
    }
