"""VerifyIQ V1 — Deterministic claim verification pipeline.

This module wraps the original competition V1 pipeline (code/).
No V1 files are modified — all imports reference the canonical location.
"""

import sys as _sys
from pathlib import Path as _Path

_CODE_DIR = str(_Path(__file__).resolve().parent.parent.parent / "code")
if _CODE_DIR not in _sys.path:
    _sys.path.insert(0, _CODE_DIR)

from config import Config
from rule_engine import RuleEngine
from severity_engine import SeverityEngine
from evidence_checker import EvidenceChecker
from claim_parser import ClaimParser
from risk_analyzer import RiskAnalyzer
from output_validator import OutputValidator
from decision_agent import DecisionAgent
from image_validator import validate_images, any_valid_images, all_images_valid
from claim_processor import ClaimProcessor

__all__ = [
    "Config",
    "RuleEngine",
    "SeverityEngine",
    "EvidenceChecker",
    "ClaimParser",
    "RiskAnalyzer",
    "OutputValidator",
    "DecisionAgent",
    "validate_images",
    "any_valid_images",
    "all_images_valid",
    "ClaimProcessor",
]
