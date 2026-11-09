"""
Decision log: every decision event, append-only (enforced) and tamper-evident.

Before Session 9, a human decision lived only inside the graph's checkpoint state.
Nothing recorded who decided, when, with what note, or why an Apply was refused,
a run superseded, or a crash recovered. This module records each of those as one
entry:

    seq, at (UTC), actor, kind, run_id, work_package_id, detail (JSON), prev_hash, hash

- Append-only is ENFORCED, not a convention: SQLite triggers abort any UPDATE or
  DELETE on the table (cf. rules_audit.py, where it is only a convention, AUD-15).
- Tamper-evident: each entry's hash covers the previous entry's hash and its own
  content, including its sequence number. `verify_chain()` recomputes every hash
  and names the first entry that was edited, removed or reordered, even if someone
  with raw database access dropped the triggers first.
- Kinds are a closed set. The log records what people and the system did; it never
  decides anything, and no LLM writes to it.

Lives in the reviewer's SQLite database. The reviewer service is the only writer,
and it is one-service-per-database (review-03).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

KINDS = frozenset({"decision_requested", "decision", "decision_refused", "decision_failed",
                   "apply_requested", "apply", "apply_refused", "apply_failed",
                   "superseded", "recovered"})  # *_failed: review-04; *_requested: review-05 R05-09
_OUTCOMES = {"decision_requested": {"decision", "decision_refused", "decision_failed"},
             "apply_requested": {"apply", "apply_refused", "apply_failed"}}
_GENESIS = "GENESIS"


class LogTamperError(RuntimeError):
    """The hash chain doesn't verify: an entry was edited, removed or reordered."""


@dataclass(frozen=True)
class LogEntry:
    seq: int
    at: datetime
    actor: str
    kind: str
    run_id: str
    work_package_id: Optional[str]
    detail: dict
    prev_hash: str
    hash: str


def _canonical(seq: int, at: str, actor: str, kind: str, run_id: str, wp: Optional[str], detail: str) -> str:
    return json.dumps({"seq": seq, "at": at, "actor": actor, "kind": kind, "run_id": run_id,
                       "work_package_id": wp, "detail": detail}, sort_keys=True, separators=(",", ":"))


def _hash(prev_hash: str, canonical: str) -> str:
    return hashlib.sha256(f"{prev_hash}\n{canonical}".encode()).hexdigest()


class DecisionLog:
    def __init__(self, db_path: str, read_only: bool = False) -> None:
        self.db_path = db_path
        if read_only:
            # review-05 R05-11: a reader never creates, migrates or writes the database.
            from pathlib import Path
            if not Path(db_path).is_file():
                raise FileNotFoundError(f"no database at {db_path}")
            self._conn = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True,
                                         check_same_thread=False, isolation_level=None)
            has = self._conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='decision_log'").fetchone()
            if not has:
                self._conn.close()
                raise LookupError(f"{db_path} has no decision log")
            return
        self._conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS decision_log (
                seq INTEGER PRIMARY KEY,
                at TEXT NOT NULL,
                actor TEXT NOT NULL,
                kind TEXT NOT NULL,
                run_id TEXT NOT NULL,
                work_package_id TEXT,
                detail TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                hash TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS decision_log_no_update BEFORE UPDATE ON decision_log
            BEGIN SELECT RAISE(ABORT, 'decision_log is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS decision_log_no_delete BEFORE DELETE ON decision_log
            BEGIN SELECT RAISE(ABORT, 'decision_log is append-only'); END;
        """)

    def close(self) -> None:
        self._conn.close()

    def append(self, *, kind: str, actor: str, run_id: str, work_package_id: Optional[str],
               detail: dict[str, Any], at: Optional[datetime] = None) -> LogEntry:
        if kind not in KINDS:
            raise ValueError(f"unknown decision-log kind {kind!r}; expected one of {sorted(KINDS)}")
        at_s = (at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        detail_s = json.dumps(detail, sort_keys=True, default=str)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute("SELECT seq, hash FROM decision_log ORDER BY seq DESC LIMIT 1").fetchone()
            seq, prev = (row[0] + 1, row[1]) if row else (1, _GENESIS)
            h = _hash(prev, _canonical(seq, at_s, actor, kind, run_id, work_package_id, detail_s))
            self._conn.execute(
                "INSERT INTO decision_log (seq, at, actor, kind, run_id, work_package_id, detail, prev_hash, hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (seq, at_s, actor, kind, run_id, work_package_id, detail_s, prev, h))
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return LogEntry(seq, datetime.fromisoformat(at_s), actor, kind, run_id, work_package_id,
                        json.loads(detail_s), prev, h)

    def entries(self) -> list[LogEntry]:
        rows = self._conn.execute(
            "SELECT seq, at, actor, kind, run_id, work_package_id, detail, prev_hash, hash "
            "FROM decision_log ORDER BY seq").fetchall()
        return [LogEntry(r[0], datetime.fromisoformat(r[1]), r[2], r[3], r[4], r[5], json.loads(r[6]), r[7], r[8])
                for r in rows]

    def open_requests(self) -> list[LogEntry]:
        """review-05 R05-09: requests with no outcome entry after them (same run and interrupt).
        One here means the outcome couldn't be logged: check that package in the graph."""
        entries = self.entries()
        out = []
        for i, e in enumerate(entries):
            if e.kind not in _OUTCOMES:
                continue
            key = (e.run_id, e.detail.get("interrupt_id"))
            if not any(x.kind in _OUTCOMES[e.kind] and (x.run_id, x.detail.get("interrupt_id")) == key
                       for x in entries[i + 1:]):
                out.append(e)
        return out

    def head(self) -> Optional[tuple[int, str]]:
        """(seq, hash) of the newest entry, or None for an empty log. Session 10: record
        this somewhere outside the database (the daily brief prints it) so a later
        `verify_anchor` can catch the newest entries being cut off, which the chain
        alone can't see."""
        row = self._conn.execute("SELECT seq, hash FROM decision_log ORDER BY seq DESC LIMIT 1").fetchone()
        return (row[0], row[1]) if row else None

    def verify_anchor(self, seq: int, expected_hash: str) -> None:
        """Raise LogTamperError unless entry `seq` exists with `expected_hash`. With
        `verify_chain()`, this proves entries 1..seq are the ones that were anchored."""
        row = self._conn.execute("SELECT hash FROM decision_log WHERE seq = ?", (seq,)).fetchone()
        if row is None:
            raise LogTamperError(f"anchor entry {seq} is missing: the log was cut back below it")
        if row[0] != expected_hash:
            raise LogTamperError(f"anchor entry {seq}'s hash does not match the recorded anchor")

    def verify_chain(self) -> int:
        """Recompute every hash. Returns the entry count, or raises LogTamperError."""
        rows = self._conn.execute(
            "SELECT seq, at, actor, kind, run_id, work_package_id, detail, prev_hash, hash "
            "FROM decision_log ORDER BY seq").fetchall()
        prev = _GENESIS
        for expected_seq, r in enumerate(rows, start=1):
            seq = r[0]
            if seq != expected_seq:
                raise LogTamperError(f"entry {expected_seq} is missing (next present entry is {seq})")
            if r[7] != prev:
                raise LogTamperError(f"entry {seq}: previous-hash link broken")
            if _hash(prev, _canonical(seq, r[1], r[2], r[3], r[4], r[5], r[6])) != r[8]:
                raise LogTamperError(f"entry {seq}: content does not match its hash (edited)")
            prev = r[8]
        return len(rows)
