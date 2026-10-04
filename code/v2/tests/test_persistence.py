"""Tests for ClaimStore persistence — Phase 13"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from code.v2.models.decision import V2Decision
from code.v2.persistence import ClaimStore


class TestClaimStore:
    def setup_method(self):
        self.store = ClaimStore(":memory:")
        self.store.initialize()

    def test_initialize_creates_tables(self):
        store = ClaimStore(":memory:")
        store.initialize()
        tables = store._fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        names = {r[0] for r in tables}
        assert "claims" in names
        assert "decisions" in names
        assert "fraud_events" in names
        assert "review_items" in names
        assert "metrics_snapshots" in names

    def test_save_claim_returns_id(self):
        cid = self.store.save_claim("dent on bumper", "car", "user1")
        assert isinstance(cid, int)
        assert cid > 0

    def test_save_claim_increments_id(self):
        cid1 = self.store.save_claim("dent", "car", "u1")
        cid2 = self.store.save_claim("scratch", "car", "u1")
        assert cid2 > cid1

    def test_save_decision_returns_id(self):
        cid = self.store.save_claim("dent", "car", "u1")
        decision = V2Decision(
            claim_status="supported",
            severity="moderate",
            confidence=0.85,
            risk_flags=["low_confidence"],
            justification="seems legit",
        )
        did = self.store.save_decision(cid, decision)
        assert isinstance(did, int)
        assert did > 0

    def test_save_fraud_event_returns_id(self):
        cid = self.store.save_claim("dent", "car", "u1")
        fid = self.store.save_fraud_event(cid, "image_tampering", 0.9, ["exif_mismatch"])
        assert isinstance(fid, int)
        assert fid > 0

    def test_get_claim_returns_dict(self):
        cid = self.store.save_claim("dent on bumper", "car", "user1")
        claim = self.store.get_claim(cid)
        assert claim is not None
        assert claim["claim_text"] == "dent on bumper"
        assert claim["claim_object"] == "car"
        assert claim["user_id"] == "user1"

    def test_get_claim_nonexistent(self):
        claim = self.store.get_claim(9999)
        assert claim is None

    def test_get_recent_claims(self):
        self.store.save_claim("dent", "car", "u1")
        self.store.save_claim("scratch", "car", "u2")
        claims = self.store.get_recent_claims(limit=10)
        assert len(claims) == 2
        assert claims[0]["claim_text"] == "scratch"

    def test_get_recent_claims_empty(self):
        claims = self.store.get_recent_claims()
        assert claims == []

    def test_get_fraud_events_all(self):
        cid = self.store.save_claim("dent", "car", "u1")
        self.store.save_fraud_event(cid, "type_a", 0.5, [])
        self.store.save_fraud_event(cid, "type_b", 0.8, [])
        events = self.store.get_fraud_events()
        assert len(events) == 2

    def test_get_fraud_events_by_claim(self):
        cid1 = self.store.save_claim("dent", "car", "u1")
        cid2 = self.store.save_claim("scratch", "car", "u2")
        self.store.save_fraud_event(cid1, "type_a", 0.5, [])
        self.store.save_fraud_event(cid2, "type_b", 0.8, [])
        events = self.store.get_fraud_events(claim_id=cid1)
        assert len(events) == 1

    def test_save_metrics_snapshot(self):
        snapshot = {"total_requests": 10, "avg_latency": 150.5, "failure_count": 1}
        sid = self.store.save_metrics_snapshot(snapshot)
        assert isinstance(sid, int)
        assert sid > 0

    def test_get_metrics_history(self):
        snap1 = {"total_requests": 10, "avg_latency": 100.0, "failure_count": 0}
        snap2 = {"total_requests": 20, "avg_latency": 200.0, "failure_count": 1}
        self.store.save_metrics_snapshot(snap1)
        self.store.save_metrics_snapshot(snap2)
        history = self.store.get_metrics_history(hours=24)
        assert len(history) == 2

    def test_get_metrics_history_empty(self):
        history = self.store.get_metrics_history(hours=1)
        assert history == []
