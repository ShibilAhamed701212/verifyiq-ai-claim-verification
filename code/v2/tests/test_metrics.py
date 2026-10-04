"""Tests for MetricsCollector — Phase 10"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from code.v2.observability.metrics import MetricsCollector


class TestMetricsCollector:
    def setup_method(self):
        self.metrics = MetricsCollector()

    def test_empty_metrics(self):
        m = self.metrics.get_metrics()
        assert m.total_latency_ms == 0.0
        assert len(m.module_timings) == 0

    def test_record_module(self):
        self.metrics.record("test_module", 100.0, success=True)
        m = self.metrics.get_metrics()
        assert len(m.module_timings) == 1
        assert m.module_timings[0].module == "test_module"
        assert m.module_timings[0].latency_ms == 100.0

    def test_record_failure(self):
        self.metrics.record("failing_module", 50.0, success=False, error="timeout")
        m = self.metrics.get_metrics()
        assert len(m.model_failures) == 1

    def test_reset(self):
        self.metrics.record("m1", 100.0)
        self.metrics.reset()
        m = self.metrics.get_metrics()
        assert len(m.module_timings) == 0
