"""
Findings gate: certificate and schedule findings reach human review.

Found by the builder while fixing review-03 S08-04, as the same bug class:
`check_certificates()` (Session 3) and `check_schedule_constraints()` (Session 6)
computed findings, but nothing in the graph acted on them. A job with no permit on
file, or scheduled outside every shift, passed straight through as cleared.

    certificate findings (always, from the run's certificates; none on file = MISSING) --+
    schedule findings (only when the run has a shift calendar) --------------------------+
        any finding naming a package --> requires_hitl_review, not cleared,
                                         rule + message + contact recorded in its rationale

Report-only on the findings themselves; it never edits a schedule or a certificate.
With no shift calendar, schedule rules can't be evaluated and nothing is routed on
schedule alone (the brief already says the run has no crew or shift calendar data).
"""

from __future__ import annotations

from agent_core import named_rules
from agent_core.certificates import Certificate, check_certificates
from agent_core.crews import Crew, ShiftCalendar, check_schedule_constraints


def _route(wp, note: str) -> None:
    wp.requires_hitl_review = True
    wp.cleared_for_execution = False
    if not wp.conflict_rationale:
        wp.conflict_rationale = note
    elif note not in wp.conflict_rationale:
        wp.conflict_rationale = f"{wp.conflict_rationale} | {note}"


def _hold(wp, rule_id: str) -> None:
    """review-05 R05-03: an open certificate or schedule finding blocks clearance even after approval."""
    if rule_id not in wp.open_findings:
        wp.open_findings.append(rule_id)


def findings_node(state: dict) -> dict:
    packages = state["work_packages"]
    inputs = state.get("run_inputs") or {}
    by_id = {p.work_package_id: p for p in packages}
    certificates = [Certificate.model_validate(c) for c in inputs.get("certificates") or []]
    routed = False

    for wp in packages:
        for f in check_certificates(wp, certificates):
            rule = named_rules.get_rule(f.rule_id)
            _route(wp, f"Finding {f.rule_id}: {f.message}. Contact: {rule.contact_role}.")
            _hold(wp, f.rule_id)
            routed = True

    # review-05 R05-10: crew rules (unknown crew, contractor windows, double booking) need no
    # calendar, so they run whenever the run has crew data; only WS-SC-003 needs the calendar.
    if inputs.get("calendar") or inputs.get("crews"):
        crews = [Crew.model_validate(c) for c in inputs.get("crews") or []]
        calendar = ShiftCalendar.model_validate(inputs["calendar"]) if inputs.get("calendar") else None
        for f in check_schedule_constraints(packages, crews, calendar):
            for pid in f.work_package_ids:
                _route(by_id[pid], f"Finding {f.message}")
                _hold(by_id[pid], f.rule_id)
            routed = True

    return {
        "work_packages": packages,
        "requires_hitl_review": bool(state.get("requires_hitl_review")) or routed,
    }
