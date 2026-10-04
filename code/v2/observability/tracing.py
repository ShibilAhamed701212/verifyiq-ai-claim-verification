import json
import time
from code.v2.models.decision import V2Decision
from pathlib import Path


class TraceLogger:
    """Persists decision traces for audit and debugging."""

    def __init__(self, log_dir: str = ".v2_traces"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_decision(self, claim_id: str, decision: V2Decision):
        trace = {
            "claim_id": claim_id,
            "timestamp": time.time(),
            "status": decision.claim_status,
            "confidence": decision.confidence,
            "risk_flags": decision.risk_flags,
            "justification": decision.justification[:500],
        }
        path = self.log_dir / f"{claim_id}.json"
        try:
            with open(path, "w") as f:
                json.dump(trace, f, indent=2)
        except Exception:
            pass
