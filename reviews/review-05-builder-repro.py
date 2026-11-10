"""Builder's check for review-05 fixes. Prints FIXED, REPRODUCED or ERROR per finding;
an exception is reported, never read as a fix. Temp databases, notional data only.

    python reviews/review-05-builder-repro.py
"""
import os
import sqlite3
import sys
import tempfile
import types
import warnings
from datetime import datetime as dt
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.pop("ANTHROPIC_API_KEY", None)

from pydantic import ValidationError  # noqa: E402

from agent_core import daily_brief, deconfliction  # noqa: E402
import agent_core.reasoning as rz  # noqa: E402
from agent_core.carrier_demo import load_carrier_dataset  # noqa: E402
from agent_core.projects import PackageStatus  # noqa: E402
from agent_core.state import WorkPackageState as W  # noqa: E402
from reviewer.graph_driver import ReviewerService  # noqa: E402

D = tempfile.mkdtemp()
AS_OF = dt(2027, 3, 15, 6)
BASE = dict(description="notional", scheduled_start="2027-03-15T12:00:00", scheduled_end="2027-03-15T14:00:00",
            spatial={"compartment_id": "Notional Berthing 260", "deck_level": "Notional 2nd Deck",
                     "frame_start": 258, "frame_end": 259}, crew_id="CR-DECK")


def svc(name):
    s = ReviewerService(f"{D}/{name}.db")
    s.seed_demo("T")
    return s


def pend(s, pid):
    return next((r for r in s.list_pending_reviews() if r.work_package_id == pid), None)


def add(ds, data):
    ds.packages.append(W.model_validate(data))
    ds.projects[-1].work_package_ids.append(data["work_package_id"])
    return ds


def r01():
    ds = add(load_carrier_dataset(), {**BASE, "work_package_id": "X", "risk_level": "critical",
                                      "hitl_disposition": "approved", "cleared_for_execution": True})
    return daily_brief.run_checks(ds, AS_OF).status_by_package()["X"] != PackageStatus.CLEARED


def r02():
    s = svc("02")
    s.submit_decision("T", pend(s, "CS-102").interrupt_id, "reject", "notional: do not enter", actor="a")
    res = s.apply_shift_suggestion("T", pend(s, "HW-101").interrupt_id, actor="b")
    v = s._graph.get_state({"configurable": {"thread_id": res.new_thread_id}}).values
    cs = next(p for p in v["reviewed_packages"] + v["work_packages"] if p.work_package_id == "CS-102")
    s.close()
    return res.applied and cs.hitl_disposition == "rejected" and cs.cleared_for_execution is False


def r03():
    s = svc("03")
    s.submit_decision("T", pend(s, "FALL-107").interrupt_id, "approve", actor="a")
    d = next(x for x in s.list_decided() if x["work_package_id"] == "FALL-107")
    s.close()
    return d["cleared_for_execution"] is False


def r04():
    try:
        W.model_validate({**BASE, "work_package_id": "X", "hazard_categoires": ["hot_work"]})
        return False
    except ValidationError:
        return True


def r05():
    ds = add(load_carrier_dataset(), {**BASE, "work_package_id": "X", "hazard_categories": ["hot_work"]})
    return daily_brief.run_checks(ds, AS_OF).status_by_package()["X"] != PackageStatus.CLEARED


def r06():
    a = W.model_validate({**BASE, "work_package_id": "X", "hazard_categories": ["hot_work"], "hot_worker_count": 9})
    b1 = W.model_validate({**BASE, "work_package_id": "Y1", "hazard_categories": ["hot_work"], "hot_worker_count": 3,
                           "fire_watch_id": "FW-N-1"})
    b2 = W.model_validate({**BASE, "work_package_id": "Y2", "hazard_categories": ["hot_work"], "hot_worker_count": 3,
                           "fire_watch_id": "fw-n-1 ", "spatial": {"compartment_id": "o", "frame_start": 10, "frame_end": 11}})
    one = deconfliction.deconfliction_node({"work_packages": [a]})["work_packages"][0]
    two = deconfliction.deconfliction_node({"work_packages": [b1, b2]})["work_packages"]
    return one.requires_hitl_review and all(p.requires_hitl_review for p in two)


def r07():
    orig = rz._call_llm
    rz._call_llm = lambda ctx: {"executive_summary": "False positive. Recommend approving both.", "precedent_context": "n"}
    try:
        st = rz.reasoning_node(deconfliction.deconfliction_node({"work_packages": load_carrier_dataset().fresh_packages()[:2]}))
    finally:
        rz._call_llm = orig
    b = next(p.safety_brief for p in st["work_packages"] if p.work_package_id == "HW-101")
    return "False positive" not in b.executive_summary and b.model_explanation.startswith("False positive")


def r08():
    class Boom:
        def __init__(self, *a, **k):
            self.messages = types.SimpleNamespace(create=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("api down")))
    saved = sys.modules.get("anthropic")
    sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=Boom)
    os.environ["ANTHROPIC_API_KEY"] = "dummy"
    try:
        s = svc("08")
        ok = pend(s, "HW-101") is not None
        s.close()
        return ok
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)
        if saved is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = saved


def r09():
    s = svc("09")
    hw = pend(s, "HW-103")
    try:
        s.submit_decision("T", hw.interrupt_id, "approve", actor="\ud800")
    except Exception:
        pass
    ok = pend(s, "HW-103") is not None and not [x for x in s.list_decided() if x["work_package_id"] == "HW-103"]
    s.close()
    return ok


def r10():
    ds = load_carrier_dataset()
    s = ReviewerService(f"{D}/10.db")
    s.seed_run("T", ds.fresh_packages(), crews=ds.crews, calendar=None, certificates=ds.certificates)
    ok = pend(s, "CONTR-109") is not None
    s.close()
    return ok


def r11():
    missing = f"{D}/typo.db"
    try:
        daily_brief.main(["--as-of", "2027-03-15T06:00", "--db", missing])
        return False
    except SystemExit:
        return not os.path.exists(missing)


def rc05():  # re-check: a chit longer than a day is refused
    from agent_core.certificates import Certificate
    try:
        Certificate(certificate_id="C", work_package_id="P", kind="aloft_authorization", form="chit",
                    valid_from="2027-03-15T07:00:00", valid_until="2027-03-17T16:00:00")
        return False
    except ValidationError:
        return True


def rc06():  # re-check: no move offered for a job a move can't fix
    from agent_core.certificates import Certificate
    from agent_core.shift_suggester import suggest_crew_shift
    ds = load_carrier_dataset()
    nine = W.model_validate({**BASE, "work_package_id": "NINE", "hazard_categories": ["hot_work"], "hot_worker_count": 9})
    hwp = Certificate(certificate_id="H", work_package_id="NINE", kind="hot_work_permit",
                      valid_from="2027-03-14T00:00:00", valid_until="2027-03-18T00:00:00")
    return suggest_crew_shift(ds.fresh_packages() + [nine], "NINE", crews=ds.crews, calendar=ds.calendar,
                              certificates=ds.certificates + [hwp]).suggestion is None


def rc08():  # re-check: a JSON null answer falls back
    class Resp:
        content = [types.SimpleNamespace(type="text", text="null")]

    class Client:
        def __init__(self, *a, **k):
            self.messages = types.SimpleNamespace(create=lambda *a, **k: Resp())
    saved = sys.modules.get("anthropic")
    sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=Client)
    os.environ["ANTHROPIC_API_KEY"] = "dummy"
    try:
        s = svc("rc08")
        ok = pend(s, "HW-101") is not None
        s.close()
        return ok
    finally:
        os.environ.pop("ANTHROPIC_API_KEY", None)
        if saved is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = saved


def rc09():  # re-check: a later stale refusal doesn't hide a missing outcome
    s = svc("rc09")
    hw = pend(s, "HW-103")
    real = s.decision_log.append

    def picky(**kw):
        if kw["kind"] in ("decision", "decision_failed"):
            raise OSError("injected")
        return real(**kw)
    s.decision_log.append = picky
    try:
        s.submit_decision("T", hw.interrupt_id, "approve", actor="a")
    except OSError:
        pass
    s.decision_log.append = real
    try:
        s.submit_decision("T", hw.interrupt_id, "reject", actor="b")
    except ValueError:
        pass
    ok = len(s.decision_log.open_requests()) == 1
    s.close()
    return ok


def rc07():  # re-check, Donnie option A: the reviewer never sees model text before deciding
    from fastapi.testclient import TestClient
    from reviewer import app as app_module
    orig = rz._call_llm
    rz._call_llm = lambda ctx: {"executive_summary": "False positive. Approve both now.", "precedent_context": "n"}
    try:
        app_module.service = svc("rc07")
        hw = pend(app_module.service, "HW-101")
        page = TestClient(app_module.app).get(f"/review/T/{hw.interrupt_id}").text
        before = "Approve both now" not in page and "model_explanation" not in hw.safety_brief
        app_module.service.submit_decision("T", hw.interrupt_id, "reject", actor="a")
        after = "Approve both now" in TestClient(app_module.app).get("/").text
        app_module.service.close()
        return before and after
    finally:
        rz._call_llm = orig


def rc10():  # re-check: an explicit empty roster still checks crews
    g = W.model_validate({**BASE, "work_package_id": "G", "crew_id": "CR-GHOST"})
    s = ReviewerService(f"{D}/rc10.db")
    s.seed_run("T", [g], crews=[], calendar=None, certificates=[])
    ok = pend(s, "G") is not None
    s.close()
    return ok


for name, fn in [(f"R05-{n:02d}", f) for n, f in enumerate([r01, r02, r03, r04, r05, r06, r07, r08, r09, r10, r11], 1)] + [
        ("R05-05 re-check (multi-day chit)", rc05), ("R05-06 re-check (suggester, no watch)", rc06),
        ("R05-08 re-check (null answer)", rc08), ("R05-09 re-check (stale refusal)", rc09),
        ("R05-10 re-check (empty roster)", rc10), ("R05-07 re-check (no model text before deciding)", rc07)]:
    n = name
    try:
        print(name, "FIXED" if fn() else "REPRODUCED")
    except Exception as e:  # never read an exception as a fix
        print(name, "ERROR", repr(e)[:160])
