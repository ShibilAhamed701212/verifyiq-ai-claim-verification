"""Batch processing for 100/1000/10000 claims."""

import time
from code.v2.pipeline import V2Pipeline
from code.v2.rate_limiter import RateLimiter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    batch_size: int = 10
    max_workers: int = 4
    retry_attempts: int = 2
    timeout_ms: int = 30000


class BatchProcessor:
    """Process claims in batches with rate limiting and error isolation."""

    def __init__(self, pipeline: V2Pipeline, rate_limiter: RateLimiter | None = None):
        self.pipeline = pipeline
        self.rate_limiter = rate_limiter or RateLimiter()
        self._stats = {
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "latencies_ms": [],
            "start_time": None,
            "end_time": None,
        }

    def process_single(self, claim: dict) -> object:
        """Process a single claim with error handling."""
        try:
            if self.rate_limiter:
                self.rate_limiter.wait_if_needed()
            claim_text = claim.get("user_claim", "")
            image_paths = claim.get("image_paths", "").split(";") if claim.get("image_paths") else []
            image_paths = [p.strip() for p in image_paths if p.strip()]
            claim_object = claim.get("claim_object", "")
            user_id = claim.get("user_id", "")
            evidence_requirements = claim.get("evidence_requirements", None)

            result = self.pipeline.process(
                claim_text=claim_text,
                image_paths=image_paths,
                claim_object=claim_object,
                user_id=user_id,
                evidence_requirements=evidence_requirements,
            )
            return result
        except Exception:
            raise

    def process_batch(self, claims: list[dict], batch_size: int = 10, max_workers: int = 4) -> list:
        """Split claims into batches, process sequentially with parallel workers per batch."""
        self._stats["start_time"] = time.time()
        self._stats["total"] = len(claims)
        results: list = [None] * len(claims)

        for batch_start in range(0, len(claims), batch_size):
            batch = claims[batch_start:batch_start + batch_size]
            batch_results = self._process_batch_inner(batch, max_workers)
            for i, result in enumerate(batch_results):
                idx = batch_start + i
                if isinstance(result, Exception):
                    results[idx] = result
                else:
                    results[idx] = result

        self._stats["end_time"] = time.time()
        return results

    def _process_batch_inner(self, batch: list[dict], max_workers: int) -> list:
        """Process a single batch using thread pool for parallelism."""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self.process_single, claim): i
                for i, claim in enumerate(batch)
            }
            batch_results = []
            start = time.time()
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    result = future.result()
                    self._stats["succeeded"] += 1
                    elapsed_ms = (time.time() - start) * 1000
                    self._stats["latencies_ms"].append(elapsed_ms)
                    batch_results.append((idx, result))
                except Exception as e:
                    self._stats["failed"] += 1
                    batch_results.append((idx, e))

        batch_results.sort(key=lambda x: x[0])
        return [r for _, r in batch_results]

    def get_stats(self) -> dict:
        """Return processing statistics."""
        latencies = self._stats["latencies_ms"]
        total_time = 0.0
        if self._stats["start_time"] and self._stats["end_time"]:
            total_time = (self._stats["end_time"] - self._stats["start_time"]) * 1000
        return {
            "total": self._stats["total"],
            "succeeded": self._stats["succeeded"],
            "failed": self._stats["failed"],
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "total_time_ms": total_time,
        }
