"""SQLite persistence layer for claims, decisions, metrics, and fraud events."""

import json
import sqlite3
import threading
from code.v2.models.decision import V2Decision


class ClaimStore:
    """Thread-safe SQLite store for all V2 data."""

    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def initialize(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_text TEXT NOT NULL,
                    claim_object TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    claim_status TEXT,
                    severity TEXT,
                    confidence REAL,
                    risk_flags TEXT,
                    justification TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (claim_id) REFERENCES claims(id)
                );
                CREATE TABLE IF NOT EXISTS fraud_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    fraud_type TEXT NOT NULL,
                    fraud_score REAL,
                    flags TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (claim_id) REFERENCES claims(id)
                );
                CREATE TABLE IF NOT EXISTS review_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    reviewed_by TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    reviewed_at TEXT,
                    FOREIGN KEY (claim_id) REFERENCES claims(id)
                );
                CREATE TABLE IF NOT EXISTS metrics_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime('now')),
                    total_requests INTEGER DEFAULT 0,
                    avg_latency REAL DEFAULT 0.0,
                    failure_count INTEGER DEFAULT 0,
                    snapshot_data TEXT
                );
            """)
            self._conn.commit()

    def save_claim(self, claim_text: str, claim_object: str, user_id: str) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO claims (claim_text, claim_object, user_id) VALUES (?, ?, ?)",
                (claim_text, claim_object, user_id),
            )
            self._conn.commit()
            return cur.lastrowid

    def save_decision(self, claim_id: int, decision: V2Decision) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO decisions (claim_id, claim_status, severity, confidence, "
                "risk_flags, justification) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    claim_id,
                    decision.claim_status,
                    decision.severity,
                    decision.confidence,
                    json.dumps(decision.risk_flags),
                    decision.justification,
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def save_fraud_event(self, claim_id: int, fraud_type: str, fraud_score: float,
                         flags: list[str]) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO fraud_events (claim_id, fraud_type, fraud_score, flags) "
                "VALUES (?, ?, ?, ?)",
                (claim_id, fraud_type, fraud_score, json.dumps(flags)),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_claim(self, claim_id: int) -> dict | None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM claims WHERE id = ?", (claim_id,))
            row = cur.fetchone()
            if row is None:
                return None
            return dict(row)

    def get_recent_claims(self, limit: int = 50) -> list[dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM claims ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_fraud_events(self, claim_id: int | None = None) -> list[dict]:
        with self._lock:
            cur = self._conn.cursor()
            if claim_id is not None:
                cur.execute(
                    "SELECT * FROM fraud_events WHERE claim_id = ? ORDER BY created_at DESC",
                    (claim_id,),
                )
            else:
                cur.execute("SELECT * FROM fraud_events ORDER BY created_at DESC")
            return [dict(row) for row in cur.fetchall()]

    def save_metrics_snapshot(self, snapshot: dict) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO metrics_snapshots (total_requests, avg_latency, "
                "failure_count, snapshot_data) VALUES (?, ?, ?, ?)",
                (
                    snapshot.get("total_requests", 0),
                    snapshot.get("avg_latency", 0.0),
                    snapshot.get("failure_count", 0),
                    json.dumps(snapshot),
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_metrics_history(self, hours: int = 24) -> list[dict]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM metrics_snapshots WHERE timestamp >= "
                "datetime('now', '-' || ? || ' hours') ORDER BY timestamp ASC",
                (str(hours),),
            )
            return [dict(row) for row in cur.fetchall()]

    def _fetchall(self, sql: str) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(sql)
            return cur.fetchall()
