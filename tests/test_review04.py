"""review-04 (Session 11) regressions. Real graph, real ReviewerService, temp sqlite.
All data notional (the carrier dataset).
"""

from datetime import datetime

import pytest

from agent_core import daily_brief
from agent_core.carrier_demo import load_carrier_dataset
from reviewer.graph_driver import ReviewerService

AS_OF = datetime(2027, 3, 15, 6, 0)


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def svc(tmp_path):
    s = ReviewerService(str(tmp_path / "r.db"))
    s.seed_demo("T")
    yield s
    s.close()


def _pending(s, pid):
    return next(r for r in s.list_pending_reviews() if r.work_package_id == pid)


def _outcomes(s):
    # review-05 R05-09: a "*_requested" entry now precedes any attempt that reaches the graph;
    # the review-04 promise is about outcomes: exactly one per attempt.
    return [e for e in s.decision_log.entries() if not e.kind.endswith("_requested")]


def _kinds(s):
    return [e.kind for e in _outcomes(s)]


# --- S11-01: every submit_decision outcome is logged as what actually happened ---------------


def test_s11_01_unknown_interrupt_is_refused_and_logged(svc):
    with pytest.raises(ValueError, match="no pending review"):
        svc.submit_decision("T", "no-such-interrupt", "approve", actor="Casey Sample")
    [e] = _outcomes(svc)
    assert e.kind == "decision_refused" and e.actor == "Casey Sample"
    assert "no pending review" in e.detail["reason"]


def test_s11_01_stale_resubmission_is_refused_not_logged_as_a_decision(svc):
    hw = _pending(svc, "HW-101")
    svc.submit_decision("T", hw.interrupt_id, "approve", actor="Casey Sample")
    with pytest.raises(ValueError, match="no pending review"):
        svc.submit_decision("T", hw.interrupt_id, "reject", actor="Riley Example")
    decisions = [e for e in svc.decision_log.entries() if e.kind == "decision"]
    assert len(decisions) == 1 and decisions[0].detail["disposition"] == "approved"
    assert _kinds(svc) == ["decision", "decision_refused"]


def test_s11_01_a_graph_error_is_logged_as_failed_and_reraised(svc, monkeypatch):
    hw = _pending(svc, "HW-101")
    monkeypatch.setattr(ReviewerService, "_resume", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected")))
    with pytest.raises(RuntimeError, match="injected"):
        svc.submit_decision("T", hw.interrupt_id, "approve", actor="Casey Sample")
    [e] = _outcomes(svc)
    assert e.kind == "decision_failed" and e.work_package_id == "HW-101" and "injected" in e.detail["error"]


def test_s11_01_no_stored_disposition_is_never_logged_as_a_decision(svc, monkeypatch):
    hw = _pending(svc, "HW-101")
    monkeypatch.setattr(ReviewerService, "_resume", lambda *a, **k: None)  # graph silently did nothing
    with pytest.raises(RuntimeError, match="no disposition"):
        svc.submit_decision("T", hw.interrupt_id, "approve", actor="Casey Sample")
    assert _kinds(svc) == ["decision_failed"]


def test_s11_01_the_web_form_reports_a_stale_submission(tmp_path):
    from fastapi.testclient import TestClient
    from reviewer import app as app_module
    app_module.service = ReviewerService(str(tmp_path / "ui.db"))
    app_module.service.seed_demo("T")
    hw = _pending(app_module.service, "HW-101")
    client = TestClient(app_module.app)
    client.post(f"/review/T/{hw.interrupt_id}", data={"decision": "approve", "note": "", "actor": "a"})
    resp = client.post(f"/review/T/{hw.interrupt_id}", data={"decision": "reject", "note": "", "actor": "b"})
    assert resp.status_code == 200 and "Decision not recorded" in resp.text


# --- S11-02: every Apply outcome is logged, including an exception -----------------------------


def test_s11_02_apply_exception_is_logged_and_survives_restart(svc, monkeypatch):
    hw = _pending(svc, "HW-101")
    real_seed = ReviewerService.seed_run

    def boom(self, tid, *a, **k):
        if tid != "T":
            raise RuntimeError("injected")
        return real_seed(self, tid, *a, **k)

    monkeypatch.setattr(ReviewerService, "seed_run", boom)
    with pytest.raises(RuntimeError, match="injected"):
        svc.apply_shift_suggestion("T", hw.interrupt_id, actor="Riley Example")
    monkeypatch.undo()
    [e] = _outcomes(svc)
    assert e.kind == "apply_failed" and e.actor == "Riley Example" and e.work_package_id == "HW-101"
    assert "injected" in e.detail["error"] and e.detail["apply_marker_left"] is False
    db = svc.db_path
    svc.close()
    s2 = ReviewerService(db)
    assert _kinds(s2) == ["apply_failed"]
    assert any(r.work_package_id == "HW-101" for r in s2.list_pending_reviews())
    s2.close()


def test_s11_02_apply_failure_after_the_successor_exists_says_recovery_will_finish_it(tmp_path, monkeypatch):
    s = ReviewerService(str(tmp_path / "c.db"))
    s.seed_demo("T")
    hw = _pending(s, "HW-101")
    monkeypatch.setattr(ReviewerService, "_close_superseded_reviews",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        s.apply_shift_suggestion("T", hw.interrupt_id)
    [e] = _outcomes(s)
    assert e.kind == "apply_failed" and e.detail["apply_marker_left"] is True
    monkeypatch.undo()
    s.close()
    s2 = ReviewerService(s.db_path)
    kinds = _kinds(s2)
    assert kinds[0] == "apply_failed" and "recovered" in kinds
    s2.close()


# --- S11-03: the brief carries the routing reason the graph carries ---------------------------


def _with_input_rationale():
    ds = load_carrier_dataset()
    i = next(n for n, p in enumerate(ds.packages) if p.work_package_id == "ELEC-111")
    ds.packages[i] = ds.packages[i].model_copy(update={
        "requires_hitl_review": True,
        "conflict_rationale": "Notional isolation boundary unverified; contact Electrical Supervisor before release."})
    return ds


def test_s11_03_brief_shows_an_input_routing_rationale_and_contact():
    text = daily_brief.render(_with_input_rationale(), as_of=AS_OF)
    block = text[text.index("  ELEC-111"):text.index("\n\nJUDGMENT FLAGS")]
    assert "Why: Notional isolation boundary unverified; contact Electrical Supervisor before release." in block


def test_s11_03_pending_with_no_rule_and_no_note_says_so():
    ds = load_carrier_dataset()
    i = next(n for n, p in enumerate(ds.packages) if p.work_package_id == "ELEC-111")
    ds.packages[i] = ds.packages[i].model_copy(update={"requires_hitl_review": True})
    text = daily_brief.render(ds, as_of=AS_OF)
    block = text[text.index("  ELEC-111"):text.index("\n\nJUDGMENT FLAGS")]
    assert "no reason was recorded" in block


@pytest.mark.parametrize("ds_factory", [load_carrier_dataset, _with_input_rationale])
def test_s11_03_every_package_needing_a_person_shows_a_rule_or_a_reason(ds_factory):
    text = daily_brief.render(ds_factory(), as_of=AS_OF)
    section = text[text.index("NEEDS A PERSON\n"):text.index("\n\nJUDGMENT FLAGS")]
    import re
    blocks = re.split(r"\n  (?=\S)", section)[1:]  # one block per package line
    assert blocks
    for b in blocks:
        assert "WS-" in b or "Why:" in b, b


# --- re-check: an exception at ANY step, including the first read, is logged exactly once -----

_FAULT_POINTS = ["_pending_for", "_closed_to_decisions", "get_pending_review", "run_inputs", "_resume"]


def _inject(monkeypatch, svc, point):
    def boom(*a, **k):
        raise OSError(f"injected at {point}")
    if point == "get_state":
        monkeypatch.setattr(svc._graph, "get_state", boom)
    else:
        monkeypatch.setattr(ReviewerService, point, boom)


@pytest.mark.parametrize("point", ["get_state"] + _FAULT_POINTS)
def test_recheck_any_decision_fault_logs_exactly_one_failed_entry(svc, monkeypatch, point):
    hw = _pending(svc, "HW-101")
    _inject(monkeypatch, svc, point)
    try:
        svc.submit_decision("T", hw.interrupt_id, "approve", actor="Casey Sample")
    except Exception:
        pass
    monkeypatch.undo()
    entries = _outcomes(svc)
    assert len(entries) == 1, [e.kind for e in entries]
    if entries[0].kind != "decision":  # a fault in a step the path never reached is fine
        assert entries[0].kind in ("decision_failed", "decision_refused") and entries[0].actor == "Casey Sample"


@pytest.mark.parametrize("point", ["get_state"] + _FAULT_POINTS)
def test_recheck_any_apply_fault_logs_exactly_one_entry(svc, monkeypatch, point):
    hw = _pending(svc, "HW-101")
    _inject(monkeypatch, svc, point)
    try:
        svc.apply_shift_suggestion("T", hw.interrupt_id, actor="Casey Sample")
    except Exception:
        pass
    monkeypatch.undo()
    attempts = [e for e in svc.decision_log.entries() if e.kind in ("apply", "apply_refused", "apply_failed")]
    assert len(attempts) == 1 and attempts[0].actor == "Casey Sample", [e.kind for e in svc.decision_log.entries()]


@pytest.mark.parametrize("op", ["decide", "apply"])
def test_recheck_first_read_failure_is_logged_and_survives_restart(svc, monkeypatch, op):
    hw = _pending(svc, "HW-101")
    _inject(monkeypatch, svc, "get_state")
    with pytest.raises(OSError):
        if op == "decide":
            svc.submit_decision("T", hw.interrupt_id, "approve", actor="Casey Sample")
        else:
            svc.apply_shift_suggestion("T", hw.interrupt_id, actor="Casey Sample")
    monkeypatch.undo()
    db = svc.db_path
    svc.close()
    s2 = ReviewerService(db)
    [e] = _outcomes(s2)
    assert e.kind == ("decision_failed" if op == "decide" else "apply_failed")
    assert "injected" in e.detail["error"] and e.detail["interrupt_id"] == hw.interrupt_id
    s2.close()


def test_r05_09_every_attempt_that_reached_the_graph_has_its_request_first(svc):
    # review-05: the request entry precedes the outcome for a decision and an Apply.
    svc.submit_decision("T", _pending(svc, "HW-103").interrupt_id, "approve", actor="a")
    svc.apply_shift_suggestion("T", _pending(svc, "HW-101").interrupt_id, actor="b")
    kinds = [e.kind for e in svc.decision_log.entries()]
    assert kinds.index("decision_requested") < kinds.index("decision")
    assert kinds.index("apply_requested") < kinds.index("apply")
    assert svc.decision_log.open_requests() == []
