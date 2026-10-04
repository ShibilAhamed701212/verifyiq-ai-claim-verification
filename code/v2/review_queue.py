"""Manual review queue for VerifyIQ decisions."""

import enum
import threading
import time
import uuid
from code.v2.models.decision import V2Decision
from dataclasses import dataclass


class ReviewStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


@dataclass
class ReviewItem:
    claim_text: str
    image_paths: list[str]
    claim_object: str
    user_id: str
    decision: V2Decision
    status: ReviewStatus = ReviewStatus.PENDING
    reviewed_by: str | None = None
    reviewer_notes: str | None = None
    reviewed_at: float | None = None


class ReviewQueue:
    """In-memory queue for manual review of claims."""

    def __init__(self):
        self._items: dict[str, ReviewItem] = {}
        self._lock = threading.Lock()

    def add(self, claim_text: str, image_paths: list[str], claim_object: str,
            user_id: str, decision: V2Decision) -> str:
        review_id = uuid.uuid4().hex[:12]
        item = ReviewItem(
            claim_text=claim_text,
            image_paths=image_paths,
            claim_object=claim_object,
            user_id=user_id,
            decision=decision,
        )
        with self._lock:
            self._items[review_id] = item
        return review_id

    def get_pending(self) -> list[ReviewItem]:
        with self._lock:
            return [it for it in self._items.values() if it.status == ReviewStatus.PENDING]

    def get_by_status(self, status: ReviewStatus) -> list[ReviewItem]:
        with self._lock:
            return [it for it in self._items.values() if it.status == status]

    def review(self, review_id: str, status: ReviewStatus, reviewer: str,
               notes: str | None = None) -> bool:
        with self._lock:
            if review_id not in self._items:
                return False
            item = self._items[review_id]
            item.status = status
            item.reviewed_by = reviewer
            item.reviewer_notes = notes
            item.reviewed_at = time.time()
            return True

    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._items)
            pending = sum(1 for it in self._items.values() if it.status == ReviewStatus.PENDING)
            approved = sum(1 for it in self._items.values() if it.status == ReviewStatus.APPROVED)
            rejected = sum(1 for it in self._items.values() if it.status == ReviewStatus.REJECTED)
            escalated = sum(1 for it in self._items.values() if it.status == ReviewStatus.ESCALATED)
            return {
                "total": total,
                "pending": pending,
                "approved": approved,
                "rejected": rejected,
                "escalated": escalated,
            }
