"""
Human-in-the-loop safety gate.

Any work package flagged by the deconfliction agent (or independently
marked CRITICAL risk) must stop here for a named human reviewer to
approve, reject, or modify before it can proceed. This node uses
LangGraph's `interrupt()` so the graph genuinely pauses execution
and waits -- it does not simulate a review, it blocks on one.

Restructured from a single node looping over N packages (one node
invocation, N interrupt() calls) to a fan-out of one node invocation
per package that needs review (Send()). The old shape reran the whole
loop -- including every already-resolved interrupt() call and every
events.emit() before it -- on every single resume, and serialized every
review behind every other one in submission order regardless of whether
they were related. This shape gives each package its own checkpointed
node invocation: reviewers don't block each other, and a crash mid-review
only affects the one package being reviewed at that moment.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END
from langgraph.types import Send, interrupt

from agent_core import events
from agent_core.reasoning import provenance_tag
from agent_core.state import HitlDisposition, RiskLevel, WorkPackageState


def _extract_decision(raw) -> tuple[HitlDisposition, str | None]:
    """
    Reads a disposition (and an optional audit-trail note) from a resume
    value. The reviewer app's UI is already structured -- a reviewer
    clicks a literal Approve or Reject button, never types a verdict as
    prose -- so this function's job is narrow: read the exact token the
    button produced, and treat everything else as an inert note that can
    never change which disposition is recorded.

    Two accepted shapes:
      - a dict, `{"decision": "approved"|"rejected", "note": <str, optional>}`
        -- the real reviewer app's resume value, and the only shape a
        real human decision should ever take.
      - a bare string that is EXACTLY (case-insensitive, whitespace-
        stripped) one of "approve", "approved", "reject", "rejected" --
        kept only for direct `graph.invoke(Command(resume=...))` callers
        in tests/CLI tooling. Any trailing text on a bare string --
        even something as benign as "approve, looks good" -- now fails
        closed to INVALID rather than being prefix-matched, because a
        bare string has no separate channel for rationale; use the dict
        shape's `note` field for that instead.

    This replaces the previous six-word negation/hedge-cue scanner
    (ADR-011), which tried to catch conditional or negated free text by
    checking a fixed list of eight cue phrases against the leading words
    of the answer. That approach was defeatable by any real-world hedge
    phrasing not on the list -- confirmed live through the reviewer app
    itself: a reviewer clicking Approve and typing "contingent on
    gas-free re-test" into the note field produced the resume string
    "approve - contingent on gas-free re-test", which matched none of
    the eight cue phrases and parsed as a clean APPROVED. Rather than
    grow the cue list indefinitely and stay one unanticipated phrase
    behind, this removes free-text parsing from the authorization
    channel entirely: the decision is read as an exact structural
    token, and any rationale or condition a reviewer attaches is
    recorded as a note but never inspected to determine disposition.

    See `HitlDisposition`'s docstring: this system has exactly two live
    dispositions today (plus fail-closed INVALID) and no conditional-
    approval state -- a note here is audit trail only, never enforced.
    """
    note = None
    if isinstance(raw, dict):
        token = str(raw.get("decision", "")).strip().lower()
        raw_note = raw.get("note")
        note = raw_note.strip() if isinstance(raw_note, str) and raw_note.strip() else None
    else:
        token = str(raw).strip().lower()

    if token in ("approve", "approved"):
        return HitlDisposition.APPROVED, note
    if token in ("reject", "rejected"):
        return HitlDisposition.REJECTED, note
    return HitlDisposition.INVALID, note


def _needs_review(wp: WorkPackageState) -> bool:
    return wp.requires_hitl_review or wp.risk_level == RiskLevel.CRITICAL


def hitl_prepare_node(state: dict) -> dict:
    passthrough = [wp for wp in state["work_packages"] if not _needs_review(wp)]
    return {"reviewed_packages": passthrough}


def hitl_route(state: dict):
    needs_review = [wp for wp in state["work_packages"] if _needs_review(wp)]
    if not needs_review:
        return END
    return [Send("hitl_gate_single", {"work_package": wp}) for wp in needs_review]


class HitlSingleState(TypedDict):
    work_package: WorkPackageState


def hitl_gate_single_node(state: HitlSingleState) -> dict:
    wp = state["work_package"]

    provenance = provenance_tag(wp.safety_brief.source) if wp.safety_brief else None

    events.emit(
        "hitl_awaiting",
        work_package_id=wp.work_package_id,
        hazard_categories=list(wp.hazard_categories),
        risk_level=wp.risk_level,
        safety_brief_provenance=provenance,
    )

    decision = interrupt(
        {
            "work_package_id": wp.work_package_id,
            "description": wp.description,
            "hazard_categories": wp.hazard_categories,
            "conflicts": wp.conflicts,
            "conflict_rationale": wp.conflict_rationale,
            "safety_brief": wp.safety_brief.model_dump() if wp.safety_brief else None,
            "safety_brief_provenance": provenance,
            "risk_level": wp.risk_level,
            "prompt": (
                f"Work package {wp.work_package_id} requires human review before "
                f"it can be approved. Submit a structured decision: "
                f"{{'decision': 'approved'|'rejected', 'note': <optional>}}. "
                f"A note is recorded for audit but never changes the disposition -- "
                f"there is no conditional-approval state yet; reject and have the "
                f"package resubmitted if approval should depend on something not "
                f"yet true."
            ),
        }
    )

    disposition, note = _extract_decision(decision)
    wp.hitl_disposition = disposition
    wp.cleared_for_execution = disposition == HitlDisposition.APPROVED

    events.emit(
        "hitl_decided",
        work_package_id=wp.work_package_id,
        disposition=disposition,
        cleared_for_execution=wp.cleared_for_execution,
    )

    rationale_suffix = f" | HITL decision: {disposition.value}"
    if note:
        rationale_suffix += f" (note: {note})"
    rationale_suffix += f" (cleared_for_execution={wp.cleared_for_execution})"
    wp.conflict_rationale = (wp.conflict_rationale or "") + rationale_suffix

    return {"reviewed_packages": [wp]}
