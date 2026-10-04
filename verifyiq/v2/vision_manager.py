"""Vision provider availability management with health tracking and circuit breaker.

States:
  AVAILABLE   — at least one provider is healthy
  DEGRADED    — primary provider failed, fallback succeeded
  UNAVAILABLE — no provider is reachable

On UNAVAILABLE, the system must refuse or degrade honestly.
"""

import threading
import time
from dataclasses import dataclass
from enum import Enum


class VisionState(Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class FallbackMode(Enum):
    PRODUCTION = "production"
    DEMO = "demo"
    RESEARCH = "research"


@dataclass
class ProviderHealth:
    name: str
    available: bool = False
    last_latency_ms: float = 0.0
    consecutive_failures: int = 0
    total_failures: int = 0
    total_calls: int = 0
    circuit_open: bool = False
    circuit_open_at: float | None = None
    circuit_cooldown_s: float = 60.0
    last_error: str | None = None
    quota_remaining: int | None = None

    @property
    def health_score(self) -> float:
        if self.circuit_open:
            return 0.0
        if not self.available:
            return 0.0
        if self.total_calls == 0:
            return 1.0
        return max(0.0, 1.0 - (self.consecutive_failures * 0.3))


class ProviderHealthTracker:
    """Tracks per-provider health metrics with circuit breaker."""

    PROVIDER_PRIORITY = ["gemini", "openrouter", "local"]

    def __init__(self):
        self._lock = threading.Lock()
        self._providers: dict[str, ProviderHealth] = {}
        for name in self.PROVIDER_PRIORITY:
            self._providers[name] = ProviderHealth(name=name)

    def register_available(self, name: str, quota: int | None = None):
        with self._lock:
            p = self._providers.get(name)
            if p:
                p.available = True
                p.quota_remaining = quota

    def record_success(self, name: str, latency_ms: float):
        with self._lock:
            p = self._providers.get(name)
            if p:
                p.last_latency_ms = latency_ms
                p.consecutive_failures = 0
                p.total_calls += 1
                if p.circuit_open:
                    p.circuit_open = False
                    p.circuit_open_at = None

    def record_failure(self, name: str, error: str):
        with self._lock:
            p = self._providers.get(name)
            if p:
                p.consecutive_failures += 1
                p.total_failures += 1
                p.total_calls += 1
                p.last_error = error
                if p.consecutive_failures >= 3:
                    p.circuit_open = True
                    p.circuit_open_at = time.time()

    def get_health(self, name: str) -> ProviderHealth | None:
        with self._lock:
            return self._providers.get(name)

    def get_all_health(self) -> list[ProviderHealth]:
        with self._lock:
            return list(self._providers.values())

    def is_available(self, name: str) -> bool:
        with self._lock:
            p = self._providers.get(name)
            if not p:
                return False
            if p.circuit_open:
                if p.circuit_open_at and (time.time() - p.circuit_open_at) > p.circuit_cooldown_s:
                    p.circuit_open = False
                    p.circuit_open_at = None
                    return p.available
                return False
            return p.available

    def best_available(self) -> str | None:
        for name in self.PROVIDER_PRIORITY:
            if self.is_available(name):
                return name
        return None

    def summary(self) -> dict:
        with self._lock:
            return {
                name: {
                    "available": p.available,
                    "healthy": not p.circuit_open and p.available,
                    "health_score": round(p.health_score, 2),
                    "consecutive_failures": p.consecutive_failures,
                    "total_failures": p.total_failures,
                    "last_latency_ms": p.last_latency_ms,
                    "circuit_open": p.circuit_open,
                    "last_error": p.last_error,
                    "quota_remaining": p.quota_remaining,
                }
                for name, p in self._providers.items()
            }


class VisionUnavailableError(RuntimeError):
    """Raised when vision analysis is unavailable and mode requires it."""


class VisionAvailabilityManager:
    """Manages VLM provider availability, fallback modes, and health tracking."""

    def __init__(self, mode: str = "production"):
        self._mode = FallbackMode(mode)
        self._state = VisionState.UNAVAILABLE
        self._tracker = ProviderHealthTracker()
        self._state_reason: str = "Initializing"
        self._last_state_change = time.time()

    @property
    def mode(self) -> FallbackMode:
        return self._mode

    @mode.setter
    def mode(self, value: str):
        self._mode = FallbackMode(value)

    @property
    def state(self) -> VisionState:
        return self._state

    @property
    def state_reason(self) -> str:
        return self._state_reason

    @property
    def tracker(self) -> ProviderHealthTracker:
        return self._tracker

    def register_providers(self, provider_list: list) -> None:
        """Register providers and test availability."""
        for provider in provider_list:
            name = provider.model_name
            available = provider.is_available()
            if available:
                self._tracker.register_available(name)
        self._recalculate_state("Provider registration complete")

    def check_provider(self, name: str) -> bool:
        """Check if a specific provider is usable right now."""
        if not self._tracker.is_available(name):
            return False
        return True

    def record_call(self, name: str, latency_ms: float, success: bool, error: str | None = None):
        if success:
            self._tracker.record_success(name, latency_ms)
        else:
            self._tracker.record_failure(name, error or "unknown")
        self._recalculate_state(f"Provider {name} {'succeeded' if success else 'failed'}")

    def _recalculate_state(self, reason: str):
        old = self._state
        if self._tracker.best_available() is not None:
            primary_healthy = self._tracker.is_available("gemini")
            self._state = VisionState.AVAILABLE if primary_healthy else VisionState.DEGRADED
        else:
            self._state = VisionState.UNAVAILABLE

        if old != self._state:
            self._last_state_change = time.time()
            self._state_reason = reason

    def ensure_vision(self, image_count: int) -> None:
        """Check if vision is available. Raises VisionUnavailableError if not.

        Only checks when images are actually provided — text-only claims
        (image_count == 0) always pass.
        """
        if image_count == 0:
            return
        if self._state == VisionState.UNAVAILABLE:
            if self._mode == FallbackMode.PRODUCTION:
                raise VisionUnavailableError(
                    "Image analysis temporarily unavailable — no vision provider is reachable. "
                    "Startup rejected in PRODUCTION mode. Set VERIFYIQ_MODE=demo or research to continue."
                )
        if self._state == VisionState.UNAVAILABLE and self._mode == FallbackMode.DEMO:
            return
        if self._state == VisionState.UNAVAILABLE and self._mode == FallbackMode.RESEARCH:
            return

    def get_vision_message(self, image_count: int) -> str:
        """Return an honest message about vision status."""
        if self._state == VisionState.UNAVAILABLE:
            if image_count > 0:
                return "Image analysis temporarily unavailable — vision provider unreachable. Claim processed based on text only."
            return "Image analysis temporarily unavailable."
        if self._state == VisionState.DEGRADED:
            return "Image analysis running in degraded mode (fallback provider)."
        return "Image analysis operational."

    def get_health_report(self) -> dict:
        return {
            "state": self._state.value,
            "mode": self._mode.value,
            "state_reason": self._state_reason,
            "best_provider": self._tracker.best_available(),
            "providers": self._tracker.summary(),
            "last_state_change": self._last_state_change,
        }
