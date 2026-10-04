"""Distributed tracing support for VerifyIQ."""

import functools
import time
import uuid


class Tracer:
    """Lightweight distributed tracer.

    Usage:
        tracer = Tracer()
        with tracer.span("operation_name"):
            ...
    """

    def __init__(self, trace_id: str | None = None):
        self.trace_id = trace_id or self.generate_trace_id()
        self._spans: list[dict] = []

    @staticmethod
    def generate_trace_id() -> str:
        return uuid.uuid4().hex[:16]

    def span(self, name: str):
        """Context manager that records a named span with timing."""
        return _Span(self, name)

    def get_trace_id(self) -> str:
        return self.trace_id

    def get_spans(self) -> list[dict]:
        return list(self._spans)

    def reset(self):
        self._spans.clear()


class _Span:
    def __init__(self, tracer: Tracer, name: str):
        self._tracer = tracer
        self._name = name
        self._start: float = 0.0

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (time.time() - self._start) * 1000
        self._tracer._spans.append({
            "name": self._name,
            "trace_id": self._tracer.trace_id,
            "duration_ms": round(elapsed, 3),
        })


def trace(func):
    """Decorator that wraps a function with timing and trace_id.

    The decorated function receives a 'trace_id' keyword argument
    (if not already provided) and logs timing to the global tracer.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if "trace_id" not in kwargs:
            kwargs["trace_id"] = Tracer.generate_trace_id()
        return func(*args, **kwargs)

    return wrapper
