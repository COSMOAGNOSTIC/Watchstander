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

import fcntl
import os
import sqlite3
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agent_core.certificates import Certificate
from agent_core.crews import Crew, ShiftCalendar
from agent_core.demo_fixtures import acushnet_demo_work_packages
from agent_core.graph import build_graph
from agent_core.shift_suggester import suggest_crew_shift
from agent_core.state import WorkPackageState
from reviewer import registry

DEFAULT_DB_PATH = str(Path(__file__).parent / "reviewer_state.db")


def _owner_lock_path(db_path: str) -> str:
    """
    review-03 re-check 3: the lock must follow the DATABASE, not the name used to open it.
    A lock file named after the path let a symlink or hard link to the same database take
    a second, different lock. Key it on the file's identity (device + inode), which every
    alias shares. The database itself is never opened or closed for locking: on Linux,
    closing any handle to a file drops that process's SQLite (POSIX) locks on it.
    """
    if not os.path.exists(db_path):
        with open(db_path, "a"):  # create it, so it has an identity; nothing holds it open yet
            pass
    st = os.stat(db_path)  # follows symlinks; hard links share st_ino
    lock_dir = Path(tempfile.gettempdir()) / "watchstander-reviewer-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return str(lock_dir / f"{st.st_dev}-{st.st_ino}.lock")


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of the reviewer's Apply. `applied` False means nothing changed."""
    applied: bool
    message: str
    new_thread_id: str | None = None


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
        # review-03 re-check 2: ONE service per database. An exclusive OS file lock, held
        # for this service's lifetime, makes a second service on the same database refuse
        # to start. The OS releases it when this process exits for any reason (crash,
        # kill), so the next service to get it knows no other live owner exists.
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = open(_owner_lock_path(db_path), "w")
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock_file.close()
            raise RuntimeError(
                f"another reviewer service already has this database open ({db_path}); "
                "run one reviewer service per database"
            ) from None
        # Inside the one service: Apply and decisions run one at a time, end to end.
        self._op_lock = threading.RLock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._checkpointer = SqliteSaver(self._conn)
        self._graph = build_graph(checkpointer=self._checkpointer)
        self._recover_applies()

    def close(self) -> None:
        """Idempotent: releases the database lock so another service may open it."""
        if self._lock_file.closed:
            return
        self._conn.close()
        fcntl.flock(self._lock_file, fcntl.LOCK_UN)
        self._lock_file.close()

    def seed_run(self, thread_id: str, packages: list[WorkPackageState], *, crews=None,
                 calendar=None, certificates=None, label: str = "run") -> None:
        """
        Session 8b: run `packages` through the real graph, keeping an untouched copy of
        the inputs in state (`run_inputs`) so reasoning can suggest crew-shift moves and
        Apply can re-check against exactly what this run was seeded with.
        """
        run_inputs = {
            "packages": [p.model_dump() for p in packages],
            "crews": [c.model_dump() for c in crews] if crews else [],
            "calendar": calendar.model_dump() if calendar else None,
            "certificates": [c.model_dump() for c in certificates] if certificates else [],
        }
        config = {"configurable": {"thread_id": thread_id}}
        self._graph.invoke(
            {"work_packages": [p.model_copy(deep=True) for p in packages], "reviewed_packages": [],
             "run_inputs": run_inputs},
            config=config,
        )
        registry.register_thread(self.db_path, thread_id, label=label)

    def run_inputs(self, thread_id: str) -> dict | None:
        state = self._graph.get_state({"configurable": {"thread_id": thread_id}})
        return state.values.get("run_inputs")

    def apply_shift_suggestion(self, thread_id: str, interrupt_id: str) -> ApplyResult:
        with self._op_lock:  # review-03 re-check 2: one operation at a time, end to end
            return self._apply_locked(thread_id, interrupt_id)

    def _apply_locked(self, thread_id: str, interrupt_id: str) -> ApplyResult:
        """
        Session 8b. Re-run the crew-shift suggester against this run's inputs. Only if
        it returns exactly the move the brief showed:
          - start a NEW run with the moved times, every moved package marked
            requires_hitl_review (Apply never approves; the move gets a human decision);
          - close every still-pending review in the OLD run as rejected, noting it was
            superseded (those judgments were made against a schedule that no longer
            exists), and record the supersession.
        Otherwise nothing changes and the result says why.
        """
        review = self.get_pending_review(thread_id, interrupt_id)
        if review is None:
            return ApplyResult(False, "Not applied: no pending review found for that package "
                                      "(it may already be decided, or its run already superseded).")
        shown = (review.safety_brief or {}).get("shift_outcome") or {}
        if not shown.get("suggestion"):
            return ApplyResult(False, f"Not applied: the brief for {review.work_package_id} has no suggestion to apply.")
        inputs = self.run_inputs(thread_id)
        if not inputs or not inputs.get("crews") or not inputs.get("calendar"):
            return ApplyResult(False, "Not applied: this run has no crew or shift calendar data.")

        new_thread = f"{thread_id}-applied-{interrupt_id[:8]}"
        # review-03 S08-01: claim the run before anything else. From here on the old run
        # takes no decisions (S08-02), and no other Apply, in any process, can proceed.
        # review-03 re-check 2: re-read inside the lock. The review may have been decided
        # after it was first read.
        if not any(r.interrupt_id == interrupt_id for r in self._pending_for(thread_id)) \
                or self._closed_to_decisions(thread_id):
            return ApplyResult(False, f"Not applied: {review.work_package_id}'s review was decided, or its run "
                                      "superseded, while Apply was starting. Nothing was changed.")
        # The marker records an Apply in progress, for crash recovery and to close the run.
        if not registry.acquire_lock(self.db_path, thread_id, "apply", time.time(), successor=new_thread):
            return ApplyResult(False, f"Not applied: an Apply on run {thread_id} is already in progress.")

        packages = [WorkPackageState.model_validate(p) for p in inputs["packages"]]
        crews = [Crew.model_validate(c) for c in inputs["crews"]]
        calendar = ShiftCalendar.model_validate(inputs["calendar"])
        certificates = [Certificate.model_validate(c) for c in inputs.get("certificates") or []]
        fresh = suggest_crew_shift(packages, review.work_package_id, crews=crews,
                                   calendar=calendar, certificates=certificates)
        if fresh.suggestion is None or fresh.suggestion.model_dump() != shown["suggestion"]:
            registry.release_lock(self.db_path, thread_id)
            why = fresh.reason or "the re-check produced a different move"
            return ApplyResult(False, f"Not applied: the suggestion no longer holds ({why}). Nothing was changed.")

        moved = {m.work_package_id: m for m in fresh.suggestion.moves}
        new_packages = []
        for p in packages:
            data = p.model_dump()
            # The successor recomputes these; stale ones must not carry over (S08-03).
            data.update(conflicts=[], conflict_rationale=None, safety_brief=None)
            if p.work_package_id in moved:
                m = moved[p.work_package_id]
                # review-03 S08-03: a moved package always needs a fresh human decision.
                # Any approval or clearance it carried was for the old schedule.
                data.update(scheduled_start=m.suggested_start, scheduled_end=m.suggested_end,
                            requires_hitl_review=True, hitl_disposition=None,
                            cleared_for_execution=False)
            new_packages.append(WorkPackageState.model_validate(data))

        try:
            self.seed_run(new_thread, new_packages, crews=crews, calendar=calendar, certificates=certificates,
                          label=f"schedule change applied from {thread_id}")
        except Exception:
            # Nothing has changed yet, so reopen the old run rather than leave it closed.
            if not self.run_inputs(new_thread):
                registry.release_lock(self.db_path, thread_id)
            raise
        registry.set_lock_status(self.db_path, thread_id, "seeded")
        self._close_superseded_reviews(thread_id, new_thread)
        return ApplyResult(
            True,
            f"Schedule change applied in run {new_thread}: crew {fresh.suggestion.crew_id} moved to "
            f"{fresh.suggestion.to_shift_id}. Every moved package still needs review; "
            f"the reviews in run {thread_id} were superseded.",
            new_thread,
        )

    def _close_superseded_reviews(self, thread_id: str, successor: str) -> None:
        """Reject every still-pending review in the old run, record the supersession,
        and finish the claim. Idempotent, so crash recovery can call it again."""
        for pending in self._pending_for(thread_id):
            self._resume(thread_id, pending.interrupt_id, "reject",
                         f"superseded: schedule change applied in run {successor}")
        registry.mark_superseded(self.db_path, thread_id, successor)
        registry.release_lock(self.db_path, thread_id)

    def _recover_applies(self) -> None:
        """
        review-03 S08-02 and its re-checks: finish or roll back an Apply whose owner died.
        This runs only after this service holds the database's exclusive file lock, so no
        other live owner can exist and every leftover Apply marker is from a dead process.
        If its successor run exists, finish superseding the old run; if not, nothing
        changed yet, so release it and the old run is reviewable again. No clock, no lease.
        """
        for thread_id, kind, successor in registry.expired_locks(self.db_path, float("inf")):
            if kind == "apply" and successor and self.run_inputs(successor):
                self._close_superseded_reviews(thread_id, successor)
            else:
                registry.release_lock(self.db_path, thread_id)

    def seed_demo(self, thread_id: str) -> None:
        """Runs the real ACUSHNET demo work packages through the REAL
        graph -- real deconfliction, real reasoning (deterministic
        fallback unless ANTHROPIC_API_KEY is set), a real interrupt()
        for every flagged package. Not the scripted event replay
        visualizer/demo_broadcaster.py uses."""
        self.seed_run(thread_id, acushnet_demo_work_packages(), label="ACUSHNET demo run")

    def _closed_to_decisions(self, thread_id: str) -> bool:
        """review-03 S08-02: a run being applied, or already superseded, takes no decisions."""
        lock = registry.get_lock(self.db_path, thread_id)
        return ((lock is not None and lock["kind"] == "apply")
                or registry.superseded_by(self.db_path, thread_id) is not None)

    def list_pending_reviews(self) -> list[PendingReview]:
        pending: list[PendingReview] = []
        for thread_id in registry.list_thread_ids(self.db_path):
            if self._closed_to_decisions(thread_id):
                continue
            pending.extend(self._pending_for(thread_id))
        return pending

    def _pending_for(self, thread_id: str) -> list[PendingReview]:
        """Pending interrupts for one run, whether or not it is open to decisions."""
        pending: list[PendingReview] = []
        for thread_id in [thread_id]:
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
            superseded = registry.superseded_by(self.db_path, thread_id)
            for wp in state.values.get("reviewed_packages", []):
                if wp.hitl_disposition is not None:
                    decided.append(
                        {
                            "thread_id": thread_id,
                            "work_package_id": wp.work_package_id,
                            "disposition": wp.hitl_disposition,
                            # review-03 re-check: an approval on a replaced schedule never reads as cleared.
                            "cleared_for_execution": wp.cleared_for_execution and superseded is None,
                            "superseded_by": superseded,
                        }
                    )
        return decided

    def submit_decision(
        self, thread_id: str, interrupt_id: str, decision: str, note: str | None = None
    ) -> None:
        # review-03 re-check 2: the check and the write happen under the service's one
        # operation lock, so no Apply can start in between.
        with self._op_lock:
            if self._closed_to_decisions(thread_id):
                # review-03 S08-02: never act on a schedule that an Apply has replaced.
                raise ValueError(
                    f"run {thread_id} is superseded or being applied; review the packages in its successor run"
                )
            self._resume(thread_id, interrupt_id, decision, note)

    def _resume(self, thread_id: str, interrupt_id: str, decision: str, note: str | None) -> None:
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
