"""VerifyIQ API — FastAPI service for claim verification.

Modes (set via VERIFYIQ_MODE env var):
  production  — reject startup if no vision provider is available
  demo        — allow text-only processing with clear "no vision" disclaimer
  research    — same as demo but with manual_review_required on all claims
"""

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from verifyiq.v2.observability.metrics import get_collector
from verifyiq.v2.observability.logging import get_logger
from verifyiq.v2.tracer import Tracer
from verifyiq.v2.vision_manager import VisionUnavailableError


# ── Request / Response Models ──────────────────────────────────────────────

class ClaimRequest(BaseModel):
    claim_text: str
    image_paths: list[str] = Field(default_factory=list)
    claim_object: str
    user_id: Optional[str] = None


class BatchRequest(BaseModel):
    claims: list[ClaimRequest]
    batch_size: int = 5


class ClaimResponse(BaseModel):
    claim_status: str
    confidence: float
    severity: str
    risk_flags: list[str]
    justification: str
    trace_id: str
    latency_ms: float


class BatchResponse(BaseModel):
    results: list[ClaimResponse]
    stats: dict


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    mode: str = "production"
    vision_state: str = "unknown"


# ── Lazy Singleton ─────────────────────────────────────────────────────────

_pipeline = None
_startup_time = time.time()
_logger = get_logger("api.main")


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from verifyiq.v2.pipeline import V2Pipeline
        _pipeline = V2Pipeline()
    return _pipeline


# ── Lifecycle ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_collector().reset()
    mode = os.environ.get("VERIFYIQ_MODE", "production")
    _logger.info(f"VerifyIQ API starting in {mode} mode")
    try:
        pipeline = get_pipeline()
        state = pipeline.vision_manager.state.value
        _logger.info(f"Vision state: {state}")
        if state == "unavailable" and mode == "production":
            _logger.error("VISION UNAVAILABLE — refusing startup in production mode")
            raise RuntimeError(
                "No vision provider available. Cannot start in PRODUCTION mode. "
                "Set VERIFYIQ_MODE=demo or VERIFYIQ_MODE=research to continue."
            )
    except RuntimeError:
        raise
    except Exception as exc:
        _logger.warning(f"Vision check failed during startup: {exc}")
    yield
    _logger.info("VerifyIQ API shutting down")


app = FastAPI(
    title="VerifyIQ API",
    description="Multi-modal claim verification service",
    version=os.environ.get("VERIFYIQ_VERSION", "0.1.0"),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


@app.post("/claim", response_model=ClaimResponse)
async def verify_claim(request: ClaimRequest):
    trace_id = Tracer.generate_trace_id()
    tracer = Tracer(trace_id)
    collector = get_collector()
    collector._request_counter += 1

    start = time.time()
    try:
        pipeline = get_pipeline()
        decision = pipeline.process(
            claim_text=request.claim_text,
            image_paths=request.image_paths,
            claim_object=request.claim_object,
            user_id=request.user_id or "",
        )
        latency = (time.time() - start) * 1000

        collector.record("api_claim", latency)
        collector._latencies.append(latency)

        _logger.info("Claim processed", extra={"trace_id": trace_id, "status": decision.claim_status})

        return ClaimResponse(
            claim_status=decision.claim_status,
            confidence=decision.confidence,
            severity=decision.severity,
            risk_flags=decision.risk_flags,
            justification=decision.justification,
            trace_id=trace_id,
            latency_ms=latency,
        )
    except VisionUnavailableError as exc:
        collector._failure_counter += 1
        latency = (time.time() - start) * 1000
        _logger.error("Vision unavailable", extra={"trace_id": trace_id, "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail={
                "error": "vision_unavailable",
                "message": str(exc),
                "hint": "Set VERIFYIQ_MODE=demo or VERIFYIQ_MODE=research to run without a vision provider.",
            },
        )
    except Exception as exc:
        collector._failure_counter += 1
        latency = (time.time() - start) * 1000
        _logger.error("Claim processing failed", extra={"trace_id": trace_id, "error": str(exc)})
        raise HTTPException(
            status_code=500,
            detail={"error": "processing_failed", "trace_id": trace_id},
        )


@app.post("/batch", response_model=BatchResponse)
async def batch_verify(request: BatchRequest):
    results = []
    errors = 0

    for i, claim_req in enumerate(request.claims):
        try:
            resp = await verify_claim(claim_req)
            results.append(resp)
        except HTTPException:
            errors += 1
            results.append(ClaimResponse(
                claim_status="error",
                confidence=0.0,
                severity="unknown",
                risk_flags=[],
                justification=f"Claim {i} failed",
                trace_id="",
                latency_ms=0.0,
            ))

    total = len(request.claims)
    return BatchResponse(
        results=results,
        stats={"total": total, "succeeded": total - errors, "failed": errors},
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    try:
        pipeline = get_pipeline()
        vm = pipeline.vision_manager
        vision_state = vm.state.value
        mode = vm.mode.value
        provider_report = vm.get_health_report()

        all_ok = vision_state != "unavailable" or mode != "production"
        code = 200 if all_ok else 503
        status = "healthy" if all_ok else "degraded"
    except Exception:
        vision_state = "unknown"
        mode = os.environ.get("VERIFYIQ_MODE", "production")
        status = "unknown"
        code = 200

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={
            "status": status,
            "version": os.environ.get("VERIFYIQ_VERSION", "0.1.0"),
            "uptime_seconds": time.time() - _startup_time,
            "mode": mode,
            "vision_state": vision_state,
            "vision_report": provider_report if 'provider_report' in dir() else None,
        },
        status_code=code,
    )


@app.get("/metrics")
async def metrics():
    collector = get_collector()
    snapshot = collector.snapshot()
    try:
        pipeline = get_pipeline()
        snapshot["vision"] = pipeline.vision_manager.get_health_report()
    except Exception:
        snapshot["vision"] = {"state": "unknown", "error": "could not collect"}
    return snapshot
