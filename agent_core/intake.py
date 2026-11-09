"""
Intake: the graph's first step (review-05 R05-01, R05-02).

A decision only ever comes from a person through the reviewer. Input packages can't
arrive approved or cleared, and can't carry findings from somewhere else:

    input hitl_disposition / cleared_for_execution / open_findings ──► dropped
    rejection carried by Apply (run_inputs["carried_rejections"]) ──► re-applied
                                                                       (stays REJECTED, not re-queued)
    then the package is re-validated, so a CRITICAL or flagged package fails closed again.

Pure on its inputs; the brief (agent_core/daily_brief.py) runs the same step.
"""

from __future__ import annotations

from agent_core.state import HitlDisposition, WorkPackageState

_DECIDED_FIELDS = ("hitl_disposition", "cleared_for_execution", "open_findings")


def intake(packages: list[WorkPackageState], carried_rejections: dict | None = None) -> list[WorkPackageState]:
    carried = carried_rejections or {}
    out = []
    for p in packages:
        data = p.model_dump()
        for f in _DECIDED_FIELDS:
            data.pop(f, None)
        wp = WorkPackageState.model_validate(data)  # validator fails closed on CRITICAL / flagged
        c = carried.get(wp.work_package_id)
        if c is not None:
            wp.hitl_disposition = HitlDisposition.REJECTED
            wp.cleared_for_execution = False
            note = (f"Rejection carried from run {c.get('run')} by {c.get('actor')}"
                    + (f" (note: {c['note']})" if c.get("note") else "")
                    + "; stays rejected until the package itself is resubmitted.")
            wp.conflict_rationale = f"{wp.conflict_rationale} | {note}" if wp.conflict_rationale else note
        out.append(wp)
    return out


def intake_node(state: dict) -> dict:
    inputs = state.get("run_inputs") or {}
    return {"work_packages": intake(state["work_packages"], inputs.get("carried_rejections"))}
