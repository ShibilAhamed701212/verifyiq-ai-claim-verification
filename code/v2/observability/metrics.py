import threading
import time
from dataclasses import dataclass, field


@dataclass
class ModuleTiming:
    module: str
    latency_ms: float
    success: bool
    error: str | None = None

@dataclass
class PipelineMetrics:
    total_latency_ms: float = 0.0
    module_timings: list[ModuleTiming] = field(default_factory=list)
    model_failures: list[str] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
    fraud_detections: int = 0
    routing: str | None = None

class MetricsCollector:
    def __init__(self):
        self._lock = threading.Lock()
        self._timings: list[ModuleTiming] = []
        self._start_time: float | None = None
        self._fraud_detections: int = 0
        self._request_id: str | None = None
        self._request_counter: int = 0
        self._failure_counter: int = 0
        self._latencies: list[float] = []

    @property
    def request_id(self) -> str | None:
        return self._request_id

    @request_id.setter
    def request_id(self, value: str | None):
        self._request_id = value

    def start(self):
        with self._lock:
            self._start_time = time.time()

    def record(self, module: str, latency_ms: float, success: bool = True, error: str | None = None):
        with self._lock:
            self._timings.append(ModuleTiming(module, latency_ms, success, error))

    def get_metrics(self) -> PipelineMetrics:
        with self._lock:
            total = sum(t.latency_ms for t in self._timings)
            failures = [f"{t.module}: {t.error}" for t in self._timings if not t.success and t.error]
            return PipelineMetrics(
                total_latency_ms=total,
                module_timings=list(self._timings),
                model_failures=failures,
                fraud_detections=self._fraud_detections,
            )

    def record_fraud(self, count: int):
        with self._lock:
            self._fraud_detections += count

    def reset(self):
        with self._lock:
            self._timings.clear()
            self._start_time = None
            self._fraud_detections = 0
            self._request_id = None
            self._request_counter = 0
            self._failure_counter = 0
            self._latencies.clear()

    def snapshot(self) -> dict:
        """Return a snapshot of all metrics for Prometheus-style endpoints."""
        with self._lock:
            latencies = list(self._latencies)
            n = len(latencies)
            if n > 0:
                sorted_lats = sorted(latencies)
                avg = sum(sorted_lats) / n
                p50 = sorted_lats[max(0, int(n * 0.50))]
                p95 = sorted_lats[max(0, int(n * 0.95))]
                p99 = sorted_lats[max(0, int(n * 0.99))]
            else:
                avg = p50 = p95 = p99 = 0.0

            # Build module timing summary
            module_stats = {}
            for t in self._timings:
                if t.module not in module_stats:
                    module_stats[t.module] = {"calls": 0, "total_ms": 0.0, "failures": 0}
                module_stats[t.module]["calls"] += 1
                module_stats[t.module]["total_ms"] += t.latency_ms
                if not t.success:
                    module_stats[t.module]["failures"] += 1

            return {
                "total_requests": self._request_counter,
                "total_failures": self._failure_counter,
                "fraud_detections": self._fraud_detections,
                "latency_ms": {
                    "min": min(latencies) if latencies else 0.0,
                    "max": max(latencies) if latencies else 0.0,
                    "avg": round(avg, 2),
                    "p50": round(p50, 2),
                    "p95": round(p95, 2),
                    "p99": round(p99, 2),
                    "count": n,
                },
                "modules": module_stats,
            }

# Global singleton for convenience
_global_collector = MetricsCollector()

def get_collector() -> MetricsCollector:
    return _global_collector
