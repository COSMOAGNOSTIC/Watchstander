"""Builder-found during review-03 (same class as S08-04): certificate and schedule findings
were computed but never reached the review gate, so a job with no permit on file, or
outside every shift, passed through cleared. All data notional.
"""

from datetime import date, datetime as dt, time

import pytest

from agent_core.certificates import Certificate, CertificateKind as K
from agent_core.crews import Crew, ShiftCalendar
from agent_core.state import HazardCategory as H, SafetyPermitsRequired, SpatialCoordinates as SC, WorkPackageState as W
from reviewer.graph_driver import ReviewerService

CAL = ShiftCalendar.from_daily_pattern(date(2027, 1, 12), 1, [("DAY", time(7), time(15, 30))])
CREWS = [Crew(crew_id="CR-1", name="n")]


def d(h, m=0):
    return dt(2027, 1, 12, h, m)


def wp(pid, start=d(7), end=d(11), crew="CR-1", permit=False, comp=None):
    return W(work_package_id=pid, description="n", hazard_categories=[H.HOT_WORK] if permit else [],
             spatial=SC(compartment_id=comp or f"SHOP-{pid}"), scheduled_start=start, scheduled_end=end, crew_id=crew,
             permits_required=SafetyPermitsRequired(hot_work_permit=permit))


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def svc(tmp_path):
    s = ReviewerService(str(tmp_path / "r.db"))
    yield s
    s.close()


def run(svc, pkgs, certs=(), crews=CREWS, calendar=CAL):
    svc.seed_run("T", pkgs, crews=crews, calendar=calendar, certificates=list(certs))
    pending = {r.work_package_id: r for r in svc.list_pending_reviews()}
    state = svc._graph.get_state({"configurable": {"thread_id": "T"}}).values
    passed = {p.work_package_id: p for p in state.get("reviewed_packages", []) if p.hitl_disposition is None}
    return pending, passed


# --- certificates ----------------------------------------------------------


def test_required_permit_with_no_certificate_goes_to_review(svc):
    pending, passed = run(svc, [wp("HW", permit=True)])
    assert "HW" in pending and "HW" not in passed
    assert "WS-CT-001" in pending["HW"].conflict_rationale
    assert "Fire Safety Coordinator" in pending["HW"].conflict_rationale


def test_permit_expiring_mid_job_goes_to_review(svc):
    cert = Certificate(certificate_id="C", work_package_id="HW", kind=K.HOT_WORK_PERMIT, valid_from=d(7), valid_until=d(9))
    pending, _ = run(svc, [wp("HW", permit=True)], certs=[cert])
    assert "WS-CT-001" in pending["HW"].conflict_rationale


def test_permit_covering_the_whole_job_passes_through_cleared(svc):
    cert = Certificate(certificate_id="C", work_package_id="HW", kind=K.HOT_WORK_PERMIT, valid_from=d(6), valid_until=d(12))
    pending, passed = run(svc, [wp("HW", permit=True)], certs=[cert])
    assert "HW" not in pending and passed["HW"].cleared_for_execution


def test_missing_certificate_is_checked_even_without_crew_data(svc):
    pending, _ = run(svc, [wp("HW", permit=True, crew=None)], crews=None, calendar=None)
    assert "WS-CT-001" in pending["HW"].conflict_rationale


# --- schedule --------------------------------------------------------------


def test_work_outside_every_shift_goes_to_review(svc):
    pending, _ = run(svc, [wp("NIGHT", start=d(20), end=d(22))])
    assert "WS-SC-003" in pending["NIGHT"].conflict_rationale


def test_unknown_crew_goes_to_review(svc):
    pending, _ = run(svc, [wp("GHOST", crew="CR-NOPE")])
    assert "WS-SC-001" in pending["GHOST"].conflict_rationale


def test_double_booked_crew_sends_both_packages_to_review(svc):
    pending, _ = run(svc, [wp("A", start=d(7), end=d(11)), wp("B", start=d(10), end=d(14))])
    assert {"A", "B"} <= set(pending)
    assert all("WS-SC-004" in pending[k].conflict_rationale for k in ("A", "B"))


def test_without_a_calendar_schedule_rules_do_not_route(svc):
    # No crew named: since 2026-11-11 a named crew with no roster is its own finding (Donnie).
    pending, passed = run(svc, [wp("NIGHT", start=d(20), end=d(22), crew=None)], crews=None, calendar=None)
    assert "NIGHT" not in pending and passed["NIGHT"].cleared_for_execution


def test_clean_scheduled_job_with_no_permit_needed_passes_through(svc):
    pending, passed = run(svc, [wp("OK")])
    assert pending == {} and passed["OK"].cleared_for_execution


def test_every_finding_on_a_package_is_recorded(svc):
    pending, _ = run(svc, [wp("BOTH", start=d(20), end=d(22), permit=True)])
    r = pending["BOTH"].conflict_rationale
    assert "WS-CT-001" in r and "WS-SC-003" in r


def test_a_routed_package_is_not_cleared_while_it_waits(svc):
    # Same wrong-direction shape as review-03 S08-03: awaiting review must never read as cleared.
    run(svc, [wp("HW", permit=True), wp("NIGHT", start=d(20), end=d(22))])
    state = svc._graph.get_state({"configurable": {"thread_id": "T"}}).values
    waiting = {p.work_package_id: p for p in state["work_packages"]}
    assert waiting["HW"].cleared_for_execution is False and waiting["HW"].requires_hitl_review
    assert waiting["NIGHT"].cleared_for_execution is False and waiting["NIGHT"].requires_hitl_review


def test_findings_node_itself_leaves_no_routed_package_cleared():
    # In memory, between graph steps, before any checkpoint reload re-runs the model's validator.
    from agent_core.findings_gate import findings_node
    pkgs = [wp("HW", permit=True)]
    out = findings_node({"work_packages": pkgs, "run_inputs": {"certificates": []}})
    assert out["work_packages"][0].cleared_for_execution is False and out["requires_hitl_review"] is True
