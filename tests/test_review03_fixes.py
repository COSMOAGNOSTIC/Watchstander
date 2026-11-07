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
    s2 = ReviewerService(svc.db_path)  # restart: the first service is closed
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
    s2 = ReviewerService(svc.db_path)  # restart: the first service is closed
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


def test_s08_04_judgment_node_itself_leaves_no_flagged_package_cleared():
    from agent_core.judgment import judgment_node
    p = W(work_package_id="ALOFT", description="n", hazard_categories=[H.WORKING_ALOFT], spatial=SC(),
          scheduled_start=d(7), scheduled_end=d(11))
    out = judgment_node({"work_packages": [p]})
    assert out["work_packages"][0].cleared_for_execution is False and out["requires_hitl_review"] is True


# ===== review-03 re-check: startup recovery vs a LIVE Apply; decision vs Apply =====


def _pause_apply_after_lock(monkeypatch, svc, pend, key="WELD-1"):
    """Start Apply A in a thread and pause it inside the suggester (after it holds the lock)."""
    real = graph_driver.suggest_crew_shift
    inside, release = threading.Event(), threading.Event()

    def paused(*a, **k):
        out = real(*a, **k)
        if threading.current_thread().name == "A":
            inside.set()
            release.wait(timeout=10)
        return out

    monkeypatch.setattr(graph_driver, "suggest_crew_shift", paused)
    res = {}
    t = threading.Thread(name="A", target=lambda: res.__setitem__("A", svc.apply_shift_suggestion("T1", pend[key].interrupt_id)))
    t.start()
    assert inside.wait(timeout=10)
    return t, release, res


def test_recheck_superseded_run_never_reports_cleared(svc):
    pend = seed(svc)
    svc.submit_decision("T1", pend["TANK-ENTRY"].interrupt_id, "approve")  # approved on the old schedule
    res = svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    assert res.applied
    old_entry = next(x for x in svc.list_decided() if x["thread_id"] == "T1" and x["work_package_id"] == "TANK-ENTRY")
    assert old_entry["superseded_by"] == res.new_thread_id and old_entry["cleared_for_execution"] is False


# ===== review-03 re-check 2: one service per database; serialized operations =====

import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import textwrap  # noqa: E402


def test_recheck2_a_second_service_on_the_same_database_refuses_to_start(svc):
    with pytest.raises(RuntimeError, match="already has this database open"):
        ReviewerService(svc.db_path)


def test_recheck2_closing_a_service_lets_another_open_the_database(svc):
    svc.close()
    ReviewerService(svc.db_path).close()


def _pause_in_suggester(monkeypatch, thread_name="A"):
    real = graph_driver.suggest_crew_shift
    inside, release = threading.Event(), threading.Event()

    def paused(*a, **k):
        out = real(*a, **k)
        if threading.current_thread().name == thread_name:
            inside.set()
            release.wait(timeout=10)
        return out

    monkeypatch.setattr(graph_driver, "suggest_crew_shift", paused)
    return inside, release


def test_recheck2_concurrent_applies_in_one_service_yield_one_successor(svc, monkeypatch):
    pend = seed(svc)
    inside, release = _pause_in_suggester(monkeypatch)
    res = {}
    a = threading.Thread(name="A", target=lambda: res.__setitem__("A", svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)))
    a.start()
    assert inside.wait(timeout=10)
    b = threading.Thread(name="B", target=lambda: res.__setitem__("B", svc.apply_shift_suggestion("T1", pend["TANK-ENTRY"].interrupt_id)))
    b.start()
    release.set()
    a.join(timeout=20)
    b.join(timeout=20)
    assert res["A"].applied and not res["B"].applied
    assert [tid for tid in registry.list_thread_ids(svc.db_path) if tid != "T1"] == [res["A"].new_thread_id]


def test_recheck2_decision_during_a_live_apply_is_refused_once_apply_finishes(svc, monkeypatch):
    pend = seed(svc)
    inside, release = _pause_in_suggester(monkeypatch)
    res, errors = {}, {}
    a = threading.Thread(name="A", target=lambda: res.__setitem__("A", svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)))
    a.start()
    assert inside.wait(timeout=10)

    def decide():
        try:
            svc.submit_decision("T1", pend["WELD-1"].interrupt_id, "approve")
        except ValueError as e:
            errors["D"] = str(e)

    d = threading.Thread(name="D", target=decide)
    d.start()
    release.set()
    a.join(timeout=20)
    d.join(timeout=20)
    assert res["A"].applied and "superseded" in errors["D"]
    assert not [x for x in svc.list_decided() if x["thread_id"] == "T1" and x["cleared_for_execution"]]


def test_recheck2_apply_rereads_the_review_and_refuses_one_decided_meanwhile(svc, monkeypatch):
    # The reviewer's stale-read ordering: Apply read the review, then it was approved.
    pend = seed(svc)
    real = ReviewerService.get_pending_review
    state = {"done": False}

    def read_then_decided(self, *a, **k):
        out = real(self, *a, **k)
        if not state["done"]:
            state["done"] = True
            self.submit_decision("T1", pend["WELD-1"].interrupt_id, "approve")
        return out

    monkeypatch.setattr(ReviewerService, "get_pending_review", read_then_decided)
    r = svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    assert not r.applied and "decided" in r.message
    assert registry.superseded_by(svc.db_path, "T1") is None


def test_recheck2_failure_before_a_successor_reopens_the_run_immediately(svc, monkeypatch):
    pend = seed(svc)
    monkeypatch.setattr(ReviewerService, "seed_run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fail before successor")))
    with pytest.raises(RuntimeError):
        svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    monkeypatch.undo()
    assert {r.work_package_id for r in svc.list_pending_reviews() if r.thread_id == "T1"} == {"WELD-1", "TANK-ENTRY"}


def test_recheck2_a_process_killed_mid_apply_is_recovered_by_the_next_service(tmp_path):
    # A real crash: a separate process dies (os._exit) after creating the successor
    # but before closing the old reviews. The OS releases its database lock.
    db = str(tmp_path / "crash.db")
    script = textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {os.getcwd()!r}); sys.path.insert(0, {os.path.join(os.getcwd(), "tests")!r})
        os.environ.pop("ANTHROPIC_API_KEY", None)
        from test_review03_fixes import seed
        from reviewer.graph_driver import ReviewerService
        s = ReviewerService({db!r})
        pend = seed(s)
        ReviewerService._close_superseded_reviews = lambda *a, **k: os._exit(7)
        s.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    """)
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 7, proc.stderr[-2000:]
    s2 = ReviewerService(db)  # gets the lock the dead process held; recovery finishes its Apply
    successor = registry.superseded_by(db, "T1")
    assert successor and s2.run_inputs(successor)
    assert not [r for r in s2.list_pending_reviews() if r.thread_id == "T1"]
    assert not [x for x in s2.list_decided() if x["thread_id"] == "T1" and x["cleared_for_execution"]]
    s2.close()


def test_recheck2_a_decision_in_progress_holds_off_apply_until_it_finishes(svc, monkeypatch):
    # Direct proof of serialization: while a decision is mid-write, Apply must not start.
    pend = seed(svc)
    d_inside, d_release = threading.Event(), threading.Event()
    real_resume = ReviewerService._resume

    def slow_resume(self, *a, **k):
        if threading.current_thread().name == "D":
            d_inside.set()
            d_release.wait(timeout=10)
        return real_resume(self, *a, **k)

    monkeypatch.setattr(ReviewerService, "_resume", slow_resume)
    a_started = threading.Event()
    real_suggest = graph_driver.suggest_crew_shift
    monkeypatch.setattr(graph_driver, "suggest_crew_shift", lambda *a, **k: (a_started.set(), real_suggest(*a, **k))[1])
    d = threading.Thread(name="D", target=lambda: svc.submit_decision("T1", pend["TANK-ENTRY"].interrupt_id, "approve"))
    d.start()
    assert d_inside.wait(timeout=10)
    a = threading.Thread(name="A", target=lambda: svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id))
    a.start()
    assert not a_started.wait(timeout=0.5), "Apply started while a decision was mid-write"
    d_release.set()
    d.join(timeout=20)
    a.join(timeout=20)
    assert a_started.is_set()
