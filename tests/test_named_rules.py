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


def test_contacts_are_roles_not_named_people():
    # Notional-data rule: no personnel names. Roles are title-case job titles with no digits
    # or contact details.
    for r in RULES:
        for role in (r.contact_role, r.escalation_role):
            if role:
                assert not re.search(r"\d|@", role), (r.rule_id, role)


def test_only_primary_source_checked_citations_are_marked_verified():
    verified = {c.source for r in RULES for c in r.citations if c.verified}
    # These were read against the primary-source PDF on 2026-08-08 (ADR-023);
    # nothing added in Session 4 may claim verification it didn't earn.
    assert verified <= {"NAVSEA8010-4.2", "NAVSEA8010-4.4.3", "NAVSEA8010-4.4.4"}


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
    expected = sorted({
        rule_for_hazard_pair(frozenset({H.HOT_WORK, H.CONFINED_SPACE})).rule_id,
        rule_for_hazard_pair(frozenset({H.HOT_WORK, H.WORKING_ALOFT})).rule_id,
    })
    assert conflict_rule_ids(a, b) == expected


def test_overhead_conflict_reports_overhead_rule_id():
    a, b = _wp("WP-A", [], aloft=True), _wp("WP-B", [])
    assert conflict_rule_ids(a, b) == [rule_for_overhead_work().rule_id]


def test_no_conflict_means_no_rule_ids():
    a, b = _wp("WP-A", [H.HOT_WORK]), _wp("WP-B", [H.CONFINED_SPACE], frames=(90, 94))
    assert check_conflict(a, b) is None
    assert conflict_rule_ids(a, b) == []


def test_rule_ids_agree_with_check_conflict_on_every_case():
    # Rule IDs and rationale come from one detection path, so they can never disagree.
    cases = [
        (_wp("A", [H.HOT_WORK]), _wp("B", [H.CONFINED_SPACE])),
        (_wp("A", [], aloft=True), _wp("B", [])),
        (_wp("A", [H.HOT_WORK]), _wp("B", [H.CONFINED_SPACE], frames=(90, 94))),
        (_wp("A", [H.WORKING_ALOFT]), _wp("B", [H.FALL_PROTECTION])),
    ]
    for a, b in cases:
        assert bool(conflict_rule_ids(a, b)) == (check_conflict(a, b) is not None)


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
