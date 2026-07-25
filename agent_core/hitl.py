"""
Human-in-the-loop safety gate.

Any work package flagged by the deconfliction agent (or independently
marked CRITICAL risk) must stop here for a named human reviewer to
approve, reject, or modify before it can proceed. This node uses
LangGraph's `interrupt()` so the graph genuinely pauses execution
and waits — it does not simulate a review, it blocks on one.
"""

from __future__ import annotations

from langgraph.types import interrupt

from agent_core import events
from agent_core.reasoning import provenance_tag
from agent_core.state import HitlDisposition, RiskLevel, WorkPackageState


def _parse_decision(raw) -> HitlDisposition:
    """
    Turns whatever the human reviewer typed into a structured disposition.
    Case-insensitive prefix match on "approve"/"reject"; anything else -
    a typo, a note with no clear verdict, an empty string - is INVALID and
    is treated identically to REJECTED by the caller. This is a fail-closed
    parse: an ambiguous answer must never be read as approval.
    """
    text = str(raw).strip().lower()
    if text.startswith("approve"):
        return HitlDisposition.APPROVED
    if text.startswith("reject"):
        return HitlDisposition.REJECTED
    return HitlDisposition.INVALID


def hitl_gate_node(state: dict) -> dict:
    """
    Pauses graph execution for every work package requiring review.
    The interrupt payload carries enough context for a human reviewer
    to make a decision without digging through the full state object.
    """
    packages = state["work_packages"]
    reviewed: list[WorkPackageState] = []

    for wp in packages:
        needs_review = wp.requires_hitl_review or wp.risk_level == RiskLevel.CRITICAL
        if not needs_review:
            reviewed.append(wp)
            continue

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
                # Duplicated as a top-level field (not just embedded in
                # the brief text) so any UI rendering this payload can
                # surface it prominently without parsing prose.
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
        # The structural record a downstream consumer must actually check -
        # approve and reject are no longer just prose in conflict_rationale.
        # An unparseable answer fails closed (treated as not cleared), same
        # as an explicit rejection.
        wp.cleared_for_execution = disposition == HitlDisposition.APPROVED

        events.emit(
            "hitl_decided",
            work_package_id=wp.work_package_id,
            decision=str(decision),
            disposition=disposition,
            cleared_for_execution=wp.cleared_for_execution,
        )

        wp.conflict_rationale = (
            (wp.conflict_rationale or "")
            + f" | HITL decision: {decision} (disposition={disposition.value}, "
            f"cleared_for_execution={wp.cleared_for_execution})"
        )
        reviewed.append(wp)

    return {"work_packages": reviewed}
