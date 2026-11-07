"""
Tiny local registry of thread_ids the reviewer app has created.

LangGraph's SqliteSaver checkpoints per-thread state, but doesn't offer a
cheap "list every thread_id that currently has a pending interrupt"
query -- enumerating it from raw checkpoint rows would mean depending on
its internal schema. Simpler and more robust: the reviewer app already
knows every thread_id it creates (`seed_demo` mints one), so it just
records them here and checks each one's current state on the dashboard.
This is a registry of "threads the app has ever started," not a
duplicate of graph state -- `graph_driver.list_pending_reviews()` is
still the only source of truth for what's actually pending.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def _connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS threads ("
        "thread_id TEXT PRIMARY KEY, "
        "label TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    # Session 8b: a run whose reviews were replaced by an applied schedule change.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS superseded ("
        "thread_id TEXT PRIMARY KEY, "
        "superseded_by TEXT NOT NULL"
        ")"
    )
    # review-03 (and its re-check): ONE lock per run, shared by Apply and decisions, so
    # neither can interleave with the other in any process. The primary key makes taking
    # it atomic; `acquired_at` is the lease start, so startup recovery only acts on locks
    # old enough to be abandoned (a live Apply is never mistaken for a crashed one).
    conn.execute(
        "CREATE TABLE IF NOT EXISTS run_locks ("
        "thread_id TEXT PRIMARY KEY, "
        "kind TEXT NOT NULL, "          # apply | decision
        "successor TEXT, "              # apply only
        "status TEXT NOT NULL, "        # held | seeded
        "acquired_at REAL NOT NULL"
        ")"
    )
    conn.commit()
    return conn


def acquire_lock(db_path: str, thread_id: str, kind: str, now: float, successor: str | None = None) -> bool:
    """True if this caller now holds the run's lock; False if anyone else does."""
    conn = _connect(db_path)
    try:
        conn.execute("INSERT INTO run_locks (thread_id, kind, successor, status, acquired_at) "
                     "VALUES (?, ?, ?, 'held', ?)", (thread_id, kind, successor, now))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def set_lock_status(db_path: str, thread_id: str, status: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("UPDATE run_locks SET status = ? WHERE thread_id = ?", (status, thread_id))
        conn.commit()
    finally:
        conn.close()


def release_lock(db_path: str, thread_id: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM run_locks WHERE thread_id = ?", (thread_id,))
        conn.commit()
    finally:
        conn.close()


def get_lock(db_path: str, thread_id: str) -> dict | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT kind, successor, status, acquired_at FROM run_locks WHERE thread_id = ?",
                           (thread_id,)).fetchone()
        return dict(zip(("kind", "successor", "status", "acquired_at"), row)) if row else None
    finally:
        conn.close()


def expired_locks(db_path: str, older_than: float) -> list[tuple[str, str, str | None]]:
    """(thread_id, kind, successor) for every lock taken at or before `older_than`."""
    conn = _connect(db_path)
    try:
        return conn.execute("SELECT thread_id, kind, successor FROM run_locks WHERE acquired_at <= ?",
                            (older_than,)).fetchall()
    finally:
        conn.close()


def mark_superseded(db_path: str, thread_id: str, superseded_by: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("INSERT OR REPLACE INTO superseded (thread_id, superseded_by) VALUES (?, ?)",
                     (thread_id, superseded_by))
        conn.commit()
    finally:
        conn.close()


def superseded_by(db_path: str, thread_id: str) -> str | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT superseded_by FROM superseded WHERE thread_id = ?", (thread_id,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def register_thread(db_path: str, thread_id: str, label: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO threads (thread_id, label) VALUES (?, ?)",
            (thread_id, label),
        )
        conn.commit()
    finally:
        conn.close()


def list_thread_ids(db_path: str) -> list[str]:
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT thread_id FROM threads ORDER BY created_at DESC").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()
