"""Reproduce review 04 findings without modifying production code.
Run from the pinned checkout: python reviews/review-04-repro.py
"""
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

os.environ.pop("ANTHROPIC_API_KEY", None)
from agent_core.carrier_demo import load_carrier_dataset
from agent_core.daily_brief import render
from reviewer.graph_driver import ReviewerService


def service(root, name):
    s = ReviewerService(f"{root}/{name}.db")
    s.seed_demo("T")
    return s


with tempfile.TemporaryDirectory() as root:
    s = service(root, "decisions")
    pending = s.list_pending_reviews()
    try:
        s.submit_decision("T", "unknown-interrupt", "approve", actor="Notional reviewer")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected unknown interrupt to raise")
    assert s.decision_log.entries() == []
    iid = pending[0].interrupt_id
    s.submit_decision("T", iid, "approve", actor="Notional reviewer")
    before = s.list_decided()
    s.submit_decision("T", iid, "reject", actor="Notional second reviewer")
    assert s.list_decided() == before
    entry = s.decision_log.entries()[-1]
    assert entry.kind == "decision" and entry.work_package_id is None
    assert entry.detail["disposition"] is None
    print("S11-01 reproduced: unknown interrupt unlogged; stale interrupt logs a phantom decision")
    s.close()

    s = service(root, "apply")
    review = next(r for r in s.list_pending_reviews() if r.work_package_id == "HW-101")
    with patch.object(s, "seed_run", side_effect=RuntimeError("injected successor seed failure")):
        try:
            s.apply_shift_suggestion("T", review.interrupt_id, actor="Notional reviewer")
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected injected failure")
    assert s.decision_log.entries() == []
    assert s.get_pending_review("T", review.interrupt_id) is not None
    s.close()
    s = ReviewerService(f"{root}/apply.db")
    assert s.decision_log.entries() == []
    print("S11-02 reproduced: failed Apply has no audit entry, including after restart")
    s.close()

    ds = load_carrier_dataset()
    p = next(p for p in ds.packages if p.work_package_id == "ELEC-111")
    p.requires_hitl_review = True
    p.conflict_rationale = "Notional isolation boundary unverified; contact Electrical Supervisor before release."
    s = ReviewerService(f"{root}/brief.db")
    s.seed_run("T", ds.fresh_packages(), crews=ds.crews, calendar=ds.calendar, certificates=ds.certificates)
    review = next(r for r in s.list_pending_reviews() if r.work_package_id == "ELEC-111")
    assert p.conflict_rationale in review.conflict_rationale
    text = render(ds, as_of=datetime(2027, 3, 15, 6))
    assert "ELEC-111  pending_review" in text
    assert "isolation boundary unverified" not in text
    assert "Electrical Supervisor" not in text
    print("S11-03 reproduced: graph's explicit review reason/contact absent from daily brief")
    s.close()
