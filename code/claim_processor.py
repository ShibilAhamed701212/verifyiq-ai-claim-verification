"""
Claim processing orchestrator.

Flow:
Vision Analysis -> Evidence Checker -> Rule Engine -> Risk Analyzer ->
Decision Agent -> Output Validator.
"""

import logging
from typing import Any

from claim_parser import ClaimParser
from config import Config
from decision_agent import DecisionAgent
from evidence_checker import EvidenceChecker
from image_preprocessor import normalize_images
from image_validator import all_images_valid, any_valid_images, validate_images
from output_validator import OutputValidator
from risk_analyzer import RiskAnalyzer
from rule_engine import RuleEngine
from severity_engine import SeverityEngine
from utils import extract_claim_text, parse_image_paths, safe_csv_read
from vision_analyzer import analyze_images

logger = logging.getLogger("evidence_review.processor")


class ClaimProcessor:
    """Runs one claim through the production decision pipeline."""

    def __init__(self, config: Config):
        self.config = config
        self.claim_parser = ClaimParser(config)
        self.evidence_checker = EvidenceChecker(config.evidence_reqs_path)
        self.rule_engine = RuleEngine()
        self.risk_analyzer = RiskAnalyzer(config)
        self.output_validator = OutputValidator(config)
        self.severity_engine = SeverityEngine()
        self.decision_agent = DecisionAgent(self.output_validator, self.severity_engine)
        self.user_history_cache: dict[str, dict[str, Any]] = {}
        self._load_user_history()

    def _load_user_history(self) -> None:
        if not self.config.user_history_path.exists():
            logger.warning(f"User history file not found: {self.config.user_history_path}")
            return

        for row in safe_csv_read(self.config.user_history_path):
            user_id = row.get("user_id", "").strip()
            if user_id:
                self.user_history_cache[user_id] = row
        logger.info(f"Loaded history for {len(self.user_history_cache)} users")

    def _get_user_history(self, user_id: str) -> dict[str, Any] | None:
        return self.user_history_cache.get(user_id)

    def process_claim(self, claim_row: dict[str, str]) -> dict[str, str]:
        user_id = claim_row.get("user_id", "").strip()
        image_paths_str = claim_row.get("image_paths", "").strip()
        user_claim = claim_row.get("user_claim", "").strip()
        claim_object = claim_row.get("claim_object", "").strip().lower()

        image_paths = parse_image_paths(image_paths_str, self.config.images_dir)

        try:
            image_paths = normalize_images(image_paths)
        except Exception as e:
            logger.warning(f"Image normalization failed for {user_id}: {e}")

        try:
            validation_results = validate_images(image_paths)
            if not any_valid_images(validation_results):
                logger.warning(f"No valid images for {user_id}")
            elif not all_images_valid(validation_results):
                invalid = [r["image_path"] for r in validation_results if not r["valid"]]
                logger.warning(f"Some images invalid for {user_id}: {invalid}")
        except Exception as e:
            logger.warning(f"Image validation failed for {user_id}: {e}")

        try:
            parser_result = self.claim_parser.parse(user_claim, claim_object)
        except Exception as e:
            logger.error(f"Claim parser failed for {user_id}: {e}")
            parser_result = {"claimed_damage_type": "unknown", "claimed_object_part": "unknown", "claim_text": user_claim}

        user_history = self._get_user_history(user_id)
        claim_text = extract_claim_text(user_claim) or user_claim

        try:
            vision_result = analyze_images(
                image_paths=image_paths,
                user_claim=claim_text,
                claim_object=claim_object,
                config=self.config,
            )
        except Exception as e:
            logger.error(f"Vision analysis failed for {user_id}: {e}")
            vision_result = self._empty_vision_result(f"Vision component error: {str(e)[:100]}")

        try:
            evidence_result = self.evidence_checker.evaluate(
                claim_object=claim_object,
                parser_result=parser_result,
                vision_result=vision_result,
                total_images=len(image_paths),
            )
        except Exception as e:
            logger.error(f"Evidence checker failed for {user_id}: {e}")
            evidence_result = {"evidence_standard_met": False, "evidence_standard_met_reason": f"Evidence evaluation error: {str(e)[:100]}", "reason": f"Evidence evaluation error: {str(e)[:100]}", "requirement_text": "", "valid_image": False}

        try:
            rule_result = self.rule_engine.evaluate(
                parser_result=parser_result,
                vision_result=vision_result,
                evidence_result=evidence_result,
            )
        except Exception as e:
            logger.error(f"Rule engine failed for {user_id}: {e}")
            rule_result = {"claim_status": "not_enough_information", "justification": f"Rule engine error: {str(e)[:100]}", "claimed_damage_type": parser_result.get("claimed_damage_type", "unknown"), "claimed_object_part": parser_result.get("claimed_object_part", "unknown"), "visible_damage_type": vision_result.get("damage_type", "unknown"), "visible_object_part": vision_result.get("object_part", "unknown"), "confidence": 0.0, "review_candidate": False, "mismatch_type": "evidence_insufficient", "risk_flags": []}

        try:
            risk_result = self.risk_analyzer.analyze(
                image_analysis=vision_result,
                user_history=user_history,
                claim_object=claim_object,
                user_claim=user_claim,
                evidence_result=evidence_result,
                rule_result=rule_result,
                image_paths=image_paths,
            )
        except Exception as e:
            logger.error(f"Risk analyzer failed for {user_id}: {e}")
            risk_result = ["manual_review_required"]

        try:
            return self.decision_agent.build_output_row(
                claim_row=claim_row,
                parser_result=parser_result,
                vision_result=vision_result,
                evidence_result=evidence_result,
                rule_result=rule_result,
                risk_result=risk_result,
            )
        except Exception as e:
            logger.error(f"Decision agent build failed for {user_id}: {e}", exc_info=True)
            return self.decision_agent.fallback_output(claim_row, str(e))

    def _fallback_output(self, claim_row: dict[str, str], error_message: str) -> dict[str, str]:
        return self.decision_agent.fallback_output(claim_row, error_message)

    @staticmethod
    def _empty_vision_result(reason: str) -> dict[str, Any]:
        return {
            "damage_visible": False, "damage_type": "unknown", "object_part": "unknown",
            "image_quality": "unknown", "supporting_images": [], "confidence": 0.0,
            "notes": reason, "conflicting_images": False,
            "per_image_assessments": [], "image_assessments": [],
            "overall_issue_type": "unknown", "overall_object_part": "unknown",
            "supporting_image_ids": [],
        }
