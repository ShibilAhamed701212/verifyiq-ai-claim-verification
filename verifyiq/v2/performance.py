import time
from contextlib import contextmanager

_import_timings: dict[str, float] = {}

@contextmanager
def import_time(module_name: str):
    """Context manager that records how long a module import takes (in ms)."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        _import_timings[module_name] = _import_timings.get(module_name, 0) + elapsed


def get_startup_profile() -> dict:
    """Return dict with module import timings and summary."""
    return dict(sorted(_import_timings.items()))


def measure_claim_latency(pipeline, claim_text: str, image_paths: list[str] | None = None,
                           claim_object: str = "", user_id: str = "",
                           evidence_requirements: list[dict] | None = None) -> dict:
    """Run pipeline.process and return a timing breakdown in ms."""
    from verifyiq.v2.observability.metrics import get_collector
    get_collector().reset()
    start = time.perf_counter()
    pipeline.process(
        claim_text=claim_text,
        image_paths=image_paths or [],
        claim_object=claim_object,
        user_id=user_id,
        evidence_requirements=evidence_requirements,
    )
    total_ms = (time.perf_counter() - start) * 1000
    metrics = get_collector().get_metrics()
    module_timings = {t.module: t.latency_ms for t in metrics.module_timings}
    return {
        "total_ms": total_ms,
        "module_timings": module_timings,
        "fraud_detections": metrics.fraud_detections,
    }
