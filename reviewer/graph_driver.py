"""
Wraps `agent_core.graph.build_graph()` with a persistent SqliteSaver so
the reviewer web app can genuinely pause and resume the real graph
across separate HTTP requests -- "seed a run" is one request, "approve
this package" is a later, unrelated request, and the graph's
`interrupt()` state has to survive the gap between them on disk, not
just in a single process's memory (a `MemorySaver`, which is what every
test in tests/test_graph.py and tests/test_hitl.py uses, would lose all
pending reviews the moment the process restarts).

This is the first consumer of the real graph outside of the test suite
and the (fully scripted, no real graph run) visualizer demo -- see
reviewer/README.md for why that gap mattered.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agent_core.demo_fixtures import acushnet_demo_work_packages
from agent_core.graph import build_graph
from reviewer import registry

DEFAULT_DB_PATH = str(Path(__file__).parent / "reviewer_state.db")


@dataclass(frozen=True)
class PendingReview:
    """One flagged work package still awaiting a human decision. `interrupt_id`
    is what `Command(resume={interrupt_id: decision})` targets -- see
    hitl.py's docstring on why each package gets its own checkpointed
    interrupt() rather than one shared one."""

    thread_id: str
    interrupt_id: str
    work_package_id: str
    description: str
    hazard_categories: list[str]
    risk_level: str
    conflict_rationale: str | None
    safety_brief: dict | None
    safety_brief_provenance: str | None
    prompt: str


class ReviewerService:
    """One shared SqliteSaver connection for the app's lifetime --
    `check_same_thread=False` (langgraph's own choice, see
    SqliteSaver.from_conn_string) makes this safe across FastAPI's
    request threadpool for this app's traffic level (a single local
    reviewer, not concurrent production load)."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._checkpointer = SqliteSaver(self._conn)
        self._graph = build_graph(checkpointer=self._checkpointer)

    def close(self) -> None:
        self._conn.close()

    def seed_demo(self, thread_id: str) -> None:
        """Runs the real ACUSHNET demo work packages through the REAL
        graph -- real deconfliction, real reasoning (deterministic
        fallback unless ANTHROPIC_API_KEY is set), a real interrupt()
        for every flagged package. Not the scripted event replay
        visualizer/demo_broadcaster.py uses."""
        config = {"configurable": {"thread_id": thread_id}}
        self._graph.invoke(
            {"work_packages": acushnet_demo_work_packages(), "reviewed_packages": []},
            config=config,
        )
        registry.register_thread(self.db_path, thread_id, label="ACUSHNET demo run")

    def list_pending_reviews(self) -> list[PendingReview]:
        pending: list[PendingReview] = []
        for thread_id in registry.list_thread_ids(self.db_path):
            config = {"configurable": {"thread_id": thread_id}}
            state = self._graph.get_state(config)
            for task in state.tasks:
                if task.result is not None:
                    # A Send()-fanned-out task that has already been resumed
                    # keeps its original interrupt() value in this snapshot
                    # even after completing -- `task.result` being populated
                    # is what actually distinguishes "done" from "still
                    # paused," not the presence of `task.interrupts` alone.
                    # Found by testing the real approve flow: without this
                    # check, an already-approved package never left the
                    # pending queue.
                    continue
                for interrupt in task.interrupts:
                    value = interrupt.value
                    pending.append(
                        PendingReview(
                            thread_id=thread_id,
                            interrupt_id=interrupt.id,
                            work_package_id=value.get("work_package_id", ""),
                            description=value.get("description", ""),
                            hazard_categories=list(value.get("hazard_categories", [])),
                            risk_level=str(value.get("risk_level", "")),
                            conflict_rationale=value.get("conflict_rationale"),
                            safety_brief=value.get("safety_brief"),
                            safety_brief_provenance=value.get("safety_brief_provenance"),
                            prompt=value.get("prompt", ""),
                        )
                    )
        return pending

    def get_pending_review(self, thread_id: str, interrupt_id: str) -> PendingReview | None:
        for review in self.list_pending_reviews():
            if review.thread_id == thread_id and review.interrupt_id == interrupt_id:
                return review
        return None

    def list_decided(self) -> list[dict]:
        """Packages with a recorded HITL disposition, across every known
        thread -- the dashboard's "recently decided" section, proof the
        decision actually reached the graph's real state, not just a UI
        acknowledgment."""
        decided: list[dict] = []
        for thread_id in registry.list_thread_ids(self.db_path):
            config = {"configurable": {"thread_id": thread_id}}
            state = self._graph.get_state(config)
            for wp in state.values.get("reviewed_packages", []):
                if wp.hitl_disposition is not None:
                    decided.append(
                        {
                            "thread_id": thread_id,
                            "work_package_id": wp.work_package_id,
                            "disposition": wp.hitl_disposition,
                            "cleared_for_execution": wp.cleared_for_execution,
                        }
                    )
        return decided

    def submit_decision(
        self, thread_id: str, interrupt_id: str, decision: str, note: str | None = None
    ) -> None:
        """Resumes only this one interrupt -- every other package still
        pending on this or any other thread is left untouched and stays
        reviewable independently (verified directly: see
        reviewer/tests -- partial resume leaves the other interrupt
        pending, it does not require answering every open review in one
        call).

        `decision` and `note` are passed to the graph as separate
        structured fields, never concatenated into one string -- see
        agent_core/hitl.py's `_extract_decision` docstring for why: the
        prior string-concatenation shape (`f"{decision} - {note}"`) let
        a note's wording (e.g. "contingent on gas-free re-test") slip
        past the old hedge-cue parser and get recorded as a clean
        approval. Structured fields make that class of bug structurally
        impossible -- the note can never be mistaken for the decision."""
        config = {"configurable": {"thread_id": thread_id}}
        resume_value = {"decision": decision, "note": note}
        self._graph.invoke(Command(resume={interrupt_id: resume_value}), config=config)
