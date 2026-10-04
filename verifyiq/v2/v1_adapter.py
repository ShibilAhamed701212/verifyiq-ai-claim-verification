"""Adapters that call V1 components as pure functions.

V1 is frozen. These adapters are the ONLY bridge between V2 and V1.
No V1 file may be imported, modified, or monkey-patched by V2.
"""

from pathlib import Path
from typing import Optional

from config import Config
from rule_engine import RuleEngine
from severity_engine import SeverityEngine
from evidence_checker import EvidenceChecker
from claim_parser import ClaimParser


class V1RuleAdapter:
    """Calls V1 RuleEngine as a pure function."""

    def __init__(self):
        self._engine = RuleEngine()

    def evaluate(self, claim_data: dict) -> dict:
        parser_result = {
            "claimed_damage_type": claim_data.get("damage_type", "unknown"),
            "claimed_object_part": claim_data.get("object_part", "unknown"),
        }
        vision_result = {
            "damage_visible": claim_data.get("damage_visible", False),
            "damage_type": claim_data.get("visible_damage_type") or claim_data.get("damage_type", "unknown"),
            "object_part": claim_data.get("visible_object_part") or claim_data.get("object_part", "unknown"),
            "confidence": claim_data.get("confidence", 0.0),
        }
        evidence_result = {
            "evidence_standard_met": claim_data.get("evidence_standard_met", False),
            "reason": claim_data.get("reason", ""),
        }
        return self._engine.evaluate(parser_result, vision_result, evidence_result)


class V1SeverityAdapter:
    """Calls V1 SeverityEngine as a pure function."""

    def __init__(self):
        self._engine = SeverityEngine()

    def evaluate(self, issue_type: str, claim_object: str, claim_text: str) -> str:
        return self._engine.determine(issue_type, claim_text, claim_object)


class V1EvidenceAdapter:
    """Calls V1 EvidenceChecker as a pure function."""

    def __init__(self, csv_path: Optional[Path] = None):
        self._checker = EvidenceChecker(csv_path or Config().evidence_reqs_path)

    def check(self, vision_result: dict, evidence_requirements: list[dict],
              claim_object: str, issue_type: str) -> dict:
        parser_result = {
            "claimed_damage_type": issue_type,
            "claimed_object_part": "unknown",
        }
        total = len(vision_result.get("per_image_assessments", []))
        return self._checker.evaluate(claim_object, parser_result, vision_result, total)


class V1ParserAdapter:
    """Calls V1 ClaimParser as a pure function."""

    def __init__(self, config: Optional[Config] = None):
        self._parser = ClaimParser(config or Config())

    def parse(self, claim_text: str, claim_object: str) -> dict:
        return self._parser.parse(claim_text, claim_object)


class V1RiskAdapter:
    """Calls V1 RiskAnalyzer as a pure function.

    Reproduces V1 risk flag behavior that V2's fraud+conversation layers miss.
    This is the ONLY bridge to V1's RiskAnalyzer — no V1 files are modified.
    """

    # V2 flags with direct V1 equivalents
    FLAG_ALIASES = {
        "object_part_mismatch": "wrong_object_part",
    }

    # V1 flags that are also valid V2 flags (shared namespace)
    EQUIVALENT_FLAGS = {
        "claim_mismatch": "claim_mismatch",
        "damage_not_visible": "damage_not_visible",
        "manual_review_required": "manual_review_required",
        "blurry_image": "blurry_image",
        "cropped_or_obstructed": "cropped_or_obstructed",
        "low_light_or_glare": "low_light_or_glare",
        "wrong_angle": "wrong_angle",
        "wrong_object": "wrong_object",
        "wrong_object_part": "wrong_object_part",
        "user_history_risk": "user_history_risk",
        "possible_manipulation": "possible_manipulation",
        "non_original_image": "non_original_image",
        "text_instruction_present": "text_instruction_present",
    }

    def __init__(self, config: Optional[Config] = None):
        from risk_analyzer import RiskAnalyzer
        self._analyzer = RiskAnalyzer(config or Config())

    def normalize(self, v2_flags: list[str], v1_flags: list[str]) -> tuple[list[str], list[str]]:
        """Normalize flags from both systems.

        Args:
            v2_flags: flags from V2 pipeline (fraud + conversation + rule)
            v1_flags: flags from V1 RiskAnalyzer

        Returns:
            (merged_unique, v1_compatible)
            merged_unique: all flags with aliases resolved, deduplicated, sorted
            v1_compatible: flags that match V1's output namespace (for exact-match comparison)
        """
        resolved = set()
        for flag in v2_flags + v1_flags:
            resolved.add(self.FLAG_ALIASES.get(flag, flag))
        for flag in v1_flags:
            resolved.add(flag)

        merged = sorted(resolved) if resolved else ["none"]
        v1_compat = sorted(r for r in resolved if r in self.EQUIVALENT_FLAGS.values() or r in self.FLAG_ALIASES.values())
        v1_compat = v1_compat if v1_compat else ["none"]
        return merged, v1_compat

    def analyze(
        self,
        image_analysis: dict,
        user_history: Optional[dict],
        claim_object: str,
        user_claim: str,
        evidence_result: Optional[dict] = None,
        rule_result: Optional[dict] = None,
        image_paths: Optional[list] = None,
    ) -> list[str]:
        """Call V1 RiskAnalyzer with the same interface.

        Returns sorted list of V1-compatible risk flags (or ["none"] if empty).
        Internal flags (evidence_insufficient, low_confidence, object_part_mismatch)
        are already filtered by V1 RiskAnalyzer.
        """
        return self._analyzer.analyze(
            image_analysis=image_analysis,
            user_history=user_history,
            claim_object=claim_object,
            user_claim=user_claim,
            evidence_result=evidence_result,
            rule_result=rule_result,
            image_paths=image_paths,
        )
