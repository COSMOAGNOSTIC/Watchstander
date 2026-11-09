"""Builder's check for review-04 fixes. Each scenario prints FIXED, REPRODUCED or ERROR;
an exception is reported, never mistaken for a fix. Temp databases, notional data.

    python reviews/review-04-builder-repro.py
"""
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.pop("ANTHROPIC_API_KEY", None)

from agent_core import daily_brief  # noqa: E402
from agent_core.carrier_demo import load_carrier_dataset  # noqa: E402
from reviewer.graph_driver import ReviewerService  # noqa: E402

D = tempfile.mkdtemp()


def pending(s, pid):
    return next(r for r in s.list_pending_reviews() if r.work_package_id == pid)


def s11_01():
    s = ReviewerService(f"{D}/a.db"); s.seed_demo("T")
    try:
        s.submit_decision("T", "no-such-interrupt", "approve", actor="a")
    except ValueError:
        pass
    hw = pending(s, "HW-101")
    s.submit_decision("T", hw.interrupt_id, "approve", actor="a")
    try:
        s.submit_decision("T", hw.interrupt_id, "reject", actor="b")
    except ValueError:
        pass
    entries = s.decision_log.entries(); s.close()
    bad_decisions = [e for e in entries if e.kind == "decision" and e.detail.get("disposition") is None]
    refused = [e for e in entries if e.kind == "decision_refused"]
    return not bad_decisions and len(refused) == 2


def s11_02():
    s = ReviewerService(f"{D}/b.db"); s.seed_demo("T")
    hw = pending(s, "HW-101")
    real = ReviewerService.seed_run

    def boom(self, tid, *a, **k):
        if tid != "T":
            raise RuntimeError("injected")
        return real(self, tid, *a, **k)

    ReviewerService.seed_run = boom
    try:
        s.apply_shift_suggestion("T", hw.interrupt_id, actor="a")
    except RuntimeError:
        pass
    finally:
        ReviewerService.seed_run = real
    s.close()
    s2 = ReviewerService(f"{D}/b.db"); kinds = [e.kind for e in s2.decision_log.entries()]; s2.close()
    return kinds == ["apply_failed"]


def s11_03():
    ds = load_carrier_dataset()
    i = next(n for n, p in enumerate(ds.packages) if p.work_package_id == "ELEC-111")
    ds.packages[i] = ds.packages[i].model_copy(update={
        "requires_hitl_review": True,
        "conflict_rationale": "Notional isolation boundary unverified; contact Electrical Supervisor before release."})
    text = daily_brief.render(ds, as_of=datetime(2027, 3, 15, 6))
    return "isolation boundary" in text and "Electrical Supervisor" in text


def _first_read_fault(op):
    db = f"{D}/first-{op}.db"
    s = ReviewerService(db); s.seed_demo("T")
    hw = pending(s, "HW-101")
    real = s._graph.get_state

    def boom(*a, **k):
        raise OSError("injected first-read failure")

    s._graph.get_state = boom
    try:
        if op == "decide":
            s.submit_decision("T", hw.interrupt_id, "approve", actor="a")
        else:
            s.apply_shift_suggestion("T", hw.interrupt_id, actor="a")
    except OSError:
        pass
    finally:
        s._graph.get_state = real
    s.close()
    s2 = ReviewerService(db); kinds = [e.kind for e in s2.decision_log.entries()]; s2.close()
    return kinds == ["decision_failed" if op == "decide" else "apply_failed"]


for name, fn in [("S11-01", s11_01), ("S11-02", s11_02), ("S11-03", s11_03),
                 ("S11-01 re-check (first read fails)", lambda: _first_read_fault("decide")),
                 ("S11-02 re-check (first read fails)", lambda: _first_read_fault("apply"))]:
    try:
        print(name, "FIXED" if fn() else "REPRODUCED")
    except Exception as e:  # never read an exception as a fix
        print(name, "ERROR", repr(e))
