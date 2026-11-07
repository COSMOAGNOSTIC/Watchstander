"""Builder's independent reproduction of review-03 (Session 8) findings S08-01..06.
Rebuilt from the reviewer's descriptions. Each probe is isolated and uses its own temp
database; an exception is reported as ERROR, never as fixed. Run from the repo root.
"""
import importlib
import os
import sys
import tempfile
import threading
from datetime import date, datetime as dt, time

os.environ.pop("ANTHROPIC_API_KEY", None)

from agent_core.certificates import Certificate, CertificateKind as K
from agent_core.crews import Crew, ShiftCalendar
from agent_core.judgment import judgment_flags
from agent_core.state import HazardCategory as H, HitlDisposition, SafetyPermitsRequired, SpatialCoordinates as SC, WorkPackageState as W
from reviewer import graph_driver
from reviewer.graph_driver import ReviewerService

PATTERN = [("DAY", time(7), time(15, 30)), ("SWING", time(15, 30), time(0)), ("MID", time(0), time(7))]
CAL = ShiftCalendar.from_daily_pattern(date(2027, 1, 12), 3, PATTERN)
CREWS = [Crew(crew_id="CR-WELD", name="n"), Crew(crew_id="CR-TANK", name="n")]
results = {}


def d(h, m=0):
    return dt(2027, 1, 12, h, m)


def pair(**weld_kw):
    return [W(work_package_id="WELD-1", description="n", hazard_categories=[H.HOT_WORK], spatial=SC(compartment_id="TANK-4"),
              scheduled_start=d(7), scheduled_end=d(11), crew_id="CR-WELD", **weld_kw),
            W(work_package_id="TANK-ENTRY", description="n", hazard_categories=[H.CONFINED_SPACE], spatial=SC(compartment_id="TANK-4"),
              scheduled_start=d(7), scheduled_end=d(15), crew_id="CR-TANK")]


def svc():
    return ReviewerService(os.path.join(tempfile.mkdtemp(), "r.db"))


def probe(rid):
    def deco(fn):
        try:
            ok, obs = fn()
            results[rid] = ok
            print(f"{rid}: {'REPRODUCED' if ok else 'NOT REPRODUCED'} -- {obs}")
        except Exception as e:
            results[rid] = None
            print(f"{rid}: ERROR -- {type(e).__name__}: {e}")
        return fn
    return deco


@probe("S08-01")
def _():
    s = svc()
    s.seed_run("T1", pair(), crews=CREWS, calendar=CAL, certificates=[])
    pend = {r.work_package_id: r for r in s.list_pending_reviews()}
    real = graph_driver.suggest_crew_shift
    barrier = threading.Barrier(2)

    def slow(*a, **k):
        out = real(*a, **k)
        barrier.wait(timeout=10)
        return out

    graph_driver.suggest_crew_shift = slow
    s2 = ReviewerService(s.db_path)
    res = {}
    try:
        ts = [threading.Thread(target=lambda key, sv: res.__setitem__(key, sv.apply_shift_suggestion("T1", pend[key].interrupt_id)),
                               args=(k, sv)) for k, sv in (("WELD-1", s), ("TANK-ENTRY", s2))]
        [t.start() for t in ts]
        [t.join() for t in ts]
    finally:
        graph_driver.suggest_crew_shift = real
    applied = [k for k, r in res.items() if r.applied]
    return len(applied) == 2, f"both Applies succeeded: {applied}; successors={[r.new_thread_id for r in res.values()]}"


@probe("S08-02")
def _():
    s = svc()
    s.seed_run("T1", pair(), crews=CREWS, calendar=CAL, certificates=[])
    weld = next(r for r in s.list_pending_reviews() if r.work_package_id == "WELD-1")
    orig = ReviewerService.submit_decision
    ReviewerService.submit_decision = lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("injected checkpoint failure"))
    try:
        try:
            s.apply_shift_suggestion("T1", weld.interrupt_id)
        except RuntimeError:
            pass
    finally:
        ReviewerService.submit_decision = orig
    s.close()
    s = ReviewerService(s.db_path)
    old = [r for r in s.list_pending_reviews() if r.thread_id == "T1"]
    if not old:
        return False, "old run not reviewable after restart"
    s.submit_decision("T1", next(r for r in old if r.work_package_id == "WELD-1").interrupt_id, "approve")
    cleared = [x for x in s.list_decided() if x["thread_id"] == "T1" and x["cleared_for_execution"]]
    return bool(cleared), f"after interrupted Apply + restart: {len(old)} old reviews still open; old WELD-1 approved and cleared={bool(cleared)}"


@probe("S08-03")
def _():
    s = svc()
    s.seed_run("T1", pair(hitl_disposition=HitlDisposition.APPROVED, cleared_for_execution=True), crews=CREWS, calendar=CAL, certificates=[])
    weld = next(r for r in s.list_pending_reviews() if r.work_package_id == "WELD-1")
    res = s.apply_shift_suggestion("T1", weld.interrupt_id)
    moved = next(p for p in s.run_inputs(res.new_thread_id)["packages"] if p["work_package_id"] == "WELD-1")
    return moved["hitl_disposition"] == "approved" and moved["cleared_for_execution"], \
        f"moved WELD-1 in new run: disposition={moved['hitl_disposition']}, cleared={moved['cleared_for_execution']}, requires_review={moved['requires_hitl_review']}"


@probe("S08-04")
def _():
    p = W(work_package_id="ALOFT", description="n", hazard_categories=[H.WORKING_ALOFT], spatial=SC(),
          scheduled_start=d(7), scheduled_end=d(11), crew_id="CR-WELD")
    flags = [f.rule_id for f in judgment_flags([p])]
    s = svc()
    s.seed_run("T1", [p], crews=CREWS, calendar=CAL, certificates=[])
    pending = s.list_pending_reviews()
    return "WS-JF-006" in flags and not pending, f"judgment_flags={flags}; pending reviews after seed_run={len(pending)}"


@probe("S08-05")
def _():
    from fastapi.testclient import TestClient
    from reviewer import app as app_module
    pkgs = pair(permits_required=SafetyPermitsRequired(hot_work_permit=True))
    cert = Certificate(certificate_id="HW-1", work_package_id="WELD-1", kind=K.HOT_WORK_PERMIT, valid_from=d(7), valid_until=d(11))
    app_module.service = svc()
    app_module.service.seed_run("T1", pkgs, crews=CREWS, calendar=CAL, certificates=[cert])
    weld = next(r for r in app_module.service.list_pending_reviews() if r.work_package_id == "WELD-1")
    stored = {rid for r in weld.safety_brief["shift_outcome"]["rejected"] for rid in r["rule_ids"]}
    page = TestClient(app_module.app).get(f"/review/T1/{weld.interrupt_id}").text
    return "WS-CT-001" in stored and "WS-CT-001" not in page, f"stored rejection rules={sorted(stored)}; WS-CT-001 on page={'WS-CT-001' in page}"


@probe("S08-06")
def _():
    sys.path.insert(0, "tests")
    t = importlib.import_module("test_session08b")
    from agent_core import reasoning
    orig = reasoning.describe_shift_outcome
    reasoning.describe_shift_outcome = lambda o: "Suggested, not applied: fabricated move"
    try:
        s = svc()
        t.test_brief_explains_when_there_is_no_suggestion(s)
        passed = True
    except AssertionError:
        passed = False
    finally:
        reasoning.describe_shift_outcome = orig
    return passed, f"no-suggestion test passed with fabricated suggestion text: {passed}"


print(f"\nreproduced: {sorted(k for k, v in results.items() if v)}")
print(f"not reproduced: {sorted(k for k, v in results.items() if v is False)}")
print(f"errors: {sorted(k for k, v in results.items() if v is None)}")
