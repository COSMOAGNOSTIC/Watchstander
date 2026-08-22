import json

from agent_core.rules_audit import read_audit_log, record_rule_change


def test_record_and_read_round_trip(tmp_path):
    log_path = tmp_path / "audit.jsonl"

    record_rule_change(
        timestamp="2026-08-21T00:00:00+00:00",
        editor="D.Langford",
        field="max_concurrent_hot_workers_per_fire_watch",
        old_value=4,
        new_value=3,
        reason="site-specific tightening for a smaller fire party this availability",
        path=log_path,
    )

    records = read_audit_log(log_path)
    assert len(records) == 1
    r = records[0]
    assert r.editor == "D.Langford"
    assert r.field == "max_concurrent_hot_workers_per_fire_watch"
    assert r.old_value == 4
    assert r.new_value == 3


def test_append_only_never_overwrites_prior_entries(tmp_path):
    log_path = tmp_path / "audit.jsonl"

    record_rule_change(
        timestamp="2026-08-21T00:00:00+00:00",
        editor="A",
        field="f1",
        old_value=1,
        new_value=2,
        reason="first change",
        path=log_path,
    )
    record_rule_change(
        timestamp="2026-08-21T01:00:00+00:00",
        editor="B",
        field="f2",
        old_value="x",
        new_value="y",
        reason="second change",
        path=log_path,
    )

    records = read_audit_log(log_path)
    assert len(records) == 2
    assert records[0].editor == "A"
    assert records[1].editor == "B"


def test_missing_log_returns_empty_list_not_an_error(tmp_path):
    assert read_audit_log(tmp_path / "never_written.jsonl") == []


def test_log_file_is_valid_jsonl_one_object_per_line(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    record_rule_change(
        timestamp="2026-08-21T00:00:00+00:00",
        editor="D.Langford",
        field="incompatible_hazard_pairs",
        old_value=[["hot_work", "confined_space"]],
        new_value=[["hot_work", "confined_space"], ["hot_work", "over_the_side"]],
        reason="added a pair after AIT feedback",
        path=log_path,
    )
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["editor"] == "D.Langford"
    assert parsed["new_value"] == [["hot_work", "confined_space"], ["hot_work", "over_the_side"]]
