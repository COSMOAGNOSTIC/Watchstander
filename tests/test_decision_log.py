"""Session 9: decision log. Every decision event, append-only (enforced) and tamper-evident.
Real graph, real ReviewerService, temp sqlite. All names notional.
"""

import sqlite3
from datetime import date, datetime as dt, time

import pytest
from fastapi.testclient import TestClient

from agent_core.crews import Crew, ShiftCalendar
from notional_permits import permits_on_file
from agent_core.decision_log import DecisionLog, LogTamperError
from agent_core.state import HazardCategory as H, SpatialCoordinates as SC, WorkPackageState as W
from reviewer import app as app_module
from reviewer import graph_driver
from reviewer.graph_driver import ReviewerService

CAL = ShiftCalendar.from_daily_pattern(date(2027, 1, 12), 3, [("DAY", time(7), time(15, 30)), ("SWING", time(15, 30), time(0)), ("MID", time(0), time(7))])
CREWS = [Crew(crew_id="CR-WELD", name="n"), Crew(crew_id="CR-TANK", name="n")]


def d(h, m=0):
    return dt(2027, 1, 12, h, m)


def pair():
    return [W(work_package_id="WELD-1", description="n", hazard_categories=[H.HOT_WORK], spatial=SC(compartment_id="TANK-4"),
              scheduled_start=d(7), scheduled_end=d(11), crew_id="CR-WELD"),
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


def seed(s):
    s.seed_run("T1", pair(), crews=CREWS, calendar=CAL, certificates=permits_on_file(pair()))  # review-05
    return {r.work_package_id: r for r in s.list_pending_reviews() if r.thread_id == "T1"}


# --- what gets logged ------------------------------------------------------


def test_a_decision_is_logged_with_who_what_and_why(svc):
    pend = seed(svc)
    svc.submit_decision("T1", pend["TANK-ENTRY"].interrupt_id, "approve", "notional note", actor="Casey Sample")
    [e] = [e for e in svc.decision_log.entries() if e.kind == "decision"]
    assert (e.actor, e.run_id, e.work_package_id) == ("Casey Sample", "T1", "TANK-ENTRY")
    assert e.detail["disposition"] == "approved" and e.detail["note"] == "notional note"
    assert e.at.tzinfo is not None


def test_a_decision_without_a_name_is_recorded_as_unidentified(svc):
    pend = seed(svc)
    svc.submit_decision("T1", pend["TANK-ENTRY"].interrupt_id, "reject")
    [e] = [e for e in svc.decision_log.entries() if e.kind == "decision"]
    assert e.actor == "unidentified reviewer" and e.detail["disposition"] == "rejected"


def test_apply_and_the_superseding_rejections_are_logged(svc):
    pend = seed(svc)
    res = svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id, actor="Riley Example")
    kinds = [e.kind for e in svc.decision_log.entries()]
    assert "apply" in kinds and kinds.count("superseded") == 2
    applied = next(e for e in svc.decision_log.entries() if e.kind == "apply")
    assert applied.actor == "Riley Example" and applied.detail["successor"] == res.new_thread_id
    assert [m["work_package_id"] for m in applied.detail["moves"]] == ["WELD-1"]
    assert all(e.actor == "system" for e in svc.decision_log.entries() if e.kind == "superseded")


def test_a_refused_apply_is_logged_with_its_reason(svc, monkeypatch):
    pend = seed(svc)
    from agent_core.shift_suggester import CrewShiftOutcome
    monkeypatch.setattr(graph_driver, "suggest_crew_shift", lambda *a, **k: CrewShiftOutcome(reason="notional change"))
    svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id, actor="Riley Example")
    [e] = [e for e in svc.decision_log.entries() if e.kind == "apply_refused"]
    assert "no longer holds" in e.detail["reason"]


def test_a_refused_decision_is_logged(svc):
    pend = seed(svc)
    svc.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    with pytest.raises(ValueError):
        svc.submit_decision("T1", pend["TANK-ENTRY"].interrupt_id, "approve", actor="Casey Sample")
    [e] = [e for e in svc.decision_log.entries() if e.kind == "decision_refused"]
    assert e.actor == "Casey Sample" and "superseded" in e.detail["reason"]


def test_crash_recovery_is_logged(tmp_path, monkeypatch):
    s = ReviewerService(str(tmp_path / "c.db"))
    pend = seed(s)
    monkeypatch.setattr(ReviewerService, "_close_superseded_reviews", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        s.apply_shift_suggestion("T1", pend["WELD-1"].interrupt_id)
    monkeypatch.undo()
    s.close()
    s2 = ReviewerService(s.db_path)
    assert "recovered" in [e.kind for e in s2.decision_log.entries()]
    s2.close()


def test_the_log_survives_a_restart(svc):
    pend = seed(svc)
    svc.submit_decision("T1", pend["TANK-ENTRY"].interrupt_id, "approve", actor="Casey Sample")
    svc.close()
    s2 = ReviewerService(svc.db_path)
    assert [e.kind for e in s2.decision_log.entries()] == ["decision_requested", "decision"]  # review-05 R05-09
    s2.close()


# --- append-only, enforced; tamper-evident -----------------------------------


def _log(tmp_path):
    return DecisionLog(str(tmp_path / "log.db"))


def test_entries_cannot_be_updated_or_deleted(tmp_path):
    log = _log(tmp_path)
    log.append(kind="decision", actor="Casey Sample", run_id="T", work_package_id="P", detail={"disposition": "approved"})
    conn = sqlite3.connect(log.db_path)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE decision_log SET actor = 'someone else'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM decision_log")
    conn.close()


def test_an_intact_chain_verifies(tmp_path):
    log = _log(tmp_path)
    for i in range(3):
        log.append(kind="decision", actor="a", run_id="T", work_package_id=f"P{i}", detail={"i": i})
    assert log.verify_chain() == 3


def test_an_edited_entry_is_pinpointed(tmp_path):
    log = _log(tmp_path)
    for i in range(3):
        log.append(kind="decision", actor="a", run_id="T", work_package_id=f"P{i}", detail={"i": i})
    conn = sqlite3.connect(log.db_path)
    conn.execute("DROP TRIGGER decision_log_no_update")  # someone with raw database access
    conn.execute("UPDATE decision_log SET actor = 'b' WHERE seq = 2")
    conn.commit(); conn.close()
    with pytest.raises(LogTamperError, match="entry 2"):
        log.verify_chain()


def test_a_removed_entry_is_detected(tmp_path):
    log = _log(tmp_path)
    for i in range(3):
        log.append(kind="decision", actor="a", run_id="T", work_package_id=f"P{i}", detail={"i": i})
    conn = sqlite3.connect(log.db_path)
    conn.execute("DROP TRIGGER decision_log_no_delete")
    conn.execute("DELETE FROM decision_log WHERE seq = 2")
    conn.commit(); conn.close()
    with pytest.raises(LogTamperError):
        log.verify_chain()


def test_unknown_kinds_are_refused(tmp_path):
    with pytest.raises(ValueError, match="kind"):
        _log(tmp_path).append(kind="edited", actor="a", run_id="T", work_package_id="P", detail={})


# --- reviewer UI ---------------------------------------------------------------


def _client(tmp_path):
    app_module.service = ReviewerService(str(tmp_path / "ui.db"))
    return TestClient(app_module.app)


def test_the_review_form_records_the_reviewers_name(tmp_path):
    client = _client(tmp_path)
    pend = seed(app_module.service)
    client.post(f"/review/T1/{pend['TANK-ENTRY'].interrupt_id}",
                data={"decision": "approve", "note": "", "actor": "Casey Sample"}, follow_redirects=False)
    [e] = [e for e in app_module.service.decision_log.entries() if e.kind == "decision"]
    assert e.actor == "Casey Sample"


def test_the_log_page_lists_entries_and_reports_the_chain(tmp_path):
    client = _client(tmp_path)
    pend = seed(app_module.service)
    app_module.service.submit_decision("T1", pend["TANK-ENTRY"].interrupt_id, "approve", actor="Casey Sample")
    page = client.get("/log").text
    assert "Casey Sample" in page and "TANK-ENTRY" in page and "approved" in page
    assert "Chain verified: 2 entries" in page  # request + decision (review-05 R05-09)


def test_known_limit_truncating_the_newest_entries_is_not_detected_by_the_chain_alone(tmp_path):
    # Documented limit, not a bug claim: a hash chain can't see its own tail removed.
    # Detecting that needs the latest hash recorded somewhere else (an external anchor).
    log = _log(tmp_path)
    for i in range(3):
        log.append(kind="decision", actor="a", run_id="T", work_package_id=f"P{i}", detail={"i": i})
    head = log.entries()[-1].hash
    conn = sqlite3.connect(log.db_path)
    conn.execute("DROP TRIGGER decision_log_no_delete")
    conn.execute("DELETE FROM decision_log WHERE seq = 3")
    conn.commit(); conn.close()
    assert log.verify_chain() == 2            # chain alone still verifies
    assert log.entries()[-1].hash != head     # but a recorded head exposes the truncation
