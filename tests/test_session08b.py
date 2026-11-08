"""Session 8b: crew-shift suggestion in the brief and the reviewer, and an Apply that
re-checks against the run's inputs, never approves, and supersedes the old run.

Runs the REAL graph through ReviewerService (tmp sqlite per test). All data notional.
"""

from datetime import date, datetime as dt, time

import pytest
from fastapi.testclient import TestClient

from agent_core.crews import Crew, ShiftCalendar
from agent_core.reasoning import reasoning_node
from agent_core.deconfliction import deconfliction_node
from agent_core.state import HazardCategory as H, HitlDisposition, SpatialCoordinates as SC, WorkPackageState as W
from reviewer import app as app_module
from reviewer import graph_driver, registry
from reviewer.graph_driver import ReviewerService

PATTERN = [("DAY", time(7), time(15, 30)), ("SWING", time(15, 30), time(0)), ("MID", time(0), time(7))]
CAL = ShiftCalendar.from_daily_pattern(date(2027, 1, 12), 3, PATTERN)
CREWS = [Crew(crew_id="CR-WELD", name="Notional weld crew"), Crew(crew_id="CR-TANK", name="Notional tank crew")]


def d(h, m=0, day=12):
    return dt(2027, 1, day, h, m)


def packages():
    return [
        W(work_package_id="WELD-1", description="notional hot work", hazard_categories=[H.HOT_WORK],
          spatial=SC(compartment_id="TANK-4"), scheduled_start=d(7), scheduled_end=d(11), crew_id="CR-WELD"),
        W(work_package_id="TANK-ENTRY", description="notional entry", hazard_categories=[H.CONFINED_SPACE],
          spatial=SC(compartment_id="TANK-4"), scheduled_start=d(7), scheduled_end=d(15), crew_id="CR-TANK"),
    ]


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def svc(tmp_path):
    s = ReviewerService(str(tmp_path / "rev.db"))
    yield s
    s.close()


def _seed(svc, thread="T1", pkgs=None):
    svc.seed_run(thread, pkgs or packages(), crews=CREWS, calendar=CAL, certificates=[], label="notional run")
    return {r.work_package_id: r for r in svc.list_pending_reviews() if r.thread_id == thread}


# --- the brief carries a deterministic suggestion -----------------------


def test_brief_carries_the_crew_shift_suggestion_and_says_not_applied(svc):
    weld = _seed(svc)["WELD-1"]
    outcome = weld.safety_brief["shift_outcome"]
    assert outcome["suggestion"]["to_shift_id"] == "20270112-SWING"
    assert outcome["suggestion"]["applied"] is False
    ra = weld.safety_brief["recommended_action"]
    assert "Suggested, not applied" in ra and "20270112-SWING" in ra and "CR-WELD" in ra


def test_brief_explains_when_there_is_no_suggestion(svc):
    # review-03 S08-06: a fixture that guarantees no suggestion (the only permit covers
    # just the original window), with assertions on the outcome and the visible reason.
    from agent_core.certificates import Certificate, CertificateKind
    from agent_core.state import SafetyPermitsRequired
    pkgs = packages()
    pkgs[0] = pkgs[0].model_copy(update={"permits_required": SafetyPermitsRequired(hot_work_permit=True)})
    cert = Certificate(certificate_id="HW-1", work_package_id="WELD-1", kind=CertificateKind.HOT_WORK_PERMIT,
                       valid_from=d(7), valid_until=d(11))
    svc.seed_run("T1", pkgs, crews=CREWS, calendar=CAL, certificates=[cert], label="notional run")
    weld = next(r for r in svc.list_pending_reviews() if r.work_package_id == "WELD-1")
    assert weld.safety_brief["shift_outcome"]["suggestion"] is None
    ra = weld.safety_brief["recommended_action"]
    assert "No crew-shift suggestion" in ra and "Suggested, not applied" not in ra
    assert "WS-CT-001" in ra


def test_run_without_crew_data_says_so_in_the_brief():
    state = deconfliction_node({"work_packages": packages()})
    state = reasoning_node(state)
    wp = next(p for p in state["work_packages"] if p.work_package_id == "WELD-1")
    assert wp.safety_brief.shift_outcome is None
    assert "No crew-shift suggestion: this run has no crew or shift calendar data" in wp.safety_brief.recommended_action


def test_seed_demo_still_works_without_crew_data(svc):
    svc.seed_acushnet_demo("DEMO")
    assert {r.work_package_id for r in svc.list_pending_reviews()} >= {"HW-2201", "CS-2202"}


# --- Apply ---------------------------------------------------------------


def test_apply_moves_the_block_in_a_new_run_and_never_approves(svc):
    weld = _seed(svc)["WELD-1"]
    res = svc.apply_shift_suggestion("T1", weld.interrupt_id)
    assert res.applied and res.new_thread_id
    new = {r.work_package_id: r for r in svc.list_pending_reviews() if r.thread_id == res.new_thread_id}
    assert "WELD-1" in new  # moved package always waits for a human decision
    inputs = svc.run_inputs(res.new_thread_id)
    moved = next(p for p in inputs["packages"] if p["work_package_id"] == "WELD-1")
    assert (moved["scheduled_start"], moved["scheduled_end"]) == (d(15, 30), d(19, 30))
    assert moved["requires_hitl_review"] is True
    assert not [x for x in svc.list_decided() if x["thread_id"] == res.new_thread_id]


def test_apply_supersedes_every_pending_review_in_the_old_run(svc):
    weld = _seed(svc)["WELD-1"]
    res = svc.apply_shift_suggestion("T1", weld.interrupt_id)
    assert not [r for r in svc.list_pending_reviews() if r.thread_id == "T1"]
    old = [x for x in svc.list_decided() if x["thread_id"] == "T1"]
    assert old and all(x["disposition"] == HitlDisposition.REJECTED for x in old)
    assert all(x["superseded_by"] == res.new_thread_id for x in old)


def test_apply_refuses_when_the_fresh_recheck_differs(svc, monkeypatch):
    weld = _seed(svc)["WELD-1"]
    from agent_core.shift_suggester import CrewShiftOutcome
    monkeypatch.setattr(graph_driver, "suggest_crew_shift",
                        lambda *a, **k: CrewShiftOutcome(reason="notional: a new conflict appeared"))
    res = svc.apply_shift_suggestion("T1", weld.interrupt_id)
    assert not res.applied and res.new_thread_id is None
    assert "no longer holds" in res.message and "new conflict appeared" in res.message
    assert "WELD-1" in {r.work_package_id for r in svc.list_pending_reviews() if r.thread_id == "T1"}


def test_apply_refuses_when_there_is_no_suggestion(svc):
    svc.seed_acushnet_demo("DEMO")
    hw = next(r for r in svc.list_pending_reviews() if r.work_package_id == "HW-2201")
    res = svc.apply_shift_suggestion("DEMO", hw.interrupt_id)
    assert not res.applied and "no suggestion" in res.message


def test_apply_on_an_unknown_review_is_refused(svc):
    _seed(svc)
    res = svc.apply_shift_suggestion("T1", "not-an-interrupt")
    assert not res.applied and "no pending review" in res.message


def test_apply_does_not_change_the_old_runs_inputs(svc):
    weld = _seed(svc)["WELD-1"]
    before = svc.run_inputs("T1")
    svc.apply_shift_suggestion("T1", weld.interrupt_id)
    assert svc.run_inputs("T1") == before


# --- reviewer UI ---------------------------------------------------------


def _client(tmp_path):
    app_module.service = ReviewerService(str(tmp_path / "ui.db"))
    return TestClient(app_module.app)


def test_detail_page_shows_the_suggestion_and_an_apply_button(tmp_path):
    client = _client(tmp_path)
    weld = _seed(app_module.service)["WELD-1"]
    page = client.get(f"/review/T1/{weld.interrupt_id}").text
    assert "Suggested, not applied" in page and "20270112-SWING" in page
    assert f'action="/review/T1/{weld.interrupt_id}/apply"' in page
    assert "re-checks" in page.lower()


def test_apply_endpoint_reports_the_outcome_on_the_dashboard(tmp_path):
    client = _client(tmp_path)
    weld = _seed(app_module.service)["WELD-1"]
    resp = client.post(f"/review/T1/{weld.interrupt_id}/apply", follow_redirects=True)
    assert resp.status_code == 200
    assert "Schedule change applied" in resp.text and "still needs review" in resp.text


def test_detail_page_has_no_apply_button_without_a_suggestion(tmp_path):
    client = _client(tmp_path)
    app_module.service.seed_acushnet_demo("DEMO")
    hw = next(r for r in app_module.service.list_pending_reviews() if r.work_package_id == "HW-2201")
    assert "/apply" not in client.get(f"/review/DEMO/{hw.interrupt_id}").text
