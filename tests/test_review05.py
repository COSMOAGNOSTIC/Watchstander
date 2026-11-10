"""review-05 (Fable red team) regressions. Real graph, real ReviewerService, temp sqlite.
All data notional. Each block names the finding it pins.
"""

import os
import sqlite3
import sys
import types
from datetime import datetime as dt

import pytest
from pydantic import ValidationError

from agent_core import certificates as certs_mod
from agent_core import daily_brief, deconfliction
from agent_core.carrier_demo import CarrierDataset, load_carrier_dataset
from agent_core.certificates import Certificate, CertificateKind, check_certificates
from agent_core.crews import Crew, Shift, Window, check_schedule_constraints
from agent_core.decision_log import DecisionLog
from agent_core.projects import PackageStatus, Project, package_status
from agent_core.state import WorkPackageState as W
from reviewer.graph_driver import ReviewerService

AS_OF = dt(2027, 3, 15, 6)
BASE = dict(description="notional", scheduled_start="2027-03-15T12:00:00", scheduled_end="2027-03-15T14:00:00",
            spatial={"compartment_id": "Notional Berthing 260", "deck_level": "Notional 2nd Deck",
                     "frame_start": 258, "frame_end": 259}, crew_id="CR-DECK")


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
    return next((r for r in s.list_pending_reviews() if r.work_package_id == pid), None)


def _with(ds, data):
    ds.packages.append(W.model_validate(data))
    ds.projects[-1].work_package_ids.append(data["work_package_id"])
    return ds


def _state_pkg(s, thread, pid):
    v = s._graph.get_state({"configurable": {"thread_id": thread}}).values
    return next(p for p in v.get("reviewed_packages", []) + v["work_packages"] if p.work_package_id == pid)


# --- R05-01: a package can't arrive already decided ---------------------------------------------


def test_r05_01_preset_approval_is_dropped_in_the_brief():
    ds = _with(load_carrier_dataset(), {**BASE, "work_package_id": "X-01", "risk_level": "critical",
                                        "hitl_disposition": "approved", "cleared_for_execution": True})
    status = daily_brief.run_checks(ds, AS_OF).status_by_package()["X-01"]
    assert status == PackageStatus.PENDING_REVIEW
    assert "X-01" in daily_brief.render(ds, as_of=AS_OF).split("NEEDS A PERSON")[1].split("JUDGMENT FLAGS")[0]


def test_r05_01_preset_approval_is_dropped_in_the_graph(tmp_path):
    ds = _with(load_carrier_dataset(), {**BASE, "work_package_id": "X-01", "requires_hitl_review": True,
                                        "hitl_disposition": "approved", "cleared_for_execution": True})
    s = ReviewerService(str(tmp_path / "g.db"))
    s.seed_run("T", ds.fresh_packages(), crews=ds.crews, calendar=ds.calendar, certificates=ds.certificates)
    assert _pending(s, "X-01") is not None
    s.close()


# --- R05-02: a rejection follows the package into Apply's successor run --------------------------


def test_r05_02_rejection_survives_apply_on_a_neighbour(svc):
    svc.submit_decision("T", _pending(svc, "CS-102").interrupt_id, "reject", "notional: do not enter", actor="Casey Sample")
    res = svc.apply_shift_suggestion("T", _pending(svc, "HW-101").interrupt_id, actor="Riley Example")
    assert res.applied
    cs = _state_pkg(svc, res.new_thread_id, "CS-102")
    assert cs.hitl_disposition == "rejected" and cs.cleared_for_execution is False
    assert "Casey Sample" in cs.conflict_rationale and "do not enter" in cs.conflict_rationale
    assert _pending(svc, "CS-102") is None  # held, not silently re-queued or cleared
    applied = next(e for e in svc.decision_log.entries() if e.kind == "apply")
    assert applied.detail["carried_rejections"] == ["CS-102"]


def test_r05_02_unrejected_neighbours_are_not_marked_rejected(svc):
    res = svc.apply_shift_suggestion("T", _pending(svc, "HW-101").interrupt_id)
    cs = _state_pkg(svc, res.new_thread_id, "CS-102")
    assert cs.hitl_disposition is None


# --- R05-03: approval can't clear an open certificate or schedule finding ------------------------


def test_r05_03_approval_with_an_open_certificate_finding_stays_blocked(svc):
    svc.submit_decision("T", _pending(svc, "FALL-107").interrupt_id, "approve", actor="Casey Sample")
    d = next(x for x in svc.list_decided() if x["work_package_id"] == "FALL-107")
    assert d["disposition"] == "approved" and d["cleared_for_execution"] is False
    p = _state_pkg(svc, "T", "FALL-107")
    assert "WS-CT-003" in p.open_findings
    assert "still blocked by WS-CT-003" in p.conflict_rationale
    entry = next(e for e in svc.decision_log.entries() if e.kind == "decision")
    assert entry.detail["cleared_for_execution"] is False and entry.detail["blocked_by"] == ["WS-CT-003"]


def test_r05_03_approval_with_an_open_schedule_finding_stays_blocked(svc):
    svc.submit_decision("T", _pending(svc, "CONTR-109").interrupt_id, "approve")
    assert next(x for x in svc.list_decided() if x["work_package_id"] == "CONTR-109")["cleared_for_execution"] is False


def test_r05_03_approval_still_clears_a_conflict_or_judgment_flag(svc):
    svc.submit_decision("T", _pending(svc, "HW-103").interrupt_id, "approve")  # WS-JF-001 only
    assert next(x for x in svc.list_decided() if x["work_package_id"] == "HW-103")["cleared_for_execution"] is True


def test_r05_03_status_of_approved_but_blocked_is_has_findings():
    p = W.model_validate({**BASE, "work_package_id": "P"})
    p.hitl_disposition, p.cleared_for_execution = "approved", False
    f = types.SimpleNamespace(work_package_id="P")
    assert package_status(p, certificate_findings=[f], judgment_flags=[], schedule_findings=[]) == PackageStatus.HAS_FINDINGS


# --- R05-04: misspelled keys are refused on every input model -----------------------------------


@pytest.mark.parametrize("model,data", [
    (W, {**BASE, "work_package_id": "P", "hazard_categoires": ["hot_work"]}),
    (W, {**BASE, "work_package_id": "P", "hot_workers": 6}),
    (W, {**BASE, "work_package_id": "P", "risk": "critical"}),
    (W, {**BASE, "work_package_id": "P", "lock": True}),
    (Crew, {"crew_id": "C", "name": "n", "contractor": True}),
    (Window, {"start": "2027-03-15T07:00:00", "end": "2027-03-15T08:00:00", "until": "x"}),
    (Shift, {"shift_id": "S", "name": "n", "start": "2027-03-15T07:00:00", "end": "2027-03-15T08:00:00", "crew": "x"}),
    (Certificate, {"certificate_id": "C", "work_package_id": "P", "kind": "hot_work_permit",
                   "valid_from": "2027-03-15T07:00:00", "valid_until": "2027-03-15T08:00:00", "valid_till": "x"}),
    (Project, {"project_id": "P", "name": "n", "priorty": "urgent"}),
])
def test_r05_04_unknown_keys_are_refused(model, data):
    with pytest.raises(ValidationError, match="xtra"):
        model.model_validate(data)


def test_r05_04_dataset_with_an_unknown_key_is_refused(tmp_path):
    import json
    from agent_core import carrier_demo
    raw = json.loads(carrier_demo.DEFAULT_PATH.read_text())
    raw["packges"] = []
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_carrier_dataset(bad)


# --- R05-05: a hazard implies its authorization -------------------------------------------------


def _kinds(pkg, certs=()):
    return [f.rule_id for f in check_certificates(W.model_validate(pkg), list(certs))]


def test_r05_05_hot_work_needs_a_hot_work_permit_without_asking():
    assert _kinds({**BASE, "work_package_id": "P", "hazard_categories": ["hot_work"]}) == ["WS-CT-001"]


def test_r05_05_confined_space_needs_an_entry_permit_without_asking():
    assert _kinds({**BASE, "work_package_id": "P", "hazard_categories": ["confined_space"]}) == ["WS-CT-002"]


def test_r05_05_work_aloft_needs_an_aloft_authorization():
    assert _kinds({**BASE, "work_package_id": "P", "hazard_categories": ["working_aloft"]}) == ["WS-CT-006"]
    assert _kinds({**BASE, "work_package_id": "P", "spatial": {**BASE["spatial"], "is_aloft": True}}) == ["WS-CT-006"]


def test_r05_05_an_aloft_chit_for_the_day_covers_it():
    chit = Certificate(certificate_id="N-CHIT", work_package_id="P", kind="aloft_authorization", form="chit",
                       valid_from="2027-03-15T07:00:00", valid_until="2027-03-15T16:00:00")
    assert _kinds({**BASE, "work_package_id": "P", "hazard_categories": ["working_aloft"]}, [chit]) == []


def test_r05_05_a_standing_aloft_covers_every_package_in_its_dates():
    standing = Certificate(certificate_id="N-STANDING", work_package_id=None, kind="aloft_authorization", form="standing",
                           valid_from="2027-03-14T00:00:00", valid_until="2027-03-18T00:00:00")
    assert _kinds({**BASE, "work_package_id": "P", "hazard_categories": ["working_aloft"]}, [standing]) == []


def test_r05_05_a_chit_that_ends_early_is_a_finding():
    chit = Certificate(certificate_id="N-CHIT", work_package_id="P", kind="aloft_authorization", form="chit",
                       valid_from="2027-03-15T07:00:00", valid_until="2027-03-15T13:00:00")
    assert _kinds({**BASE, "work_package_id": "P", "hazard_categories": ["working_aloft"]}, [chit]) == ["WS-CT-006"]


@pytest.mark.parametrize("data", [
    {"work_package_id": None, "kind": "aloft_authorization", "form": "chit"},        # a chit names its job
    {"work_package_id": "P", "kind": "aloft_authorization", "form": "standing"},     # a standing aloft is ship-wide
    {"work_package_id": "P", "kind": "aloft_authorization"},                          # form is required
    {"work_package_id": "P", "kind": "hot_work_permit", "form": "chit"},              # only aloft has a form
    {"work_package_id": None, "kind": "hot_work_permit"},                             # only a standing aloft omits its job
])
def test_r05_05_certificate_shapes_are_strict(data):
    with pytest.raises(ValidationError):
        Certificate(certificate_id="N", valid_from="2027-03-15T07:00:00", valid_until="2027-03-15T13:00:00", **data)


def test_r05_05_fall_protection_hazard_does_not_imply_a_per_job_plan():
    # Donnie: the fall protection plan is a ship's standing order, not a per-job permit.
    assert _kinds({**BASE, "work_package_id": "P", "hazard_categories": ["fall_protection"]}) == []


def test_r05_05_hot_work_with_no_permits_block_is_not_cleared():
    ds = _with(load_carrier_dataset(), {**BASE, "work_package_id": "X-05", "hazard_categories": ["hot_work"]})
    assert daily_brief.run_checks(ds, AS_OF).status_by_package()["X-05"] != PackageStatus.CLEARED


# --- R05-06: fire-watch capacity with no watch named, and watch IDs compared loosely ------------


def _flagged(pkgs):
    return {p.work_package_id: bool(p.conflicts or p.conflict_rationale)
            for p in deconfliction.deconfliction_node({"work_packages": pkgs})["work_packages"]}


def test_r05_06_over_four_hot_workers_with_no_watch_named_is_flagged():
    p = W.model_validate({**BASE, "work_package_id": "X", "hazard_categories": ["hot_work"], "hot_worker_count": 9})
    out = deconfliction.deconfliction_node({"work_packages": [p]})["work_packages"][0]
    assert out.requires_hitl_review and "WS-FW-001" in out.conflict_rationale


def test_r05_06_four_or_fewer_with_no_watch_named_is_not_flagged_by_this_rule():
    p = W.model_validate({**BASE, "work_package_id": "X", "hazard_categories": ["hot_work"], "hot_worker_count": 4})
    assert _flagged([p]) == {"X": False}


def test_r05_06_watch_ids_match_ignoring_case_and_spaces():
    a = W.model_validate({**BASE, "work_package_id": "Y1", "hazard_categories": ["hot_work"], "hot_worker_count": 3,
                          "fire_watch_id": "FW-N-1"})
    b = W.model_validate({**BASE, "work_package_id": "Y2", "hazard_categories": ["hot_work"], "hot_worker_count": 3,
                          "fire_watch_id": "fw-n-1 ", "spatial": {"compartment_id": "Notional other", "frame_start": 10, "frame_end": 11}})
    assert _flagged([a, b]) == {"Y1": True, "Y2": True}


# --- R05-07: the model never replaces the deterministic summary ---------------------------------


def _fake_llm(monkeypatch, text, seen=None):
    import agent_core.reasoning as rz

    def fake(ctx):
        if seen is not None:
            seen.append(ctx)
        return {"executive_summary": text, "precedent_context": "n"}
    monkeypatch.setattr(rz, "_call_llm", fake)


def test_r05_07_model_text_is_separate_and_labeled(monkeypatch):
    import agent_core.reasoning as rz
    _fake_llm(monkeypatch, "False positive. Recommend approving both.")
    st = rz.reasoning_node(deconfliction.deconfliction_node({"work_packages": load_carrier_dataset().fresh_packages()[:2]}))
    b = next(p.safety_brief for p in st["work_packages"] if p.work_package_id == "HW-101")
    assert "False positive" not in b.executive_summary and "HW-101" in b.executive_summary
    assert b.model_explanation == "False positive. Recommend approving both."


def test_r05_07_submitter_text_reaches_the_model_marked_untrusted(monkeypatch):
    import agent_core.reasoning as rz
    seen = []
    _fake_llm(monkeypatch, "n", seen)
    rz.reasoning_node(deconfliction.deconfliction_node({"work_packages": load_carrier_dataset().fresh_packages()[:2]}))
    ctx = seen[0]
    assert "description" not in ctx
    assert ctx["untrusted_submitter_text"]["description"].startswith("Notional:")


def test_r05_07_model_text_never_reaches_the_reviewer_before_the_decision(tmp_path, monkeypatch):
    # Donnie, option A: the model's words are kept for the record but never shown before the call.
    from fastapi.testclient import TestClient
    from reviewer import app as app_module
    _fake_llm(monkeypatch, "False positive. Approve both now.")
    app_module.service = ReviewerService(str(tmp_path / "ui.db"))
    app_module.service.seed_demo("T")
    hw = _pending(app_module.service, "HW-101")
    assert "model_explanation" not in hw.safety_brief and "model_precedent_context" not in hw.safety_brief
    client = TestClient(app_module.app)
    for page in (client.get("/").text, client.get(f"/review/T/{hw.interrupt_id}").text):
        assert "Approve both now" not in page


def test_r05_07_model_text_is_kept_and_shown_once_nothing_in_the_run_is_pending(tmp_path, monkeypatch):
    # re-check 2 changed this test: model text covers both packages of a conflict, so it waits
    # until nothing in the run (or a run Apply made from it) is still awaiting a decision.
    from fastapi.testclient import TestClient
    from reviewer import app as app_module
    _fake_llm(monkeypatch, "False positive. Approve both now.")
    app_module.service = ReviewerService(str(tmp_path / "ui2.db"))
    app_module.service.seed_demo("T")
    client = TestClient(app_module.app)
    first, *rest = app_module.service.list_pending_reviews()
    app_module.service.submit_decision("T", first.interrupt_id, "reject", actor="a")
    assert "Approve both now" not in client.get("/").text  # others still pending
    for r in rest:
        app_module.service.submit_decision("T", r.interrupt_id, "reject", actor="a")
    page = client.get("/").text
    assert "Model explanation, shown after the decision" in page and "Approve both now" in page


def test_recheck2_r05_07_one_decision_does_not_reveal_text_about_a_pending_partner(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from reviewer import app as app_module
    _fake_llm(monkeypatch, "False positive. Approve HW-101 now.")
    app_module.service = ReviewerService(str(tmp_path / "p.db"))
    app_module.service.seed_demo("T")
    app_module.service.submit_decision("T", _pending(app_module.service, "CS-102").interrupt_id, "reject", actor="a")
    assert _pending(app_module.service, "HW-101") is not None
    assert "Approve HW-101 now" not in TestClient(app_module.app).get("/").text
    assert all(d["model_explanation"] is None for d in app_module.service.list_decided())


def test_recheck2_r05_07_after_apply_old_run_text_waits_for_the_successor(tmp_path, monkeypatch):
    _fake_llm(monkeypatch, "Model view of the pair.")
    s = ReviewerService(str(tmp_path / "a.db"))
    s.seed_demo("T")
    res = s.apply_shift_suggestion("T", _pending(s, "HW-101").interrupt_id, actor="a")
    assert res.applied and any(r.thread_id == res.new_thread_id for r in s.list_pending_reviews())
    assert all(d["model_explanation"] is None for d in s.list_decided())
    s.close()


def test_r05_08_api_exception_falls_back_to_deterministic(monkeypatch, tmp_path):
    import agent_core.reasoning as rz

    class Boom:
        def __init__(self, *a, **k):
            self.messages = types.SimpleNamespace(create=self._create)

        def _create(self, *a, **k):
            raise RuntimeError("api down")

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Boom))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    assert rz._call_llm({"work_package_id": "x"}) is None
    s = ReviewerService(str(tmp_path / "f.db"))
    s.seed_demo("T")
    assert _pending(s, "HW-101") is not None
    s.close()


# --- R05-09: log first; no stored decision or Apply without a record ---------------------------


def test_r05_09_unloggable_decision_changes_nothing(svc):
    hw = _pending(svc, "HW-103")
    with pytest.raises(Exception):
        svc.submit_decision("T", hw.interrupt_id, "approve", actor="\ud800")
    assert _pending(svc, "HW-103") is not None
    assert not [x for x in svc.list_decided() if x["work_package_id"] == "HW-103"]


def test_r05_09_a_normal_decision_logs_request_then_outcome(svc):
    svc.submit_decision("T", _pending(svc, "HW-103").interrupt_id, "approve", actor="a")
    assert [e.kind for e in svc.decision_log.entries()] == ["decision_requested", "decision"]
    assert svc.decision_log.open_requests() == []


def test_r05_09_unloggable_apply_changes_nothing(svc, monkeypatch):
    hw = _pending(svc, "HW-101")
    real = svc.decision_log.append

    def picky(**kw):
        if kw["kind"] == "apply_requested":
            raise sqlite3.OperationalError("disk full (injected)")
        return real(**kw)

    monkeypatch.setattr(svc.decision_log, "append", picky)
    with pytest.raises(Exception):
        svc.apply_shift_suggestion("T", hw.interrupt_id)
    monkeypatch.undo()
    assert _pending(svc, "HW-101") is not None
    assert not [t for t in __import__("reviewer.registry", fromlist=["x"]).list_thread_ids(svc.db_path) if t != "T"]


def test_r05_09_a_request_with_no_outcome_is_visible(tmp_path):
    log = DecisionLog(str(tmp_path / "l.db"))
    log.append(kind="decision_requested", actor="a", run_id="T", work_package_id="P", detail={"interrupt_id": "i1"})
    q = log.append(kind="decision_requested", actor="a", run_id="T", work_package_id="Q", detail={"interrupt_id": "i2"})
    log.append(kind="decision", actor="a", run_id="T", work_package_id="Q",
               detail={"interrupt_id": "i2", "disposition": "approved", "request_seq": q.seq})
    assert [e.work_package_id for e in log.open_requests()] == ["P"]


# --- R05-10: schedule rules that need no calendar still run -------------------------------------


def test_r05_10_contractor_window_checked_without_a_calendar(tmp_path):
    ds = load_carrier_dataset()
    s = ReviewerService(str(tmp_path / "n.db"))
    s.seed_run("T", ds.fresh_packages(), crews=ds.crews, calendar=None, certificates=ds.certificates)
    assert _pending(s, "CONTR-109") is not None
    s.close()


def test_r05_10_rules_without_a_calendar_skip_only_the_calendar_rule():
    ds = load_carrier_dataset()
    pkgs = ds.fresh_packages() + [W.model_validate({**BASE, "work_package_id": "GHOST", "crew_id": "CR-NONE"})]
    rules = {f.rule_id for f in check_schedule_constraints(pkgs, ds.crews, None)}
    assert {"WS-SC-001", "WS-SC-002"} <= rules and "WS-SC-003" not in rules


# --- R05-11: the brief never creates or empties a database --------------------------------------


def test_r05_11_brief_refuses_a_missing_db(tmp_path):
    missing = tmp_path / "typo.db"
    with pytest.raises(SystemExit):
        daily_brief.main(["--as-of", "2027-03-15T06:00", "--db", str(missing)])
    assert not missing.exists()


def test_r05_11_brief_refuses_a_db_without_a_decision_log(tmp_path):
    other = tmp_path / "other.db"
    sqlite3.connect(other).execute("CREATE TABLE t (x)").connection.close()
    with pytest.raises(SystemExit):
        daily_brief.main(["--as-of", "2027-03-15T06:00", "--db", str(other)])


def test_r05_11_read_only_log_cannot_write(tmp_path):
    path = str(tmp_path / "ro.db")
    DecisionLog(path).close()
    ro = DecisionLog(path, read_only=True)
    with pytest.raises(sqlite3.OperationalError):
        ro.append(kind="decision", actor="a", run_id="T", work_package_id="P", detail={})


# --- review-05 re-check (reopened R05-05, 06, 08, 09, 10) ------------------------------------------


def test_recheck_r05_05_a_chit_longer_than_a_day_is_refused():
    with pytest.raises(ValidationError, match="day"):
        Certificate(certificate_id="C", work_package_id="P", kind="aloft_authorization", form="chit",
                    valid_from="2027-03-15T07:00:00", valid_until="2027-03-17T16:00:00")


def test_recheck_r05_05_a_full_day_chit_and_a_multi_day_standing_aloft_are_fine():
    Certificate(certificate_id="C", work_package_id="P", kind="aloft_authorization", form="chit",
                valid_from="2027-03-15T07:00:00", valid_until="2027-03-16T07:00:00")
    Certificate(certificate_id="S", work_package_id=None, kind="aloft_authorization", form="standing",
                valid_from="2027-03-14T00:00:00", valid_until="2027-03-30T00:00:00")


def test_recheck_r05_06_no_move_is_offered_that_leaves_the_job_flagged():
    from agent_core.shift_suggester import suggest_crew_shift
    ds = load_carrier_dataset()
    nine = W.model_validate({**BASE, "work_package_id": "NINE", "hazard_categories": ["hot_work"], "hot_worker_count": 9})
    permit = Certificate(certificate_id="HWP", work_package_id="NINE", kind="hot_work_permit",
                         valid_from="2027-03-14T00:00:00", valid_until="2027-03-18T00:00:00")
    out = suggest_crew_shift(ds.fresh_packages() + [nine], "NINE", crews=ds.crews, calendar=ds.calendar,
                             certificates=ds.certificates + [permit])
    assert out.suggestion is None
    assert all("WS-FW-001" in r.rule_ids for r in out.rejected)


class _Resp:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(type="text", text=text)]


@pytest.mark.parametrize("body", ["null", "[]", '"text"', '{"executive_summary": {"x": 1}, "precedent_context": "n"}',
                                  '{"executive_summary": "", "precedent_context": "n"}',
                                  '{"executive_summary": "ok", "precedent_context": 3}'])
def test_recheck_r05_08_malformed_model_answers_fall_back(monkeypatch, tmp_path, body):
    import agent_core.reasoning as rz

    class Client:
        def __init__(self, *a, **k):
            self.messages = types.SimpleNamespace(create=lambda *a, **k: _Resp(body))

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    assert rz._call_llm({"work_package_id": "x"}) is None
    s = ReviewerService(str(tmp_path / "m.db"))
    s.seed_demo("T")
    assert _pending(s, "HW-101") is not None
    s.close()


def test_recheck_r05_08_any_exception_in_the_model_branch_falls_back(monkeypatch, tmp_path):
    import agent_core.reasoning as rz
    monkeypatch.setattr(rz, "_call_llm", lambda ctx: {"executive_summary": object(), "precedent_context": "n"})
    s = ReviewerService(str(tmp_path / "x.db"))
    s.seed_demo("T")
    hw = _pending(s, "HW-101")
    assert hw is not None and hw.safety_brief["source"] == "deterministic-fallback"
    s.close()


def test_recheck_r05_09_a_later_refusal_does_not_close_an_earlier_request(svc, monkeypatch):
    hw = _pending(svc, "HW-103")
    real = svc.decision_log.append

    def picky(**kw):
        if kw["kind"] in ("decision", "decision_failed"):
            raise OSError("injected")
        return real(**kw)

    monkeypatch.setattr(svc.decision_log, "append", picky)
    with pytest.raises(OSError):
        svc.submit_decision("T", hw.interrupt_id, "approve", actor="a")
    monkeypatch.undo()
    with pytest.raises(ValueError):
        svc.submit_decision("T", hw.interrupt_id, "reject", actor="b")
    [open_req] = svc.decision_log.open_requests()
    assert open_req.kind == "decision_requested" and open_req.actor == "a"


def test_recheck_r05_09_every_outcome_names_its_request(svc):
    svc.submit_decision("T", _pending(svc, "HW-103").interrupt_id, "approve", actor="a")
    req, out = svc.decision_log.entries()
    assert out.detail["request_seq"] == req.seq


def test_recheck_r05_10_an_explicit_empty_roster_still_checks_crews(tmp_path):
    g = W.model_validate({**BASE, "work_package_id": "G", "crew_id": "CR-GHOST"})
    s = ReviewerService(str(tmp_path / "e.db"))
    s.seed_run("T", [g], crews=[], calendar=None, certificates=[])
    assert _pending(s, "G") is not None
    s.close()


def test_recheck_r05_10_no_crew_data_at_all_still_skips_crew_rules(tmp_path):
    g = W.model_validate({**BASE, "work_package_id": "G", "crew_id": "CR-GHOST"})
    s = ReviewerService(str(tmp_path / "n.db"))
    s.seed_run("T", [g], crews=None, calendar=None, certificates=[])
    assert _pending(s, "G") is None  # no crew data given: the brief says so; nothing to check against
    s.close()


def test_recheck_r05_08_the_model_call_raising_falls_back(monkeypatch, tmp_path):
    import agent_core.reasoning as rz
    monkeypatch.setattr(rz, "_call_llm", lambda ctx: (_ for _ in ()).throw(RuntimeError("anything at all")))
    s = ReviewerService(str(tmp_path / "r.db"))
    s.seed_demo("T")
    hw = _pending(s, "HW-101")
    assert hw is not None and hw.safety_brief["source"] == "deterministic-fallback"
    s.close()


def test_r05_07_the_review_request_itself_carries_no_model_text(tmp_path, monkeypatch):
    # First guard, checked on its own: the interrupt payload the graph raises.
    _fake_llm(monkeypatch, "False positive. Approve both now.")
    s = ReviewerService(str(tmp_path / "p.db"))
    s.seed_demo("T")
    raw = [i.value for t in s._graph.get_state({"configurable": {"thread_id": "T"}}).tasks for i in t.interrupts]
    assert raw and all("Approve both now" not in repr(v) for v in raw)
    s.close()


def test_r05_07_runs_saved_before_this_fix_are_still_stripped_on_read(tmp_path, monkeypatch):
    # Second guard, checked on its own: a checkpoint written before the fix still holds model
    # text in its review request. Simulate it by turning the first guard off while seeding.
    import agent_core.hitl as hitl
    _fake_llm(monkeypatch, "False positive. Approve both now.")
    monkeypatch.setattr(hitl, "MODEL_TEXT_FIELDS", set())
    s = ReviewerService(str(tmp_path / "old.db"))
    s.seed_demo("T")
    raw = [i.value for t in s._graph.get_state({"configurable": {"thread_id": "T"}}).tasks for i in t.interrupts]
    assert any("Approve both now" in repr(v) for v in raw)  # the old payload really has it
    hw = _pending(s, "HW-101")
    assert "model_explanation" not in hw.safety_brief
    s.close()



# --- re-check 2 low items ----------------------------------------------------------------------


def test_recheck2_mixed_time_zones_on_a_chit_get_a_clear_refusal():
    with pytest.raises(ValidationError, match="time zone|timezone|offset|comparable"):
        Certificate(certificate_id="C", work_package_id="P", kind="aloft_authorization", form="chit",
                    valid_from="2027-03-15T07:00:00+00:00", valid_until="2027-03-15T16:00:00")


def test_recheck2_older_reschedule_suggester_also_refuses_a_job_with_no_watch_named():
    from agent_core.reschedule_suggestion import suggest_reschedule
    nine = W.model_validate({**BASE, "work_package_id": "NINE", "hazard_categories": ["hot_work"], "hot_worker_count": 9})
    assert suggest_reschedule([nine], "NINE") is None


def test_recheck2_the_model_call_has_a_timeout(monkeypatch):
    import agent_core.reasoning as rz
    seen = {}

    class Client:
        def __init__(self, *a, **k):
            seen.update(k)
            self.messages = types.SimpleNamespace(create=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    rz._call_llm({"work_package_id": "x"})
    assert 0 < seen.get("timeout", 0) <= 60
