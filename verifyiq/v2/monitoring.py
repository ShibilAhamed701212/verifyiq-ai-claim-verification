"""Health checks and dependency monitoring for VerifyIQ."""

import os
import threading
import time
from collections.abc import Callable

# ── Health Checker ─────────────────────────────────────────────────────────

class HealthChecker:
    """Runs on-demand health checks for VerifyIQ dependencies."""

    @staticmethod
    def check_vlm_providers() -> dict:
        """Check that VLM provider API keys are present in environment."""
        results = []
        providers = {
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        for name, env_var in providers.items():
            if os.environ.get(env_var):
                results.append({"provider": name, "status": "ok"})
            else:
                results.append({"provider": name, "status": "missing", "detail": f"{env_var} not set"})
        return {
            "name": "vlm_providers",
            "status": "ok" if any(r["status"] == "ok" for r in results) else "missing",
            "detail": results,
        }

    @staticmethod
    def check_disk_space(min_free_mb: int = 500) -> dict:
        """Verify enough free disk space for image storage."""
        try:
            import shutil
            usage = shutil.disk_usage(".")
            free_mb = usage.free / (1024 * 1024)
            status = "ok" if free_mb >= min_free_mb else "low"
            return {
                "name": "disk_space",
                "status": status,
                "detail": f"{free_mb:.0f} MB free (threshold {min_free_mb} MB)",
                "free_mb": round(free_mb, 1),
            }
        except Exception as exc:
            return {"name": "disk_space", "status": "error", "detail": str(exc)}

    @staticmethod
    def check_memory(threshold_mb: int = 2048) -> dict:
        """Warn if RSS exceeds threshold."""
        try:
            import psutil
            process = psutil.Process()
            rss_mb = process.memory_info().rss / (1024 * 1024)
            status = "ok" if rss_mb < threshold_mb else "high"
            return {
                "name": "memory",
                "status": status,
                "detail": f"{rss_mb:.0f} MB RSS (threshold {threshold_mb} MB)",
                "rss_mb": round(rss_mb, 1),
            }
        except ImportError:
            return {"name": "memory", "status": "ok", "detail": "psutil not available, skipping"}
        except Exception as exc:
            return {"name": "memory", "status": "error", "detail": str(exc)}

    def check_all(self) -> list[dict]:
        """Run all health checks and return results."""
        return [
            self.check_vlm_providers(),
            self.check_disk_space(),
            self.check_memory(),
        ]


# ── Heartbeat ──────────────────────────────────────────────────────────────

class Heartbeat:
    """Periodically runs health checks on a background timer."""

    def __init__(self, interval: float = 30.0):
        self._interval = interval
        self._timer: threading.Timer | None = None
        self._latest: list[dict] = []
        self._running = False
        self._lock = threading.Lock()

    def _run(self):
        checker = HealthChecker()
        with self._lock:
            self._latest = checker.check_all()
        if self._running:
            self._timer = threading.Timer(self._interval, self._run)
            self._timer.daemon = True
            self._timer.start()

    def start(self):
        if self._running:
            return
        self._running = True
        self._run()

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def last_heartbeat(self) -> dict:
        with self._lock:
            return {
                "timestamp": time.time(),
                "checks": list(self._latest),
            }


# ── Dependency Monitor ─────────────────────────────────────────────────────

class DependencyMonitor:
    """Generic registry for dependency health checks."""

    def __init__(self):
        self._checks: dict[str, Callable[[], dict]] = {}

    def register(self, name: str, check_fn: Callable[[], dict]):
        self._checks[name] = check_fn

    def check_all(self) -> list[dict]:
        results = []
        for name, fn in self._checks.items():
            try:
                result = fn()
                result.setdefault("name", name)
                results.append(result)
            except Exception as exc:
                results.append({"name": name, "status": "error", "detail": str(exc)})
        return results
