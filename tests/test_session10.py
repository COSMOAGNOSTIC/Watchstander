"""Session 10: a notional carrier dataset and a deterministic text daily brief.

The dataset is invented end to end (rule 6). Each scenario in it is built to trigger one
specific named rule, and these tests pin that, so the demo can't silently stop showing a
rule. The brief is plain text from deterministic code only (rule 7): no LLM is called.
"""

import json
import re
from datetime import datetime as dt

import pytest

from agent_core import carrier_demo, daily_brief
from agent_core.carrier_demo import CarrierDataset, load_carrier_dataset
from agent_core.decision_log import DecisionLog
from agent_core.projects import PackageStatus
from reviewer.graph_driver import ReviewerService

AS_OF = dt(2027, 3, 15, 6, 0)


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def ds():
    return load_carrier_dataset()


# --- the dataset is notional and well-formed ---------------------------------------


def test_dataset_is_marked_notional_and_names_no_real_ship(ds):
    assert ds.notional is True
    assert "notional" in ds.site.lower()
    for c in ds.crews:
        assert "notional" in c.name.lower()
    for p in ds.packages:
        assert p.governing_installation is None  # no real yard


def test_loader_refuses_a_dataset_not_marked_notional(tmp_path):
    raw = json.loads(carrier_demo.DEFAULT_PATH.read_text())
    raw["notional"] = False
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="notional"):
        load_carrier_dataset(bad)


def test_loader_refuses_dangling_references(tmp_path):
    raw = json.loads(carrier_demo.DEFAULT_PATH.read_text())
    raw["projects"][0]["work_package_ids"].append("NO-SUCH-PKG")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="NO-SUCH-PKG"):
        load_carrier_dataset(bad)


def test_loader_refuses_a_certificate_for_an_unknown_package(tmp_path):
    raw = json.loads(carrier_demo.DEFAULT_PATH.read_text())
    raw["certificates"][0]["work_package_id"] = "GHOST"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="GHOST"):
        load_carrier_dataset(bad)


def test_every_package_belongs_to_exactly_one_project(ds):
    ids = [i for pr in ds.projects for i in pr.work_package_ids]
    assert sorted(ids) == sorted(p.work_package_id for p in ds.packages)


# --- each scenario triggers the rule it was built for ----------------------------------

EXPECTED_RULES = {
    "HW-101": {"WS-HZ-001"},             # hot work in the tank being entered
    "CS-102": {"WS-HZ-001"},
    "HW-103": {"WS-JF-001"},             # hot work two frames from a confined space
    "CS-104": {"WS-JF-001"},
    "ALOFT-105": {"WS-OH-001"},          # aloft over the deck crew
    "DECK-106": {"WS-OH-001"},
    "FALL-107": {"WS-CT-003"},           # fall protection plan expires mid-job
    "HW-108": {"WS-CT-001"},             # no hot work permit on file
    "CONTR-109": {"WS-SC-002"},          # contractor past its allowed window
    "LOCKED-110": set(),
    "ELEC-111": set(),
}


def test_each_scenario_triggers_exactly_its_rule(ds):
    run = daily_brief.run_checks(ds)
    assert run.rules_by_package() == EXPECTED_RULES


def test_clean_packages_are_cleared_and_every_other_package_waits_for_a_person(ds):
    run = daily_brief.run_checks(ds)
    status = run.status_by_package()
    assert {k for k, v in status.items() if v == PackageStatus.CLEARED} == {"LOCKED-110", "ELEC-111"}
    assert all(v == PackageStatus.PENDING_REVIEW for k, v in status.items() if EXPECTED_RULES[k])


def test_the_tank_conflict_has_a_crew_shift_suggestion_that_moves_only_the_unlocked_crew(ds):
    run = daily_brief.run_checks(ds)
    out = run.shift_outcomes["HW-101"]
    assert out.suggestion is not None and out.suggestion.applied is False
    assert out.suggestion.to_shift_id == "20270315-SWING"
    assert [m.work_package_id for m in out.suggestion.moves] == ["HW-101"]
    assert "locked" in run.shift_outcomes["CS-102"].reason


def test_judgment_flag_routes_to_the_notional_gas_free_engineer(ds):
    run = daily_brief.run_checks(ds)
    [f] = run.judgment_flags
    assert f.rule_id == "WS-JF-001" and f.routed_to.display_name == "Riley Example"


def test_a_late_package_is_reported_against_its_project(ds):
    run = daily_brief.run_checks(ds)
    hangar = next(r for r in run.rollups if r.project_id == "PRJ-C")
    assert hangar.late_package_ids == ["FALL-107"]


def test_running_the_checks_does_not_change_the_dataset(ds):
    before = ds.model_dump()
    daily_brief.run_checks(ds)
    assert ds.model_dump() == before


# --- the text brief ------------------------------------------------------------------


def test_brief_is_deterministic_and_says_notional(ds):
    a = daily_brief.render(ds, as_of=AS_OF)
    b = daily_brief.render(load_carrier_dataset(), as_of=AS_OF)
    assert a == b
    assert a.splitlines()[0].startswith("WATCHSTANDER DAILY BRIEF")
    assert "NOTIONAL DATA" in a.splitlines()[0]
    assert "2027-03-15 06:00" in a


def test_brief_lists_projects_by_priority_then_due_date(ds):
    text = daily_brief.render(ds, as_of=AS_OF)
    order = [m for m in re.findall(r"^\s*\[(?:URGENT|HIGH|ROUTINE|LOW)\]\s+(PRJ-\w)", text, re.M)]
    assert order == ["PRJ-A", "PRJ-B", "PRJ-C", "PRJ-D"]


def test_brief_names_every_rule_and_who_to_call(ds):
    text = daily_brief.render(ds, as_of=AS_OF)
    for rules in EXPECTED_RULES.values():
        for r in rules:
            assert r in text
    assert "Riley Example" in text and "Gas Free Engineer" in text
    assert "Production Planner" in text  # contractor window finding's contact


def test_brief_shows_the_suggestion_as_not_applied(ds):
    text = daily_brief.render(ds, as_of=AS_OF)
    line = next(l for l in text.splitlines() if "Suggested, not applied" in l)
    assert "CR-WELD-A" in line and "20270315-SWING" in line


def test_brief_never_calls_the_llm(ds, monkeypatch):
    import agent_core.reasoning as reasoning
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    monkeypatch.setattr(reasoning, "_call_llm", lambda *a, **k: pytest.fail("brief called the LLM"), raising=False)
    daily_brief.render(ds, as_of=AS_OF)


def test_brief_without_a_decision_log_says_so(ds):
    assert "No decision log supplied" in daily_brief.render(ds, as_of=AS_OF)


# --- the decision-log anchor (closes Session 9's tail-truncation gap, given a recorded anchor) ---


def _log_with(tmp_path, n):
    log = DecisionLog(str(tmp_path / "log.db"))
    for i in range(n):
        log.append(kind="decision", actor="Casey Sample", run_id="T", work_package_id=f"P{i}", detail={"i": i})
    return log


def test_brief_prints_the_log_head_as_an_anchor(ds, tmp_path):
    log = _log_with(tmp_path, 3)
    text = daily_brief.render(ds, as_of=AS_OF, decision_log=log)
    head = log.entries()[-1]
    assert f"entries: 3" in text and f"head: {head.hash}" in text and "chain verified" in text


def test_a_recorded_anchor_catches_tail_truncation(ds, tmp_path):
    import sqlite3
    log = _log_with(tmp_path, 3)
    anchor = log.head()
    conn = sqlite3.connect(log.db_path)
    conn.execute("DROP TRIGGER decision_log_no_delete")
    conn.execute("DELETE FROM decision_log WHERE seq = 3")
    conn.commit(); conn.close()
    assert log.verify_chain() == 2  # the chain alone can't see it (Session 9 limit)
    with pytest.raises(Exception, match="anchor"):
        log.verify_anchor(*anchor)
    text = daily_brief.render(ds, as_of=AS_OF, decision_log=log, anchor=anchor)
    assert "DOES NOT MATCH" in text


def test_a_matching_anchor_verifies_after_more_entries_are_added(tmp_path):
    log = _log_with(tmp_path, 2)
    anchor = log.head()
    log.append(kind="decision", actor="a", run_id="T", work_package_id="P9", detail={})
    log.verify_anchor(*anchor)  # an older anchor still matches its own entry


def test_a_rewritten_anchored_entry_is_caught(tmp_path):
    import sqlite3
    log = _log_with(tmp_path, 2)
    seq, h = log.head()
    conn = sqlite3.connect(log.db_path)
    conn.execute("DROP TRIGGER decision_log_no_update")
    conn.execute("UPDATE decision_log SET hash = 'x' WHERE seq = 2")
    conn.commit(); conn.close()
    with pytest.raises(Exception, match="anchor"):
        log.verify_anchor(seq, h)


def test_a_tampered_chain_is_reported_in_the_brief_not_hidden(ds, tmp_path):
    import sqlite3
    log = _log_with(tmp_path, 2)
    conn = sqlite3.connect(log.db_path)
    conn.execute("DROP TRIGGER decision_log_no_update")
    conn.execute("UPDATE decision_log SET actor = 'b' WHERE seq = 1")
    conn.commit(); conn.close()
    text = daily_brief.render(ds, as_of=AS_OF, decision_log=log)
    assert "DOES NOT VERIFY" in text


def test_empty_log_head_is_none(tmp_path):
    assert DecisionLog(str(tmp_path / "e.db")).head() is None


# --- the reviewer's default demo is now notional ------------------------------------------


def test_reviewer_default_demo_is_the_notional_carrier(tmp_path):
    s = ReviewerService(str(tmp_path / "r.db"))
    s.seed_demo("DEMO")
    pending = {r.work_package_id for r in s.list_pending_reviews()}
    assert pending == {k for k, v in EXPECTED_RULES.items() if v}
    hw = next(r for r in s.list_pending_reviews() if r.work_package_id == "HW-101")
    assert hw.safety_brief["shift_outcome"]["suggestion"]["to_shift_id"] == "20270315-SWING"
    s.close()


def test_cli_prints_the_brief(capsys):
    daily_brief.main(["--as-of", "2027-03-15T06:00"])
    out = capsys.readouterr().out
    assert out.startswith("WATCHSTANDER DAILY BRIEF") and "PRJ-A" in out


def test_the_seed_button_seeds_the_notional_carrier(tmp_path):
    from fastapi.testclient import TestClient
    from reviewer import app as app_module
    app_module.service = ReviewerService(str(tmp_path / "ui.db"))
    client = TestClient(app_module.app)
    assert "notional carrier" in client.get("/").text.lower()
    client.post("/seed-demo", follow_redirects=False)
    page = client.get("/").text
    assert "HW-101" in page and "HW-2201" not in page


@pytest.mark.parametrize("value", ["yes", "true", 1, "1"])
def test_notional_must_be_a_real_true_not_a_truthy_string(tmp_path, value):
    # Mutation check found pydantic coercing "yes" to True; only JSON true counts.
    raw = json.loads(carrier_demo.DEFAULT_PATH.read_text())
    raw["notional"] = value
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_carrier_dataset(bad)


@pytest.mark.parametrize("value", ["yes", "true", 1])
def test_roster_notional_must_be_a_real_true(value):
    # Same class of bug, same fix, in the Session 5 roster loader.
    from agent_core.judgment import RosterPerson
    with pytest.raises(ValueError):
        RosterPerson(person_id="NP-X", display_name="n", role="r", notional=value)
