"""Review 05, re-check 2: reviewer probes at 09f9532. Prints raw observations; notional data,
temp databases, stub model only. P1 is the reopened R05-07 path (expect "dashboard shows model
verdict: True" until fixed). Run: python reviews/review-05-recheck2-repro.py"""
import os, sys, tempfile, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.pop("ANTHROPIC_API_KEY", None)
from datetime import datetime as dt

import agent_core.reasoning as rz
from reviewer.graph_driver import ReviewerService
from agent_core.state import WorkPackageState as W
from agent_core.certificates import Certificate
from pydantic import ValidationError

D = tempfile.mkdtemp()
VERDICT = "False positive. Approve HW-101 now; no move needed."


def pend(s, t, pid):
    return next((r for r in s.list_pending_reviews() if r.thread_id == t and r.work_package_id == pid), None)


# P1: R05-07 -- model text of a decided package on the dashboard, beside its pending partner.
def p1():
    orig = rz._call_llm
    rz._call_llm = lambda ctx: {"executive_summary": VERDICT, "precedent_context": "model precedent"}
    try:
        s = ReviewerService(f"{D}/p1.db")
        s.seed_demo("T")
    finally:
        rz._call_llm = orig
    hw = pend(s, "T", "HW-101")
    cs = pend(s, "T", "CS-102")
    print("P1 review page payload for HW-101 has model text:",
          VERDICT in str(hw.safety_brief))
    s.submit_decision("T", cs.interrupt_id, "reject", "notional", actor="a")
    import reviewer.app as app
    app.service = s
    from fastapi.testclient import TestClient
    c = TestClient(app.app)
    page = c.get("/").text
    still = pend(s, "T", "HW-101") is not None
    print("P1 HW-101 still pending:", still, "| dashboard shows model verdict:", VERDICT in page)
    detail = c.get(f"/review/T/{hw.interrupt_id}").text
    print("P1 HW-101 review page shows model verdict:", VERDICT in detail)
    s.close()


# P2: R05-05 -- chit shapes.
def p2():
    base = dict(certificate_id="C", work_package_id="A", kind="aloft_authorization", form="chit")
    for lbl, f, u in [("25h", "2027-03-15T07:00:00", "2027-03-16T08:00:00"),
                      ("24h", "2027-03-15T07:00:00", "2027-03-16T07:00:00"),
                      ("overnight 23h", "2027-03-15T08:00:00", "2027-03-16T07:00:00"),
                      ("mixed tz", "2027-03-15T07:00:00+00:00", "2027-03-17T07:00:00")]:
        try:
            Certificate.model_validate({**base, "valid_from": f, "valid_until": u})
            print("P2", lbl, "accepted")
        except ValidationError as e:
            print("P2", lbl, "refused (ValidationError)")
        except Exception as e:
            print("P2", lbl, "raised", type(e).__name__, e)


# P3: R05-10 -- crews=None with a package naming a crew that doesn't exist.
def p3():
    pkg = W.model_validate(dict(work_package_id="G-1", description="notional",
        scheduled_start="2027-03-15T12:00:00", scheduled_end="2027-03-15T14:00:00",
        spatial={"compartment_id": "Notional Berthing 260", "deck_level": "Notional 2nd Deck",
                 "frame_start": 258, "frame_end": 259}, crew_id="CR-GHOST"))
    for crews in (None, []):
        s = ReviewerService(f"{D}/p3{crews is None}.db")
        s.seed_run("T", [pkg.model_copy(deep=True)], crews=crews, calendar=None)
        print(f"P3 crews={crews!r}: pending:", pend(s, "T", "G-1") is not None)
        s.close()


# P4: R05-09 -- request_seq: stale refusal no longer closes the open request.
def p4():
    s = ReviewerService(f"{D}/p4.db")
    s.seed_demo("T")
    r = pend(s, "T", "HW-103")
    real = s.decision_log.append
    def flaky(**kw):
        if kw["kind"] in ("decision", "decision_failed"):
            raise OSError("notional disk full")
        return real(**kw)
    s.decision_log.append = flaky
    try:
        s.submit_decision("T", r.interrupt_id, "approve", actor="a")
    except Exception:
        pass
    s.decision_log.append = real
    before = len(s.decision_log.open_requests())
    try:
        s.submit_decision("T", r.interrupt_id, "reject", actor="b")
    except ValueError:
        pass
    after = len(s.decision_log.open_requests())
    print("P4 open requests before/after stale reject:", before, after,
          "| chain ok:", s.decision_log.verify_chain() is not None)
    s.close()


# P5: R05-08 -- odd model answers through the whole seed path.
def p5():
    shapes = [None, [], "x", {"executive_summary": "ok"},
              {"executive_summary": " ", "precedent_context": "p"},
              {"executive_summary": {"a": 1}, "precedent_context": "p"}]
    orig = rz._call_llm
    for i, ret in enumerate(shapes):
        rz._call_llm = lambda ctx, r=ret: r
        try:
            s = ReviewerService(f"{D}/p5_{i}.db")
            s.seed_demo("T")
            print("P5", repr(ret)[:40], "pending:", len(s.list_pending_reviews()))
            s.close()
        except Exception as e:
            print("P5", repr(ret)[:40], "RAISED", type(e).__name__)
    rz._call_llm = orig


for f in (p1, p2, p3, p4, p5):
    try:
        f()
    except Exception as e:
        print(f.__name__, "ERROR", type(e).__name__, e)
