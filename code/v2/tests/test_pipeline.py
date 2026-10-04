"""Integration tests for V2Pipeline — full 10-layer pipeline."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from code.v2.observability.metrics import get_collector
from code.v2.pipeline import V2Pipeline


class TestV2Pipeline:
    def test_pipeline_initialization(self):
        pipeline = V2Pipeline()
        assert pipeline is not None
        assert len(pipeline.providers) > 0

    def test_pipeline_process_no_api(self):
        pipeline = V2Pipeline()
        result = pipeline.process(
            claim_text="There is a dent on the rear bumper",
            image_paths=[],
            claim_object="car",
            user_id="test_user",
        )
        assert result.claim_status in ("supported", "contradicted", "not_enough_information")
        assert result.justification is not None

    def test_pipeline_empty_inputs(self):
        pipeline = V2Pipeline()
        result = pipeline.process("", [], "")
        assert result is not None

    def test_pipeline_metrics_collected(self):
        get_collector().reset()
        pipeline = V2Pipeline()
        pipeline.process("test", [], "car")
        metrics = get_collector().get_metrics()
        assert len(metrics.module_timings) > 0

    def test_pipeline_returns_v2_decision(self):
        pipeline = V2Pipeline()
        result = pipeline.process("test dent", [], "car", "user1")
        assert hasattr(result, "claim_status")
        assert hasattr(result, "trace")
        assert hasattr(result, "risk_flags")
