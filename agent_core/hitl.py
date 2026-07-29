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


_NEGATION_CUES = (
    " not ",
    "n't",
    " unless ",
    " only if ",
    " except ",
    " provided that ",
    " as long as ",
    " until ",
)

_NEGATION_SCAN_WORDS = 6


def _parse_decision(raw) -> HitlDisposition:
    text = str(raw).strip().lower()
    lead_window = " ".join(text.split()[:_NEGATION_SCAN_WORDS])
    if any(cue in f" {lead_window} " for cue in _NEGATION_CUES):
        return HitlDisposition.INVALID
    if text.startswith("approve"):
        return HitlDisposition.APPROVED
    if text.startswith("reject"):
        return HitlDisposition.REJECTED
    return HitlDisposition.INVALID


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
                f"it can be approved. Respond with 'approve', 'reject', or a note."
            ),
        }
    )

    disposition = _parse_decision(decision)
    wp.hitl_disposition = disposition
    wp.cleared_for_execution = disposition == HitlDisposition.APPROVED

    events.emit(
        "hitl_decided",
        work_package_id=wp.work_package_id,
        disposition=disposition,
        cleared_for_execution=wp.cleared_for_execution,
    )

    wp.conflict_rationale = (
        (wp.conflict_rationale or "")
        + f" | HITL decision: {decision} (disposition={disposition.value}, "
        f"cleared_for_execution={wp.cleared_for_execution})"
    )

    return {"reviewed_packages": [wp]}
