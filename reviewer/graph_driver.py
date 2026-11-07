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

from agent_core.certificates import Certificate
from agent_core.crews import Crew, ShiftCalendar
from agent_core.demo_fixtures import acushnet_demo_work_packages
from agent_core.graph import build_graph
from agent_core.shift_suggester import suggest_crew_shift
from agent_core.state import WorkPackageState
from reviewer import registry

DEFAULT_DB_PATH = str(Path(__file__).parent / "reviewer_state.db")


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
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._checkpointer = SqliteSaver(self._conn)
        self._graph = build_graph(checkpointer=self._checkpointer)
        self._recover_applies()

    def close(self) -> None:
        self._conn.close()

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
        if not registry.claim_apply(self.db_path, thread_id, new_thread):
            return ApplyResult(False, f"Not applied: another Apply on run {thread_id} is already in "
                                      "progress, or the run was already superseded.")

        packages = [WorkPackageState.model_validate(p) for p in inputs["packages"]]
        crews = [Crew.model_validate(c) for c in inputs["crews"]]
        calendar = ShiftCalendar.model_validate(inputs["calendar"])
        certificates = [Certificate.model_validate(c) for c in inputs.get("certificates") or []]
        fresh = suggest_crew_shift(packages, review.work_package_id, crews=crews,
                                   calendar=calendar, certificates=certificates)
        if fresh.suggestion is None or fresh.suggestion.model_dump() != shown["suggestion"]:
            registry.release_claim(self.db_path, thread_id)
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

        self.seed_run(new_thread, new_packages, crews=crews, calendar=calendar, certificates=certificates,
                      label=f"schedule change applied from {thread_id}")
        registry.set_claim_status(self.db_path, thread_id, "seeded")
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
        registry.set_claim_status(self.db_path, thread_id, "done")

    def _recover_applies(self) -> None:
        """
        review-03 S08-02: finish or roll back any Apply interrupted mid-way. If its
        successor run exists, finish superseding the old run. If not, nothing changed
        yet, so release the claim and the old run is reviewable again.
        """
        for thread_id, successor, _status in registry.open_claims(self.db_path):
            if self.run_inputs(successor):
                self._close_superseded_reviews(thread_id, successor)
            else:
                registry.release_claim(self.db_path, thread_id)

    def seed_demo(self, thread_id: str) -> None:
        """Runs the real ACUSHNET demo work packages through the REAL
        graph -- real deconfliction, real reasoning (deterministic
        fallback unless ANTHROPIC_API_KEY is set), a real interrupt()
        for every flagged package. Not the scripted event replay
        visualizer/demo_broadcaster.py uses."""
        self.seed_run(thread_id, acushnet_demo_work_packages(), label="ACUSHNET demo run")

    def _closed_to_decisions(self, thread_id: str) -> bool:
        """review-03 S08-02: a run being applied, or already superseded, takes no decisions."""
        return (registry.get_claim(self.db_path, thread_id) is not None
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
            for wp in state.values.get("reviewed_packages", []):
                if wp.hitl_disposition is not None:
                    decided.append(
                        {
                            "thread_id": thread_id,
                            "work_package_id": wp.work_package_id,
                            "disposition": wp.hitl_disposition,
                            "cleared_for_execution": wp.cleared_for_execution,
                            "superseded_by": registry.superseded_by(self.db_path, thread_id),
                        }
                    )
        return decided

    def submit_decision(
        self, thread_id: str, interrupt_id: str, decision: str, note: str | None = None
    ) -> None:
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
