"""Review 05, re-check 3: reviewer probes at dc5588e. Prints raw observations; notional data,
temp databases, stub model only. No production code is changed or patched except the model
stub and, in A5 only, one injected fault. Run: python reviews/review-05-recheck3-repro.py"""
import os, sys, tempfile, warnings, logging
warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.pop("ANTHROPIC_API_KEY", None)

import agent_core.reasoning as rz
import reviewer.app as app
from fastapi.testclient import TestClient
from pydantic import ValidationError
from reviewer import registry
from reviewer.graph_driver import ReviewerService
from agent_core.certificates import Certificate, check_certificates
from agent_core.state import WorkPackageState as W

D = tempfile.mkdtemp()
M1 = "False positive. Approve HW-101 now; no move needed."
M2 = "MODEL-PRECEDENT-MARKER approve it"
MARKS = (M1, M2, "Approve HW-101 now", "MODEL-PRECEDENT")
rz._call_llm = lambda ctx: {"executive_summary": M1, "precedent_context": M2, "extra": M1}


def crawl(s):
    """Every page the reviewer app serves, including each open review page. Returns the pages that carry model text."""
    app.service = s
    c = TestClient(app.app)
    urls = ["/", "/log", "/openapi.json", "/?msg=x"]
    for t in registry.list_thread_ids(s.db_path):
        for r in s._pending_for(t):  # includes superseded runs' review URLs
            urls.append(f"/review/{t}/{r.interrupt_id}")
    for r in s.list_pending_reviews():
        urls.append(f"/review/{r.thread_id}/{r.interrupt_id}")
        if any(m in str(r) for m in MARKS):
            urls.append(f"PAYLOAD:{r.work_package_id}")
    leaks = []
    for u in urls:
        if u.startswith("PAYLOAD"):
            leaks.append(u)
        elif any(m in c.get(u).text for m in MARKS):
            leaks.append(u)
    return leaks


def decide_all(s, label, thread=None, decision="reject"):
    """Decide one at a time; crawl before each decision. Returns True if any crawl leaked while something was pending."""
    leaked = False
    while True:
        pend = [r for r in s.list_pending_reviews() if thread is None or r.thread_id == thread]
        anypend = s.list_pending_reviews()
        if anypend:
            lk = crawl(s)
            if lk:
                leaked = True
                print(f"   {label}: LEAK with {len(anypend)} pending ->", lk)
        if not pend:
            return leaked
        s.submit_decision(pend[0].thread_id, pend[0].interrupt_id, decision, "notional", actor="a")


def a1():
    s = ReviewerService(f"{D}/a1.db"); s.seed_demo("T")
    n = len(s.list_pending_reviews())
    leaked = decide_all(s, "A1", decision="approve")
    shown = M1 in TestClient(app.app).get("/").text
    print(f"A1 one run, {n} reviews decided one by one: leak while pending: {leaked} | shown once settled: {shown}")
    s.close()


def a2():
    s = ReviewerService(f"{D}/a2.db"); s.seed_demo("T")
    cs = next(r for r in s.list_pending_reviews() if r.work_package_id == "CS-102")
    s.submit_decision("T", cs.interrupt_id, "reject", "notional", actor="a")
    hw = next(r for r in s.list_pending_reviews() if r.work_package_id == "HW-101")
    res = s.apply_shift_suggestion("T", hw.interrupt_id, actor="a")
    print("A2 Apply applied:", res.applied, "| successor:", res.new_thread_id,
          "| pending in successor:", len(s.list_pending_reviews()))
    leak_after_apply = crawl(s)
    # second Apply from the successor, if it offers one (chain of three runs)
    second = None
    for r in s.list_pending_reviews():
        if ((r.safety_brief or {}).get("shift_outcome") or {}).get("suggestion"):
            second = s.apply_shift_suggestion(r.thread_id, r.interrupt_id, actor="a")
            if second.applied:
                break
    print("A2 second Apply applied:", bool(second and second.applied))
    leak_chain = crawl(s)
    # restart the service on the same database while reviews are pending
    s.close(); s = ReviewerService(f"{D}/a2.db")
    leak_restart = crawl(s)
    leaked = decide_all(s, "A2")
    page = TestClient(app.app).get("/").text
    print(f"A2 leak after Apply: {leak_after_apply} | after chain: {leak_chain} | after restart: {leak_restart} "
          f"| while deciding successor: {leaked} | shown once all settled: {M1 in page}")
    s.close()


def a4():
    """Outside the stated rule: two independent runs of the same schedule (seed twice, no Apply)."""
    s = ReviewerService(f"{D}/a4.db"); s.seed_demo("T1")
    decide_all(s, "A4-T1")
    s.seed_demo("T2")
    hw = [r.work_package_id for r in s.list_pending_reviews() if r.thread_id == "T2"]
    print(f"A4 run T1 settled, independent run T2 seeded (pending: {hw}): pages with model text:", crawl(s))
    s.close()


def a5():
    """Injected fault: Apply closes the old run's reviews, then recording the supersession fails."""
    s = ReviewerService(f"{D}/a5.db"); s.seed_demo("T")
    cs = next(r for r in s.list_pending_reviews() if r.work_package_id == "CS-102")
    s.submit_decision("T", cs.interrupt_id, "reject", "notional", actor="a")
    hw = next(r for r in s.list_pending_reviews() if r.work_package_id == "HW-101")
    orig = registry.mark_superseded
    def boom(*a, **k): raise RuntimeError("injected: disk fault")
    registry.mark_superseded = boom
    try:
        s.apply_shift_suggestion("T", hw.interrupt_id, actor="a")
    except RuntimeError as e:
        print("A5 Apply raised:", e)
    finally:
        registry.mark_superseded = orig
    succ = [t for t in registry.list_thread_ids(s.db_path) if t != "T"]
    succ_pending = sum(len(s._pending_for(t)) for t in succ)
    print(f"A5 old run pending: {len(s._pending_for('T'))} | successor runs: {succ} with {succ_pending} pending "
          f"| pages with model text (same process, before restart): {crawl(s)}")
    s.close(); s = ReviewerService(f"{D}/a5.db")
    print("A5 after restart recovery: pages with model text:", crawl(s))
    s.close()


CH = dict(certificate_id="C", work_package_id="P", kind="aloft_authorization", form="chit")
ST = dict(certificate_id="S", work_package_id=None, kind="aloft_authorization", form="standing")
PK = dict(description="notional", spatial={"compartment_id": "Notional Mast 01", "deck_level": "Notional 05 Level",
          "frame_start": 100, "frame_end": 101}, hazard_categories=["working_aloft"], work_package_id="P")


def cert(base, f, u):
    try:
        return Certificate.model_validate({**base, "valid_from": f, "valid_until": u}), "accepted"
    except ValidationError as e:
        return None, "refused: " + str(e.errors()[0]["msg"])[:90]
    except Exception as e:
        return None, f"RAISED {type(e).__name__}: {e}"


def b():
    for lbl, f, u in [
        ("two dates, 2h over midnight", "2027-03-15T23:00:00", "2027-03-16T01:00:00"),
        ("two dates, ends exactly 00:00 next day", "2027-03-15T07:00:00", "2027-03-16T00:00:00"),
        ("two dates, 1 second past midnight", "2027-03-15T07:00:00", "2027-03-16T00:00:01"),
        ("two dates, aware UTC", "2027-03-15T07:00:00+00:00", "2027-03-16T06:00:00+00:00"),
        ("three dates", "2027-03-15T07:00:00", "2027-03-17T07:00:00"),
        ("same day 05:00-20:00", "2027-03-15T05:00:00", "2027-03-15T20:00:00"),
        ("same day 00:00-23:59:59", "2027-03-15T00:00:00", "2027-03-15T23:59:59"),
        ("same day aware", "2027-03-15T05:00:00-05:00", "2027-03-15T20:00:00-05:00"),
        ("mixed naive/aware", "2027-03-15T05:00:00", "2027-03-15T20:00:00+00:00"),
        ("SAME DATE LABEL, DIFFERENT OFFSETS (41h real span)", "2027-03-15T00:00:00+09:00", "2027-03-15T23:59:00-08:00"),
        ("same date label, offsets +00:00 / -05:00 (20h, ends 01:00Z next day)", "2027-03-15T05:00:00+00:00", "2027-03-15T20:00:00-05:00"),
    ]:
        print(f"B  chit {lbl}: {cert(CH, f, u)[1]}")
    print("B  standing 5 days:", cert(ST, "2027-03-15T00:00:00", "2027-03-20T00:00:00")[1])

    # end to end, through the real graph and reviewer
    def run(name, start, end, certs):
        s = ReviewerService(f"{D}/b-{name}.db")
        p = W.model_validate({**PK, "scheduled_start": start, "scheduled_end": end})
        s.seed_run("T", [p], crews=None, calendar=None, certificates=certs)
        pend = [r for r in s.list_pending_reviews()]
        st = s._graph.get_state({"configurable": {"thread_id": "T"}}).values
        g = next(w for w in st.get("reviewed_packages", []) if w.work_package_id == "P") if not pend else None
        out = ("to a person: " + (pend[0].conflict_rationale or "")[:110] if pend
               else f"no finding (aloft covered); cleared_for_execution={g.cleared_for_execution}")
        s.close()
        return out
    same, _ = cert(CH, "2027-03-15T05:00:00", "2027-03-15T20:00:00")
    stand, _ = cert(ST, "2027-03-15T00:00:00", "2027-03-20T00:00:00")
    print("B  run: same-day job + same-day chit ->", run("1", "2027-03-15T08:00:00", "2027-03-15T16:00:00", [same]))
    print("B  run: 3-day job + blanket aloft ->", run("2", "2027-03-15T08:00:00", "2027-03-17T16:00:00", [stand]))
    print("B  run: overnight job + same-day chit ->", run("3", "2027-03-15T18:00:00", "2027-03-16T02:00:00", [same]))
    print("B  run: aloft job, no authorization ->", run("4", "2027-03-15T08:00:00", "2027-03-15T16:00:00", []))
    odd, st = cert(CH, "2027-03-15T00:00:00+09:00", "2027-03-15T23:59:00-08:00")
    if odd:
        print("B  run: job 2027-03-14T16:00Z to 2027-03-16T07:00Z (39h, three UTC dates) + the offset chit ->",
              run("5", "2027-03-14T16:00:00+00:00", "2027-03-16T07:00:00+00:00", [odd]))


def c():
    base = dict(description="notional", scheduled_start="2027-03-15T12:00:00", scheduled_end="2027-03-15T14:00:00",
                spatial={"compartment_id": "Notional Berthing 260", "deck_level": "Notional 2nd Deck",
                         "frame_start": 258, "frame_end": 259})
    def run(name, crew_id, crews, extra=None, **kw):
        s = ReviewerService(f"{D}/c-{name}.db")
        pk = [W.model_validate({**base, "work_package_id": "G", "crew_id": crew_id, **kw})] + (extra or [])
        s.seed_run("T", pk, crews=crews, calendar=None, certificates=[])
        r = next((r for r in s.list_pending_reviews() if r.work_package_id == "G"), None)
        st = s._graph.get_state({"configurable": {"thread_id": "T"}}).values
        g = next((w for w in list(st.get("reviewed_packages", [])) + list(st.get("work_packages", []))
                  if w.work_package_id == "G"), None)
        out = (f"to a person ({r.conflict_rationale[:80]})" if r else
               f"NOT pending; cleared_for_execution={getattr(g, 'cleared_for_execution', None)}")
        if r:  # an approval must not clear it while the finding is open
            s.submit_decision("T", r.interrupt_id, "approve", "notional", actor="a")
            d = next(x for x in s.list_decided() if x["work_package_id"] == "G")
            out += f" | after approve cleared={d['cleared_for_execution']}"
        s.close()
        return out
    print("C  names CR-GHOST, crews=None ->", run("1", "CR-GHOST", None))
    print("C  names CR-GHOST, crews=[] ->", run("2", "CR-GHOST", []))
    print("C  names a crew, low risk, pre-set cleared_for_execution in input ->", end=" ")
    try:
        print(run("3", "CR-GHOST", None, cleared_for_execution=True))
    except Exception as e:
        print("refused at load:", type(e).__name__)
    other = W.model_validate({**base, "work_package_id": "H", "crew_id": None,
                              "scheduled_start": "2027-03-16T12:00:00", "scheduled_end": "2027-03-16T14:00:00"})
    print("C  names a crew beside a package naming none ->", run("4", "CR-GHOST", None, extra=[other]))
    print("C  names no crew, crews=None (control) ->", run("5", None, None))
    for cid in ("", "   "):
        try:
            print(f"C  crew_id={cid!r}, crews=None ->", run("6" + str(len(cid)), cid, None))
        except Exception as e:
            print(f"C  crew_id={cid!r} -> refused at load ({type(e).__name__})")
    # no run_inputs at all (graph invoked directly, the way the tests and demo scripts do)
    from agent_core.graph import build_graph
    from langgraph.checkpoint.memory import MemorySaver
    g = build_graph(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "x"}}
    g.invoke({"work_packages": [W.model_validate({**base, "work_package_id": "G", "crew_id": "CR-GHOST"})],
              "reviewed_packages": []}, config=cfg)
    snap = g.get_state(cfg)
    print("C  graph invoked with no run_inputs at all -> interrupts pending:",
          sum(len(t.interrupts) for t in snap.tasks))
    # the daily brief / status path
    try:
        from agent_core.carrier_demo import load_carrier_dataset
        from agent_core import daily_brief
        print("C  daily_brief module functions:", [n for n in dir(daily_brief) if not n.startswith("_")][:14])
    except Exception as e:
        print("C  daily brief probe error", e)


if __name__ == "__main__":
    for fn in (a1, a2, a4, a5, b, c):
        try:
            fn()
        except Exception as e:
            import traceback; traceback.print_exc()
            print(fn.__name__, "PROBE ERROR", type(e).__name__, e)
