"""Session 5: judgment flags routed to a named Gas Free Engineer.

All people and data here are notional -- no real ship, yard, or personnel data.
"""

import json
from datetime import datetime as dt

import pytest

from agent_core.deconfliction import check_conflict
from agent_core.judgment import (
    JUDGMENT_ADJACENCY_FRAMES,
    Roster,
    judgment_flags,
    load_roster,
)
from agent_core.named_rules import RULES, RuleCategory, get_rule
from agent_core.state import HazardCategory as H, SpatialCoordinates, WorkPackageState
from eval.scenarios import CONFLICT_SCENARIOS

ROSTER = load_roster()
T0, T1 = dt(2027, 1, 12, 7), dt(2027, 1, 12, 15)


def _wp(pid, hazards, frames=None, compartment=None, start=T0, end=T1):
    f0, f1 = frames if frames else (None, None)
    return WorkPackageState(
        work_package_id=pid, description=f"notional {pid}", hazard_categories=hazards,
        spatial=SpatialCoordinates(frame_start=f0, frame_end=f1, compartment_id=compartment),
        scheduled_start=start, scheduled_end=end,
    )


def _person(pid, role, primary=True, notional=True, name=None):
    return {"person_id": pid, "display_name": name or f"{pid} Example", "role": role,
            "primary": primary, "notional": notional}


# --- roster --------------------------------------------------------------


def test_every_roster_entry_is_marked_notional():
    assert ROSTER.people and all(p.notional for p in ROSTER.people)


def test_roster_has_a_primary_for_every_judgment_rule_contact():
    for r in RULES:
        if r.category == RuleCategory.JUDGMENT:
            assert ROSTER.primary_for(r.contact_role).role == r.contact_role


def test_non_notional_entry_refuses_to_load(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"schema_version": 1, "people": [_person("P-1", "Gas Free Engineer", notional=False)]}))
    with pytest.raises(ValueError, match="notional"):
        load_roster(p)


def test_two_primaries_for_one_role_refuse_to_load():
    with pytest.raises(ValueError, match="primary"):
        Roster(people=[_person("P-1", "Gas Free Engineer"), _person("P-2", "Gas Free Engineer")])


def test_duplicate_person_id_refuses_to_load():
    with pytest.raises(ValueError, match="duplicate"):
        Roster(people=[_person("P-1", "Gas Free Engineer"), _person("P-1", "Safety Officer")])


def test_missing_role_raises_rather_than_routing_to_nobody():
    r = Roster(people=[_person("P-1", "Safety Officer")])
    with pytest.raises(LookupError, match="Gas Free Engineer"):
        r.primary_for("Gas Free Engineer")


def test_flags_with_a_roster_missing_the_gfe_raise():
    r = Roster(people=[_person("P-1", "Safety Officer")])
    with pytest.raises(LookupError):
        judgment_flags([_wp("A", [H.HOT_WORK])], roster=r)


# --- the judgment rules themselves ---------------------------------------


@pytest.mark.parametrize("rid", ["WS-JF-001", "WS-JF-002", "WS-JF-003"])
def test_judgment_rules_exist_and_route_to_the_gas_free_engineer(rid):
    r = get_rule(rid)
    assert r.category == RuleCategory.JUDGMENT
    assert r.contact_role == "Gas Free Engineer"


# --- WS-JF-001: hot work near but not touching a confined space ----------


def test_hot_work_adjacent_to_confined_space_is_a_judgment_flag():
    a = _wp("A", [H.HOT_WORK], (100, 110))
    b = _wp("B", [H.CONFINED_SPACE], (112, 120))
    assert check_conflict(a, b) is None  # detection misses it by design (known gap)
    [f] = judgment_flags([a, b])
    assert f.rule_id == "WS-JF-001"
    assert f.work_package_ids == ["A", "B"]
    assert f.routed_to.role == "Gas Free Engineer"
    assert f.routed_to.notional


def test_adjacency_threshold_boundary():
    edge = _wp("B", [H.CONFINED_SPACE], (110 + JUDGMENT_ADJACENCY_FRAMES, 120))
    beyond = _wp("B", [H.CONFINED_SPACE], (110 + JUDGMENT_ADJACENCY_FRAMES + 1, 120))
    a = _wp("A", [H.HOT_WORK], (100, 110))
    assert [f.rule_id for f in judgment_flags([a, edge])] == ["WS-JF-001"]
    assert judgment_flags([a, beyond]) == []


def test_adjacent_but_not_concurrent_is_not_flagged():
    a = _wp("A", [H.HOT_WORK], (100, 110))
    b = _wp("B", [H.CONFINED_SPACE], (112, 120), start=dt(2027, 2, 1, 7), end=dt(2027, 2, 1, 15))
    assert judgment_flags([a, b]) == []


def test_overlapping_hot_work_and_confined_space_is_a_conflict_not_a_judgment_flag():
    # Already caught by detection (WS-HZ-001); no duplicate judgment flag.
    a, b = _wp("A", [H.HOT_WORK], (100, 110)), _wp("B", [H.CONFINED_SPACE], (108, 120))
    assert check_conflict(a, b) is not None
    assert judgment_flags([a, b]) == []


# --- WS-JF-002: simultaneous confined-space entries ---------------------


def test_simultaneous_entries_in_same_compartment_are_flagged():
    a = _wp("A", [H.CONFINED_SPACE], (60, 70), compartment="TANK-4")
    b = _wp("B", [H.CONFINED_SPACE], (62, 68), compartment="TANK-4")
    [f] = judgment_flags([a, b])
    assert f.rule_id == "WS-JF-002"


def test_entries_in_different_spaces_and_frames_are_not_flagged():
    a = _wp("A", [H.CONFINED_SPACE], (60, 70), compartment="TANK-4")
    b = _wp("B", [H.CONFINED_SPACE], (90, 95), compartment="TANK-9")
    assert judgment_flags([a, b]) == []


def test_sequential_entries_in_same_space_are_not_flagged():
    a = _wp("A", [H.CONFINED_SPACE], compartment="TANK-4")
    b = _wp("B", [H.CONFINED_SPACE], compartment="TANK-4", start=dt(2027, 1, 13, 7), end=dt(2027, 1, 13, 15))
    assert judgment_flags([a, b]) == []


# --- WS-JF-003: gas-free hazard with no location ------------------------


@pytest.mark.parametrize("hazard", [H.HOT_WORK, H.CONFINED_SPACE])
def test_gas_free_hazard_with_no_location_is_flagged(hazard):
    [f] = judgment_flags([_wp("A", [hazard])])
    assert f.rule_id == "WS-JF-003"
    assert f.work_package_ids == ["A"]


def test_package_with_compartment_only_is_located():
    assert judgment_flags([_wp("A", [H.HOT_WORK], compartment="FR-40-2-A")]) == []


def test_unlocated_non_gas_free_hazard_is_not_a_gfe_flag():
    assert judgment_flags([_wp("A", [H.WORKING_ALOFT])]) == []


# --- determinism, routing, purity ---------------------------------------


def test_flags_are_deterministic_and_order_independent():
    pkgs = [
        _wp("C", [H.CONFINED_SPACE], (60, 70), compartment="TANK-4"),
        _wp("A", [H.HOT_WORK]),
        _wp("B", [H.CONFINED_SPACE], (62, 68), compartment="TANK-4"),
    ]
    first = judgment_flags(pkgs)
    assert [f.flag_id for f in first] == [f.flag_id for f in judgment_flags(list(reversed(pkgs)))]
    assert [f.flag_id for f in first] == ['WS-JF-002:["B","C"]', 'WS-JF-003:["A"]']


def test_flag_names_the_person_and_rule_in_its_message():
    [f] = judgment_flags([_wp("A", [H.HOT_WORK])])
    gfe = ROSTER.primary_for("Gas Free Engineer")
    assert f.routed_to.person_id == gfe.person_id
    assert gfe.display_name in f.message and "WS-JF-003" in f.message


def test_flags_never_mutate_packages():
    pkgs = [_wp("A", [H.HOT_WORK]), _wp("B", [H.CONFINED_SPACE], (60, 70))]
    before = [p.model_dump() for p in pkgs]
    judgment_flags(pkgs)
    assert [p.model_dump() for p in pkgs] == before


def test_known_gap_eval_scenarios_are_now_routed_to_a_human():
    by_id = {s.id: s for s in CONFLICT_SCENARIOS}
    for sid, rule in [("gap-adjacent-frames-not-touching", "WS-JF-001"),
                      ("gap-simultaneous-confined-space-entries", "WS-JF-002")]:
        assert rule in {f.rule_id for f in judgment_flags(by_id[sid].packages)}, sid
