"""Regression tests for review-03 (Codex, Session 8). Named test_s08_NN_*. Written to fail
against 2f94ed5 before the fix. Real graph, real ReviewerService, temp sqlite. All data notional.
"""

import threading
from datetime import date, datetime as dt, time

import pytest
from fastapi.testclient import TestClient

from agent_core.certificates import Certificate, CertificateKind as K
from agent_core.crews import Crew, ShiftCalendar
from agent_core.state import HazardCategory as H, HitlDisposition, SafetyPermitsRequired, SpatialCoordinates as SC, WorkPackageState as W
from reviewer import app as app_module
from reviewer import graph_driver, registry
from reviewer.graph_driver import ReviewerService

PATTERN = [("DAY", time(7), time(15, 30)), ("SWING", time(15, 30), time(0)), ("MID", time(0), time(7))]
CAL = ShiftCalendar.from_daily_pattern(date(2027, 1, 12), 3, PATTERN)
CREWS = [Crew(crew_id="CR-WELD", name="n"), Crew(crew_id="CR-TANK", name="n")]


def d(h, m=0):
    return dt(2027, 1, 12, h, m)


def pair(**weld_kw):
    return [W(work_package_id="WELD-1", description="n", hazard_categories=[H.HOT_WORK], spatial=SC(compartment_id="TANK-4"),
              scheduled_start=d(7), scheduled_end=d(11), crew_id="CR-WELD", **weld_kw),
            W(work_package_id="TANK-ENTRY", description="n", hazard_categories=[H.CONFINED_SPACE], spatial=SC(compartment_id="TANK-4"),
              scheduled_start=d(7), scheduled_end=d(15), crew_id="CR-TANK")]


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def svc(tmp_path):
    s = ReviewerService(str(tmp_path / "r.db"))
    yield s
    s.close()


def seed(s, pkgs=None, certs=()):
    s.seed_run("T1", pkgs or pair(), crews=CREWS, calendar=CAL, certificates=list(certs))
    return {r.work_package_id: r for r in s.list_pending_reviews() if r.thread_id == "T1"}


# --- S08-01: one Apply per run, across processes -------------------------


def test_s08_01_two_applies_that_both_pass_the_pending_check_yield_one_successor(svc, monkeypatch):
    # Codex's ordering: both requests get past the pending-review check before either
    # claims the run. Only the atomic claim can stop the second one.
    pend = seed(svc)
    other = ReviewerService(svc.db_path)  # a second process sharing the database
    barrier = threading.Barrier(2, timeout=10)
    real = ReviewerService.get_pending_review

    def both_past_the_check(self, *a, **k):
        out = real(self, *a, **k)
        barrier.wait()
        return out

    monkeypatch.setattr(ReviewerService, "get_pending_review", both_past_the_check)
    res = {}
    threads = [threading.Thread(target=lambda key, sv: res.__setitem__(key, sv.apply_shift_suggestion("T1", pend[key].interrupt_id)),
                                args=(k, sv)) for k, sv in (("WELD-1", svc), ("TANK-ENTRY", other))]
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]
    applied = [k for k, r in res.items() if r.applied]
    assert len(applied) == 1, res
    loser = next(r for r in res.values() if not r.applied)
    assert "already in progress" in loser.message
    successors = [tid for tid in registry.list_thread_ids(svc.db_path) if tid != "T1"]
    assert successors == [res[applied[0]].new_thread_id]
    other.close()


def test_s08_01_apply_on_a_superseded_run_is_refused(svc):
    pend = seed(svc)
    assert svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id).applied
    again = svc.apply_shift_suggestion("T1", pend["TANK-ENTRY"].interrupt_id)
    assert not again.applied


# --- S08-02: interrupted Apply never leaves the old schedule actionable --


def _fail_first_old_rejection(monkeypatch):
    real = ReviewerService._close_superseded_reviews
    calls = {"n": 0}

    def boom(self, *a, **k):
        calls["n"] += 1
        raise RuntimeError("injected checkpoint failure")

    monkeypatch.setattr(ReviewerService, "_close_superseded_reviews", boom)
    return real


def test_s08_02_old_run_is_closed_to_decisions_from_the_moment_apply_starts(svc, monkeypatch):
    pend = seed(svc)
    _fail_first_old_rejection(monkeypatch)
    with pytest.raises(RuntimeError):
        svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    assert not [r for r in svc.list_pending_reviews() if r.thread_id == "T1"]
    with pytest.raises(ValueError, match="superseded|being applied"):
        svc.submit_decision("T1", pend["WELD-1"].interrupt_id, "approve")


def test_s08_02_restart_finishes_an_apply_whose_successor_exists(svc, monkeypatch):
    pend = seed(svc)
    real = _fail_first_old_rejection(monkeypatch)
    with pytest.raises(RuntimeError):
        svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    monkeypatch.setattr(ReviewerService, "_close_superseded_reviews", real)
    svc.close()
    s2 = ReviewerService(svc.db_path)
    successor = registry.superseded_by(s2.db_path, "T1")
    assert successor and s2.run_inputs(successor)
    old = [x for x in s2.list_decided() if x["thread_id"] == "T1"]
    assert old and all(x["disposition"] == HitlDisposition.REJECTED and not x["cleared_for_execution"] for x in old)
    assert "WELD-1" in {r.work_package_id for r in s2.list_pending_reviews() if r.thread_id == successor}
    s2.close()


def test_s08_02_restart_releases_an_apply_that_never_created_a_successor(svc, monkeypatch):
    pend = seed(svc)
    monkeypatch.setattr(ReviewerService, "seed_run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crash before successor")))
    with pytest.raises(RuntimeError):
        svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    monkeypatch.undo()
    svc.close()
    s2 = ReviewerService(svc.db_path)
    assert {r.work_package_id for r in s2.list_pending_reviews() if r.thread_id == "T1"} == {"WELD-1", "TANK-ENTRY"}
    assert registry.superseded_by(s2.db_path, "T1") is None
    s2.close()


# --- S08-03: a move never carries an old approval ------------------------


def test_s08_03_moved_package_loses_its_seeded_approval(svc):
    pend = seed(svc, pair(hitl_disposition=HitlDisposition.APPROVED, cleared_for_execution=True))
    res = svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    moved = next(p for p in svc.run_inputs(res.new_thread_id)["packages"] if p["work_package_id"] == "WELD-1")
    assert moved["hitl_disposition"] is None and moved["cleared_for_execution"] is False
    assert moved["requires_hitl_review"] is True


def test_s08_03_successor_inputs_carry_no_stale_derived_fields(svc):
    pend = seed(svc)
    res = svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    for p in svc.run_inputs(res.new_thread_id)["packages"]:
        assert p["conflicts"] == [] and p["conflict_rationale"] is None and p["safety_brief"] is None


# --- S08-04: every judgment flag reaches the review gate -----------------


def test_s08_04_unlocated_overhead_work_reaches_review_with_its_judgment_rule(svc):
    p = W(work_package_id="ALOFT", description="n", hazard_categories=[H.WORKING_ALOFT], spatial=SC(),
          scheduled_start=d(7), scheduled_end=d(11), crew_id="CR-WELD")
    [r] = list(seed(svc, [p]).values())
    assert r.work_package_id == "ALOFT"
    assert "WS-JF-006" in r.conflict_rationale and "Safety Officer" in r.conflict_rationale
    assert r.safety_brief is not None


def test_s08_04_every_judgment_rule_routes_to_review_not_just_the_new_one(svc):
    unlocated_hot = W(work_package_id="HOT", description="n", hazard_categories=[H.HOT_WORK], spatial=SC(),
                      scheduled_start=d(7), scheduled_end=d(11), crew_id="CR-WELD")
    [r] = list(seed(svc, [unlocated_hot]).values())
    assert "WS-JF-003" in r.conflict_rationale and "Gas Free Engineer" in r.conflict_rationale


def test_s08_04_package_with_no_flags_and_no_conflicts_still_passes_straight_through(svc):
    clean = W(work_package_id="CLEAN", description="n", spatial=SC(compartment_id="SHOP-1"),
              scheduled_start=d(7), scheduled_end=d(11), crew_id="CR-WELD")
    assert seed(svc, [clean]) == {}


# --- S08-05: why every shift failed is visible ----------------------------


def _permit_only_for_original_shift():
    pkgs = pair(permits_required=SafetyPermitsRequired(hot_work_permit=True))
    cert = Certificate(certificate_id="HW-1", work_package_id="WELD-1", kind=K.HOT_WORK_PERMIT, valid_from=d(7), valid_until=d(11))
    return pkgs, [cert]


def test_s08_05_brief_names_the_rule_that_rejected_each_shift(svc):
    pkgs, certs = _permit_only_for_original_shift()
    weld = seed(svc, pkgs, certs)["WELD-1"]
    ra = weld.safety_brief["recommended_action"]
    assert "No crew-shift suggestion" in ra and "WS-CT-001" in ra and "20270112-SWING" in ra


def test_s08_05_detail_page_lists_rejected_shifts_with_rules_and_reasons(tmp_path):
    app_module.service = ReviewerService(str(tmp_path / "ui.db"))
    pkgs, certs = _permit_only_for_original_shift()
    weld = seed(app_module.service, pkgs, certs)["WELD-1"]
    page = TestClient(app_module.app).get(f"/review/T1/{weld.interrupt_id}").text
    # The structured list itself, not the brief sentence (which also names the rule).
    assert "<li>20270112-SWING: WS-CT-001</li>" in page


def test_s08_05_reason_only_rejections_are_shown_too(svc):
    from agent_core.reasoning import describe_shift_outcome
    from agent_core.shift_suggester import CrewShiftOutcome, RejectedShift
    o = CrewShiftOutcome(rejected=[RejectedShift(shift_id="S1", rule_ids=[], reasons=["WELD-1 does not start in S1"])],
                         reason="no shift passes")
    assert "WELD-1 does not start in S1" in describe_shift_outcome(o)
