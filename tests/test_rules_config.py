import json

import pytest

from agent_core.rules_config import HazardRuleSet, load_hazard_rules
from agent_core.state import HazardCategory


def test_default_file_loads_and_matches_known_values():
    """
    Locks in the exact values deconfliction.py has always used, so a
    future edit to the checked-in JSON that changes these is a visible,
    intentional test failure -- not a silent behavior change.
    """
    rules = load_hazard_rules()
    assert rules.schema_version == 1
    assert rules.max_concurrent_hot_workers_per_fire_watch == 4
    pairs = rules.as_pair_set()
    assert frozenset({HazardCategory.HOT_WORK, HazardCategory.CONFINED_SPACE}) in pairs
    assert frozenset({HazardCategory.HOT_WORK, HazardCategory.WORKING_ALOFT}) in pairs
    assert frozenset({HazardCategory.WORKING_ALOFT, HazardCategory.FALL_PROTECTION}) in pairs
    assert len(pairs) == 3


def test_deconfliction_module_constants_come_from_the_same_config():
    from agent_core.deconfliction import (
        INCOMPATIBLE_HAZARD_PAIRS,
        MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH,
    )

    rules = load_hazard_rules()
    assert INCOMPATIBLE_HAZARD_PAIRS == rules.as_pair_set()
    assert MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH == (
        rules.max_concurrent_hot_workers_per_fire_watch
    )


def test_unknown_hazard_category_fails_loudly(tmp_path):
    bad_file = tmp_path / "bad_rules.json"
    bad_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "incompatible_hazard_pairs": [["hot_work", "not_a_real_hazard"]],
                "max_concurrent_hot_workers_per_fire_watch": 4,
                "source_citation": "test",
            }
        )
    )
    with pytest.raises(Exception):
        load_hazard_rules(bad_file)


def test_self_paired_hazard_fails_loudly(tmp_path):
    bad_file = tmp_path / "bad_rules.json"
    bad_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "incompatible_hazard_pairs": [["hot_work", "hot_work"]],
                "max_concurrent_hot_workers_per_fire_watch": 4,
                "source_citation": "test",
            }
        )
    )
    with pytest.raises(Exception):
        load_hazard_rules(bad_file)


def test_non_positive_limit_fails_loudly(tmp_path):
    bad_file = tmp_path / "bad_rules.json"
    bad_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "incompatible_hazard_pairs": [],
                "max_concurrent_hot_workers_per_fire_watch": 0,
                "source_citation": "test",
            }
        )
    )
    with pytest.raises(Exception):
        load_hazard_rules(bad_file)


def test_missing_file_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_hazard_rules(tmp_path / "does_not_exist.json")


def test_valid_custom_ruleset_round_trips():
    rules = HazardRuleSet(
        schema_version=1,
        incompatible_hazard_pairs=[["over_the_side", "working_aloft"]],
        max_concurrent_hot_workers_per_fire_watch=2,
        source_citation="test",
    )
    assert rules.as_pair_set() == {
        frozenset({HazardCategory.OVER_THE_SIDE, HazardCategory.WORKING_ALOFT})
    }
