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
    # review-03 S08-01/S08-02: one Apply per run. The primary key makes the claim
    # atomic across processes sharing this database; `status` drives crash recovery.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS apply_claims ("
        "thread_id TEXT PRIMARY KEY, "
        "successor TEXT NOT NULL, "
        "status TEXT NOT NULL"  # claimed -> seeded -> done
        ")"
    )
    conn.commit()
    return conn


def claim_apply(db_path: str, thread_id: str, successor: str) -> bool:
    """True if this caller now owns the run's one Apply; False if anyone else already does."""
    conn = _connect(db_path)
    try:
        conn.execute("INSERT INTO apply_claims (thread_id, successor, status) VALUES (?, ?, 'claimed')",
                     (thread_id, successor))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def set_claim_status(db_path: str, thread_id: str, status: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("UPDATE apply_claims SET status = ? WHERE thread_id = ?", (status, thread_id))
        conn.commit()
    finally:
        conn.close()


def release_claim(db_path: str, thread_id: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM apply_claims WHERE thread_id = ?", (thread_id,))
        conn.commit()
    finally:
        conn.close()


def get_claim(db_path: str, thread_id: str) -> tuple[str, str] | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT successor, status FROM apply_claims WHERE thread_id = ?", (thread_id,)).fetchone()
        return (row[0], row[1]) if row else None
    finally:
        conn.close()


def open_claims(db_path: str) -> list[tuple[str, str, str]]:
    conn = _connect(db_path)
    try:
        return conn.execute("SELECT thread_id, successor, status FROM apply_claims WHERE status != 'done'").fetchall()
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
