"""Tests for ConsensusEngine — Phase 2"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from verifyiq.v2.consensus.engine import ConsensusEngine
from verifyiq.v2.models.observation import ObservationReport, Observation, PerImageAssessment

class TestConsensusEngine:
    def setup_method(self):
        self.engine = ConsensusEngine()
    
    def test_empty_observations(self):
        report = ObservationReport(all_failed=True)
        result = self.engine.evaluate(report)
        assert result.agreement_score == 0.0
        assert result.confidence == 0.0
        assert result.uncertainty == 1.0
        assert result.unanimous is False
    
    def test_single_observation(self):
        obs = Observation(model_name="gemini", provider="gemini", success=True, assessments=[
            PerImageAssessment(image_path="img1.jpg", damage_type="dent", confidence=0.85),
        ])
        report = ObservationReport(observations=[obs], all_failed=False)
        result = self.engine.evaluate(report)
        assert result.unanimous is True
        assert result.agreement_score == 1.0
        assert result.confidence == 0.85
    
    def test_unanimous_agreement(self):
        obs1 = Observation(model_name="gemini", provider="gemini", success=True, assessments=[
            PerImageAssessment(image_path="img1.jpg", damage_type="dent", confidence=0.85),
        ])
        obs2 = Observation(model_name="qwen", provider="openrouter", success=True, assessments=[
            PerImageAssessment(image_path="img1.jpg", damage_type="dent", confidence=0.80),
        ])
        report = ObservationReport(observations=[obs1, obs2], all_failed=False)
        result = self.engine.evaluate(report)
        assert result.unanimous is True
        assert result.agreement_score == 1.0
    
    def test_disagreement(self):
        obs1 = Observation(model_name="gemini", provider="gemini", success=True, assessments=[
            PerImageAssessment(image_path="img1.jpg", damage_type="dent", confidence=0.85),
        ])
        obs2 = Observation(model_name="qwen", provider="openrouter", success=True, assessments=[
            PerImageAssessment(image_path="img1.jpg", damage_type="scratch", confidence=0.80),
        ])
        report = ObservationReport(observations=[obs1, obs2], all_failed=False)
        result = self.engine.evaluate(report)
        assert result.unanimous is False
        assert result.agreement_score < 1.0
        assert len(result.disagreements) > 0
    
    def test_all_models_failed(self):
        obs1 = Observation(model_name="gemini", provider="gemini", success=False, error="timeout")
        obs2 = Observation(model_name="qwen", provider="openrouter", success=False, error="no key")
        report = ObservationReport(observations=[obs1, obs2], all_failed=True)
        result = self.engine.evaluate(report)
        assert result.models_succeeded == 0
        assert result.confidence == 0.0
