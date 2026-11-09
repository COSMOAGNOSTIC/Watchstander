"""Session 4: named rules with IDs, CFR cites, and who-to-call.

All data here is notional -- contacts are roles, never named people.
"""

import json
import re
from datetime import datetime as dt

import pytest

from agent_core import named_rules
from agent_core.certificates import Certificate, CertificateKind, check_certificates
from agent_core.deconfliction import INCOMPATIBLE_HAZARD_PAIRS, check_conflict, conflict_rule_ids
from agent_core.named_rules import (
    NamedRule,
    RuleCategory,
    get_rule,
    load_named_rules,
    rule_for_certificate_kind,
    rule_for_fire_watch_capacity,
    rule_for_hazard_pair,
    rule_for_overhead_work,
)
from agent_core.state import (
    HazardCategory as H,
    SafetyPermitsRequired,
    SpatialCoordinates,
    WorkPackageState,
)

RULES = load_named_rules()


def _rule_dict(**over):
    base = dict(
        rule_id="WS-HZ-099", title="t", category="hazard_pair",
        applies_to=["hot_work", "confined_space"],
        citations=[{"source": "29 CFR 1915.14", "verified": False}],
        contact_role="Gas Free Engineer", escalation_role="Safety Officer",
    )
    base.update(over)
    return base


# --- catalogue structure ---------------------------------------------------


def test_rule_ids_are_unique_and_well_formed():
    ids = [r.rule_id for r in RULES]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"WS-[A-Z]{2}-\d{3}", i) for i in ids)


def test_every_rule_has_a_contact_role_and_at_least_one_citation_or_a_note():
    for r in RULES:
        assert r.contact_role.strip()
        assert r.citations or (r.note and r.note.strip()), r.rule_id


# review-01 R16: the old check only rejected digits and "@", so a person's name
# ("Riley Example") passed. Contacts must come from this explicit role set.
ALLOWED_ROLES = {
    # review-05 (Donnie): aloft is authorized by the CSOOW (chit) or the CO (standing aloft).
    "Combat Systems Officer of the Watch (CSOOW)", "Commanding Officer",
    "Gas Free Engineer", "Safety Officer", "Fire Safety Coordinator", "Competent Person",
    "Production Planner", "Ship Superintendent",
}


def test_contacts_are_roles_not_named_people():
    for r in RULES:
        for role in (r.contact_role, r.escalation_role):
            if role is not None:
                assert role in ALLOWED_ROLES, (r.rule_id, role)


def test_no_contact_role_is_a_roster_name():
    from agent_core.judgment import load_roster
    names = {p.display_name for p in load_roster().people}
    for r in RULES:
        assert r.contact_role not in names and r.escalation_role not in names, r.rule_id


def test_only_primary_source_checked_citations_are_marked_verified():
    # A NAVSEA cite may say verified only if the site ruleset says so (read against the
    # primary-source PDF, ADR-023). No 29 CFR cite has been read against eCFR yet.
    with open("case_data/navsea_8010_psns_v2014.json", encoding="utf-8") as f:
        site = {p["procedure_id"]: p["verified"] for p in json.load(f)["procedures"]}
    for r in RULES:
        for c in r.citations:
            if c.source.startswith("NAVSEA"):
                assert c.verified == site[c.source], (r.rule_id, c.source)
            else:
                assert c.verified is False, (r.rule_id, c.source)


def test_navsea_citations_exist_in_the_site_ruleset():
    with open("case_data/navsea_8010_psns_v2014.json", encoding="utf-8") as f:
        known = {p["procedure_id"] for p in json.load(f)["procedures"]}
    cited = {c.source for r in RULES for c in r.citations if c.source.startswith("NAVSEA")}
    assert cited <= known


# --- completeness against what detection actually checks ------------------


def test_every_incompatible_hazard_pair_has_exactly_one_rule():
    for pair in INCOMPATIBLE_HAZARD_PAIRS:
        matches = [r for r in RULES if r.category == RuleCategory.HAZARD_PAIR
                   and frozenset(r.applies_to) == frozenset(h.value for h in pair)]
        assert len(matches) == 1, pair


def test_no_hazard_pair_rule_for_a_pair_detection_does_not_check():
    detected = {frozenset(h.value for h in p) for p in INCOMPATIBLE_HAZARD_PAIRS}
    for r in RULES:
        if r.category == RuleCategory.HAZARD_PAIR:
            assert frozenset(r.applies_to) in detected, r.rule_id


def test_every_certificate_kind_has_exactly_one_rule():
    for kind in CertificateKind:
        assert rule_for_certificate_kind(kind).applies_to == [kind.value]


def test_exactly_one_overhead_rule_and_one_fire_watch_rule():
    assert rule_for_overhead_work().category == RuleCategory.OVERHEAD
    assert rule_for_fire_watch_capacity().category == RuleCategory.FIRE_WATCH


def test_fire_watch_rule_cites_verified_navsea_limit():
    r = rule_for_fire_watch_capacity()
    assert any(c.source == "NAVSEA8010-4.4.3" and c.verified for c in r.citations)


# --- lookups -------------------------------------------------------------


def test_get_rule_by_id_and_unknown_id_raises():
    r = rule_for_hazard_pair(frozenset({H.HOT_WORK, H.CONFINED_SPACE}))
    assert get_rule(r.rule_id) is r
    with pytest.raises(KeyError):
        get_rule("WS-XX-999")


def test_hazard_pair_lookup_is_order_independent():
    a = rule_for_hazard_pair(frozenset({H.HOT_WORK, H.WORKING_ALOFT}))
    b = rule_for_hazard_pair(frozenset({H.WORKING_ALOFT, H.HOT_WORK}))
    assert a is b


def test_unknown_hazard_pair_raises():
    with pytest.raises(KeyError):
        rule_for_hazard_pair(frozenset({H.OVER_THE_SIDE, H.CONFINED_SPACE}))


# --- validation fails loudly ---------------------------------------------


def _load(tmp_path, rules):
    p = tmp_path / "rules.json"
    p.write_text(json.dumps({"schema_version": 1, "rules": rules}))
    return load_named_rules(p)


def test_duplicate_rule_id_refuses_to_load(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        _load(tmp_path, [_rule_dict(), _rule_dict()])


def test_malformed_rule_id_refuses_to_load(tmp_path):
    with pytest.raises(ValueError):
        _load(tmp_path, [_rule_dict(rule_id="rule-1")])


def test_unknown_hazard_category_refuses_to_load(tmp_path):
    with pytest.raises(ValueError, match="unknown"):
        _load(tmp_path, [_rule_dict(applies_to=["hot_work", "lava"])])


def test_unknown_certificate_kind_refuses_to_load(tmp_path):
    with pytest.raises(ValueError, match="unknown"):
        _load(tmp_path, [_rule_dict(rule_id="WS-CT-099", category="certificate",
                                    applies_to=["gas_free_cert"])])


def test_blank_contact_role_refuses_to_load(tmp_path):
    with pytest.raises(ValueError):
        _load(tmp_path, [_rule_dict(contact_role="  ")])


def test_wrong_schema_version_refuses_to_load(tmp_path):
    p = tmp_path / "rules.json"
    p.write_text(json.dumps({"schema_version": 2, "rules": [_rule_dict()]}))
    with pytest.raises(ValueError, match="schema_version"):
        load_named_rules(p)


def test_checked_in_file_matches_the_model():
    assert all(isinstance(r, NamedRule) for r in RULES)
    assert named_rules.RULES_BY_ID.keys() == {r.rule_id for r in RULES}


# --- detection reports rule IDs ------------------------------------------


def _wp(pid, hazards, frames=(40, 44), aloft=False, **kw):
    return WorkPackageState(
        work_package_id=pid, description=f"notional {pid}", hazard_categories=hazards,
        spatial=SpatialCoordinates(frame_start=frames[0], frame_end=frames[1], is_aloft=aloft),
        scheduled_start=dt(2027, 1, 12, 7), scheduled_end=dt(2027, 1, 12, 15), **kw,
    )


def test_hazard_pair_conflict_reports_its_rule_id():
    a, b = _wp("WP-A", [H.HOT_WORK]), _wp("WP-B", [H.CONFINED_SPACE])
    assert conflict_rule_ids(a, b) == [rule_for_hazard_pair(frozenset({H.HOT_WORK, H.CONFINED_SPACE})).rule_id]


def test_multiple_matching_pairs_report_every_rule_id_sorted():
    a = _wp("WP-A", [H.HOT_WORK])
    b = _wp("WP-B", [H.CONFINED_SPACE, H.WORKING_ALOFT])
    # Session 8a: B's working_aloft label now makes it overhead, so the overhead rule applies too.
    expected = sorted({
        rule_for_hazard_pair(frozenset({H.HOT_WORK, H.CONFINED_SPACE})).rule_id,
        rule_for_hazard_pair(frozenset({H.HOT_WORK, H.WORKING_ALOFT})).rule_id,
        rule_for_overhead_work().rule_id,
    })
    assert conflict_rule_ids(a, b) == expected


def test_overhead_conflict_reports_overhead_rule_id():
    a, b = _wp("WP-A", [], aloft=True), _wp("WP-B", [])
    assert conflict_rule_ids(a, b) == [rule_for_overhead_work().rule_id]


def test_no_conflict_means_no_rule_ids():
    a, b = _wp("WP-A", [H.HOT_WORK]), _wp("WP-B", [H.CONFINED_SPACE], frames=(90, 94))
    assert check_conflict(a, b) is None
    assert conflict_rule_ids(a, b) == []


def test_rule_ids_and_rationale_match_independent_expectations():
    # review-01 R15: the old version compared the two wrappers with each other,
    # so a detector that never detects passed. Each case now has its own answer.
    cases = [
        (_wp("A", [H.HOT_WORK]), _wp("B", [H.CONFINED_SPACE]), ["WS-HZ-001"]),
        (_wp("A", [], aloft=True), _wp("B", []), ["WS-OH-001"]),
        (_wp("A", [H.HOT_WORK]), _wp("B", [H.CONFINED_SPACE], frames=(90, 94)), []),
        # Session 8a: labelled aloft work over fall-protection work in the same frames is overhead too.
        (_wp("A", [H.WORKING_ALOFT]), _wp("B", [H.FALL_PROTECTION]), ["WS-HZ-003", "WS-OH-001"]),
    ]
    for a, b, expected in cases:
        assert conflict_rule_ids(a, b) == expected, (a.work_package_id, b.work_package_id)
        assert (check_conflict(a, b) is not None) == bool(expected)


def test_certificate_findings_carry_their_rule_id():
    pkg = WorkPackageState(
        work_package_id="WP-1", description="notional",
        scheduled_start=dt(2027, 1, 12, 7), scheduled_end=dt(2027, 1, 12, 19),
        permits_required=SafetyPermitsRequired(hot_work_permit=True),
    )
    [f] = check_certificates(pkg, [Certificate(
        certificate_id="C-1", work_package_id="WP-1", kind=CertificateKind.HOT_WORK_PERMIT,
        valid_from=dt(2027, 1, 12, 7), valid_until=dt(2027, 1, 12, 15))])
    assert f.rule_id == rule_for_certificate_kind(CertificateKind.HOT_WORK_PERMIT).rule_id
