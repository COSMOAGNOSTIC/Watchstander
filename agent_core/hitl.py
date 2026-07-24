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

from agent_core.state import RiskLevel, WorkPackageState


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

        decision = interrupt(
            {
                "work_package_id": wp.work_package_id,
                "description": wp.description,
                "hazard_categories": wp.hazard_categories,
                "conflicts": wp.conflicts,
                "conflict_rationale": wp.conflict_rationale,
                "risk_level": wp.risk_level,
                "prompt": (
                    f"Work package {wp.work_package_id} requires human review before "
                    f"it can be approved. Respond with 'approve', 'reject', or a note."
                ),
            }
        )

        wp.conflict_rationale = (wp.conflict_rationale or "") + f" | HITL decision: {decision}"
        reviewed.append(wp)

    return {"work_packages": reviewed}
