"""VerifyIQ V2 — 10-layer pipeline orchestrator.

Pipeline:
  Observation → Consensus → Fraud → Evidence → Conversation →
  Confidence → V1 Rule Adapter → Critic → Decision → Output

V1 is frozen. V2 exists entirely in code/v2/. Vision provider
availability is managed by VisionAvailabilityManager to prevent
silent degradation.
"""

import os
import time
from code.config import Config
from code.v2.confidence.calibrator import ConfidenceCalibrator
from code.v2.consensus import ConsensusEngine
from code.v2.conversation.analyzer import ConversationAnalyzer
from code.v2.critic.v2_critic import V2Critic
from code.v2.evidence.recommender import EvidenceRecommender
from code.v2.explainability.tracer import DecisionTracer
from code.v2.fraud import BehavioralFraudDetector, ImageFraudDetector, MetadataFraudDetector
from code.v2.models.confidence import ConfidenceReport
from code.v2.models.consensus import ConsensusReport
from code.v2.models.conversation import ConversationReport
from code.v2.models.decision import V2Decision
from code.v2.models.evidence import EvidenceReport
from code.v2.models.fraud import FraudReport
from code.v2.models.observation import ObservationReport
from code.v2.observability.metrics import get_collector
from code.v2.security.sanitizer import InputSanitizer
from code.v2.v1_adapter import V1EvidenceAdapter, V1ParserAdapter, V1RuleAdapter, V1SeverityAdapter
from code.v2.vision_manager import (
    VisionAvailabilityManager,
    VisionState,
)


class V2Pipeline:
    """Ten-layer claim verification pipeline.

    Each layer is independently testable. Failures at any layer produce
    degraded-but-valid output. No layer crashes the pipeline.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.metrics = get_collector()

        # Vision availability manager
        mode = os.environ.get("VERIFYIQ_MODE", "production")
        self.vision_manager = VisionAvailabilityManager(mode=mode)

        # Observation providers (lazy imports — only load what's configured)
        self.providers: list = []
        provider_configs = self.config.get("providers", {"gemini": {"model": "gemini-2.0-flash"}})
        if "gemini" in provider_configs:
            from code.v2.providers import GeminiProvider
            self.providers.append(GeminiProvider(
                provider_configs["gemini"].get("model", "gemini-2.0-flash"),
                provider_configs["gemini"],
            ))
        if "openrouter" in provider_configs:
            from code.v2.providers import OpenRouterProvider
            self.providers.append(OpenRouterProvider(
                provider_configs["openrouter"].get("model", "qwen/qwen2.5-vl-72b-instruct"),
                provider_configs["openrouter"],
            ))
        if "local" in provider_configs:
            from code.v2.providers import LocalVLMProvider
            self.providers.append(LocalVLMProvider(
                provider_configs["local"].get("model", "qwen2.5-vl-7b"),
                provider_configs["local"],
            ))

        # Register providers with vision manager
        self.vision_manager.register_providers(self.providers)

        # Core engines
        self.consensus_engine = ConsensusEngine()
        self.image_fraud = ImageFraudDetector()
        self.metadata_fraud = MetadataFraudDetector()
        self.behavioral_fraud = BehavioralFraudDetector()
        self.conversation_analyzer = ConversationAnalyzer()
        self.confidence_calibrator = ConfidenceCalibrator()
        self.evidence_recommender = EvidenceRecommender()
        self.critic = V2Critic()
        self.tracer = DecisionTracer()

        # V1 adapters
        self.rule_adapter = V1RuleAdapter()
        self.severity_adapter = V1SeverityAdapter()
        self.evidence_adapter = V1EvidenceAdapter()
        self.parser_adapter = V1ParserAdapter()

        # Security
        self.sanitizer = InputSanitizer()

    def process(self, claim_text: str, image_paths: list[str], claim_object: str,
                 user_id: str = "", evidence_requirements: list[dict] | None = None) -> V2Decision:
        self.metrics.start()

        # Layer 0: Sanitize inputs
        claim_text = self.sanitizer.sanitize_claim_text(claim_text)
        image_paths = [p for p in image_paths if self.sanitizer.sanitize_image_path(p, ".")]
        claim_text = self.sanitizer.sanitize_csv_field(claim_text)

        # Check vision availability (raises if production mode + unavailable)
        self.vision_manager.ensure_vision(len(image_paths))

        # Layer 1: Observation (multi-model)
        observation_report = self._run_observation(image_paths, claim_text, claim_object)

        # Layer 2: Consensus
        consensus_report = self._run_consensus(observation_report)

        # Layer 3: Fraud
        fraud_report = self._run_fraud(image_paths, user_id, claim_text)

        # Layer 4: Evidence
        evidence_report = self._run_evidence(observation_report, claim_text, claim_object, evidence_requirements, image_paths)

        # Layer 5: Conversation
        conversation_report = self._run_conversation(claim_text)

        # Layer 6: Confidence
        confidence_report = self._run_confidence(consensus_report, fraud_report, evidence_report, conversation_report)

        # Layer 7: V1 Rule Adapter
        decision = self._run_v1_rule(observation_report, claim_text, claim_object, evidence_report)

        # Layer 8: Critic
        critic_result, critic_issues = self.critic.review(decision, fraud_report, conversation_report, consensus_report)

        # Layer 9: Decision Assembly
        decision = self._assemble_decision(decision, consensus_report, fraud_report, conversation_report,
                                            evidence_report, confidence_report, critic_result, critic_issues)

        return decision

    def _run_observation(self, image_paths: list[str], claim_text: str, claim_object: str) -> ObservationReport:
        start = time.time()
        observations = []
        all_failed = True
        primary = None

        for provider in self.providers:
            if not provider.is_available():
                continue
            pstart = time.time()
            try:
                report = provider.analyze(image_paths, claim_text, claim_object)
                platency = (time.time() - pstart) * 1000
                observations.extend(report.observations)
                if not report.all_failed:
                    all_failed = False
                    if primary is None:
                        primary = provider.model_name
                    self.vision_manager.record_call(provider.model_name, platency, True)
                else:
                    self.vision_manager.record_call(provider.model_name, platency, False, "provider_returned_all_failed")
            except Exception as exc:
                platency = (time.time() - pstart) * 1000
                self.vision_manager.record_call(provider.model_name, platency, False, str(exc))

        elapsed = (time.time() - start) * 1000
        if all_failed and image_paths and self.vision_manager.state == VisionState.UNAVAILABLE:
            error = "vision_unavailable"
        else:
            error = "all_providers_failed" if all_failed else None
        self.metrics.record("observation", elapsed, success=not all_failed, error=error)
        return ObservationReport(observations=observations, all_failed=all_failed, primary_model=primary)

    def _run_consensus(self, observation_report: ObservationReport) -> ConsensusReport:
        start = time.time()
        result = self.consensus_engine.evaluate(observation_report)
        elapsed = (time.time() - start) * 1000
        self.metrics.record("consensus", elapsed)
        return result

    def _run_fraud(self, image_paths: list[str], user_id: str, claim_text: str) -> FraudReport:
        start = time.time()
        image_result = self.image_fraud.check(image_paths)
        metadata_result = self.metadata_fraud.check(image_paths)

        damage_type = ""
        try:
            from code.claim_parser import ClaimParser
            parser = ClaimParser(Config())
            parsed = parser.parse(claim_text, "")
            damage_type = parsed.get("claimed_damage_type", "")
        except Exception:
            pass

        behavioral_result = self.behavioral_fraud.check(user_id, damage_type, image_paths)

        overall = max(image_result.fraud_score, metadata_result.fraud_score, behavioral_result.fraud_score)
        all_flags = list(set(image_result.flags + metadata_result.flags + behavioral_result.flags))

        elapsed = (time.time() - start) * 1000
        self.metrics.record("fraud", elapsed)
        if all_flags:
            self.metrics.record_fraud(len(all_flags))

        return FraudReport(
            image_fraud=image_result,
            metadata_fraud=metadata_result,
            behavioral_fraud=behavioral_result,
            overall_fraud_score=overall,
            high_risk=overall > 0.5,
            flags=all_flags,
        )

    def _run_evidence(self, observation_report: ObservationReport, claim_text: str,
                       claim_object: str, evidence_requirements: list[dict] | None = None,
                       image_paths: list[str] | None = None) -> EvidenceReport:
        start = time.time()
        if not evidence_requirements:
            evidence_requirements = []

        image_paths = image_paths or []
        vision_data = {"per_image_assessments": []}
        for obs in observation_report.observations:
            for a in obs.assessments:
                vision_data["per_image_assessments"].append({
                    "image_path": a.image_path,
                    "damage_visible": a.damage_visible,
                    "damage_type": a.damage_type,
                    "object_part": a.object_part,
                    "confidence": a.confidence,
                    "is_clear": a.is_clear,
                    "angle_sufficient": a.angle_sufficient,
                    "lighting_adequate": a.lighting_adequate,
                })

        from code.claim_parser import ClaimParser
        parser = ClaimParser(Config())
        parsed = parser.parse(claim_text, claim_object)
        issue_type = parsed.get("claimed_damage_type", "unknown")

        v1_result = self.evidence_adapter.check(vision_data, evidence_requirements, claim_object, issue_type)
        valid_image = bool(v1_result.get("valid_image", False))

        # Fix misleading V1 message when VLM is unavailable but images were provided
        reason = v1_result.get("reason", "unknown")
        if len(image_paths) > 0 and self.vision_manager.state == VisionState.UNAVAILABLE:
            if "no images" in reason.lower():
                reason = self.vision_manager.get_vision_message(len(image_paths))

        evidence_report = EvidenceReport(
            evidence_standard_met=v1_result.get("evidence_standard_met", False),
            reason=reason,
            relevant_image_count=len(vision_data["per_image_assessments"]),
            valid_image=valid_image,
        )
        evidence_report = self.evidence_recommender.recommend(evidence_report)

        elapsed = (time.time() - start) * 1000
        self.metrics.record("evidence", elapsed)
        return evidence_report

    def _run_conversation(self, claim_text: str) -> ConversationReport:
        start = time.time()
        result = self.conversation_analyzer.analyze(claim_text)
        elapsed = (time.time() - start) * 1000
        self.metrics.record("conversation", elapsed)
        return result

    def _run_confidence(self, consensus: ConsensusReport, fraud: FraudReport,
                         evidence: EvidenceReport, conversation: ConversationReport) -> ConfidenceReport:
        start = time.time()
        result = self.confidence_calibrator.calibrate(consensus, fraud, evidence, conversation)
        elapsed = (time.time() - start) * 1000
        self.metrics.record("confidence", elapsed)
        return result

    def _run_v1_rule(self, observation_report: ObservationReport, claim_text: str,
                      claim_object: str, evidence_report: EvidenceReport) -> V2Decision:
        start = time.time()
        try:
            from code.claim_parser import ClaimParser
            parser = ClaimParser(Config())
            parsed = parser.parse(claim_text, claim_object)
            damage_type = parsed.get("claimed_damage_type", "unknown")
            object_part = parsed.get("claimed_object_part", "unknown")
        except Exception:
            damage_type = "unknown"
            object_part = "unknown"

        damage_visible = False
        visible_damage_type = "unknown"
        visible_object_part = "unknown"
        obs_confidence = 0.0
        for obs in observation_report.observations:
            if obs.success:
                for a in obs.assessments:
                    if a.damage_visible:
                        damage_visible = True
                        visible_damage_type = a.damage_type
                        visible_object_part = a.object_part
                    obs_confidence = max(obs_confidence, a.confidence)

        v1_result = self.rule_adapter.evaluate({
            "damage_type": damage_type,
            "object_part": object_part,
            "evidence_standard_met": evidence_report.evidence_standard_met,
            "damage_visible": damage_visible,
            "visible_damage_type": visible_damage_type,
            "visible_object_part": visible_object_part,
            "confidence": obs_confidence,
        })

        severity = self.severity_adapter.evaluate(visible_damage_type, claim_object, claim_text)

        decision = V2Decision(
            claim_status=v1_result.get("claim_status", "not_enough_information"),
            issue_type=visible_damage_type,
            object_part=visible_object_part,
            severity=severity,
            confidence=v1_result.get("confidence", 0.0),
            evidence_standard_met=evidence_report.evidence_standard_met,
            valid_image=evidence_report.valid_image,
            risk_flags=v1_result.get("risk_flags", []),
        )

        elapsed = (time.time() - start) * 1000
        self.metrics.record("v1_rule_adapter", elapsed)
        return decision

    def _assemble_decision(self, decision: V2Decision, consensus: ConsensusReport,
                            fraud: FraudReport, conversation: ConversationReport,
                            evidence: EvidenceReport, confidence: ConfidenceReport,
                            critic_result: str, critic_issues: list[str]) -> V2Decision:
        decision.confidence = confidence.final_confidence
        decision.risk_flags = list(set(decision.risk_flags + fraud.flags + conversation.risk_flags))

        if fraud.high_risk and "manual_review_required" not in decision.risk_flags:
            decision.risk_flags.append("manual_review_required")
        if consensus.models_succeeded == 0 and "manual_review_required" not in decision.risk_flags:
            decision.risk_flags.append("manual_review_required")

        # Add vision_unavailable flag if VLM is unreachable and images were provided
        if self.vision_manager.state == VisionState.UNAVAILABLE:
            if "vision_unavailable" not in decision.risk_flags:
                decision.risk_flags.append("vision_unavailable")
        elif self.vision_manager.state == VisionState.DEGRADED:
            if "vision_degraded" not in decision.risk_flags:
                decision.risk_flags.append("vision_degraded")

        decision = self.tracer.trace(decision, consensus, fraud, conversation, evidence, confidence)

        if critic_result == "REVIEW_REQUIRED":
            if "manual_review_required" not in decision.risk_flags:
                decision.risk_flags.append("manual_review_required")
            decision.justification += f" | Critic: {'; '.join(critic_issues)}"

        return decision
