"""Tests for ReviewQueue — Phase 12"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from verifyiq.v2.review_queue import ReviewQueue, ReviewStatus, ReviewItem
from verifyiq.v2.models.decision import V2Decision


class TestReviewStatus:
    def test_enum_values(self):
        assert ReviewStatus.PENDING.value == "pending"
        assert ReviewStatus.APPROVED.value == "approved"
        assert ReviewStatus.REJECTED.value == "rejected"
        assert ReviewStatus.ESCALATED.value == "escalated"


class TestReviewItem:
    def test_default_status_is_pending(self):
        item = ReviewItem(
            claim_text="test",
            image_paths=[],
            claim_object="car",
            user_id="u1",
            decision=V2Decision(),
        )
        assert item.status == ReviewStatus.PENDING

    def test_optional_fields_default_to_none(self):
        item = ReviewItem(
            claim_text="test",
            image_paths=[],
            claim_object="car",
            user_id="u1",
            decision=V2Decision(),
        )
        assert item.reviewed_by is None
        assert item.reviewer_notes is None
        assert item.reviewed_at is None


class TestReviewQueue:
    def setup_method(self):
        self.queue = ReviewQueue()

    def test_add_returns_review_id(self):
        rid = self.queue.add("dent on bumper", [], "car", "user1", V2Decision())
        assert isinstance(rid, str)
        assert len(rid) > 0

    def test_add_unique_ids(self):
        rid1 = self.queue.add("dent", [], "car", "u1", V2Decision())
        rid2 = self.queue.add("scratch", [], "car", "u1", V2Decision())
        assert rid1 != rid2

    def test_get_pending_returns_new_items(self):
        self.queue.add("dent", [], "car", "u1", V2Decision())
        pending = self.queue.get_pending()
        assert len(pending) == 1
        assert pending[0].claim_text == "dent"

    def test_get_pending_excludes_reviewed(self):
        rid = self.queue.add("dent", [], "car", "u1", V2Decision())
        self.queue.review(rid, ReviewStatus.APPROVED, "reviewer1")
        pending = self.queue.get_pending()
        assert len(pending) == 0

    def test_get_by_status(self):
        rid1 = self.queue.add("dent", [], "car", "u1", V2Decision())
        self.queue.add("scratch", [], "car", "u1", V2Decision())
        self.queue.review(rid1, ReviewStatus.APPROVED, "rev1")
        approved = self.queue.get_by_status(ReviewStatus.APPROVED)
        pending = self.queue.get_by_status(ReviewStatus.PENDING)
        assert len(approved) == 1
        assert len(pending) == 1

    def test_review_returns_true_on_success(self):
        rid = self.queue.add("dent", [], "car", "u1", V2Decision())
        result = self.queue.review(rid, ReviewStatus.APPROVED, "rev1", notes="looks good")
        assert result is True

    def test_review_returns_false_on_bad_id(self):
        result = self.queue.review("nonexistent", ReviewStatus.APPROVED, "rev1")
        assert result is False

    def test_review_updates_fields(self):
        rid = self.queue.add("dent", [], "car", "u1", V2Decision())
        self.queue.review(rid, ReviewStatus.APPROVED, "rev1", notes="ok")
        items = self.queue.get_by_status(ReviewStatus.APPROVED)
        assert len(items) == 1
        assert items[0].reviewed_by == "rev1"
        assert items[0].reviewer_notes == "ok"
        assert items[0].reviewed_at is not None

    def test_get_stats_empty(self):
        stats = self.queue.get_stats()
        assert stats["total"] == 0
        assert stats["pending"] == 0
        assert stats["approved"] == 0
        assert stats["rejected"] == 0
        assert stats["escalated"] == 0

    def test_get_stats_after_adds(self):
        rid1 = self.queue.add("a", [], "car", "u1", V2Decision())
        rid2 = self.queue.add("b", [], "car", "u1", V2Decision())
        rid3 = self.queue.add("c", [], "car", "u1", V2Decision())
        self.queue.review(rid1, ReviewStatus.APPROVED, "r1")
        self.queue.review(rid2, ReviewStatus.REJECTED, "r1")
        self.queue.review(rid3, ReviewStatus.ESCALATED, "r1")
        stats = self.queue.get_stats()
        assert stats["total"] == 3
        assert stats["pending"] == 0
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["escalated"] == 1

    def test_multiple_reviews_same_id(self):
        rid = self.queue.add("dent", [], "car", "u1", V2Decision())
        r1 = self.queue.review(rid, ReviewStatus.APPROVED, "r1")
        r2 = self.queue.review(rid, ReviewStatus.REJECTED, "r1")
        assert r1 is True
        assert r2 is True
        items = self.queue.get_by_status(ReviewStatus.REJECTED)
        assert len(items) == 1
