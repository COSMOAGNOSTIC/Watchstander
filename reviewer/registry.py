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
    conn.commit()
    return conn


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
