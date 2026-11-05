"""Regression tests for review-01 (Codex, Sessions 2-5). One or more per finding,
named test_rNN_*. Each was written to fail against 12d3873 before the fix.

All data is notional.
"""

from datetime import datetime as dt, timezone
from zoneinfo import ZoneInfo

import pytest

from agent_core import deconfliction, judgment, named_rules
from agent_core.certificates import Certificate, CertificateKind as K, check_certificates
from agent_core.crews import Crew, ShiftCalendar, Shift, Window, check_schedule_constraints
from agent_core.deconfliction import (
    check_conflict,
    conflict_rule_ids,
    deconfliction_node,
    find_all_conflicts,
)
from agent_core.judgment import Roster, RosterPerson, judgment_flags
from agent_core.projects import PackageStatus, Project, package_status, rollup_project
from agent_core.state import (
    HazardCategory as H,
    SafetyPermitsRequired,
    SpatialCoordinates as SC,
    WorkPackageState as W,
)

T0, T1 = dt(2027, 1, 12, 7), dt(2027, 1, 12, 15)
NONE = dict(certificate_findings=[], judgment_flags=[], schedule_findings=[])


def wp(pid="WP-1", hz=(), sp=None, start=T0, end=T1, **kw):
    return W(work_package_id=pid, description="notional", hazard_categories=list(hz),
             spatial=sp or SC(compartment_id="TANK-1"), scheduled_start=start, scheduled_end=end, **kw)


# --- R01 / R02 (D1): status is an AND gate over every check ---------------


def test_r01_review_required_after_construction_is_pending_not_cleared():
    p = wp()
    p.requires_hitl_review = True
    assert package_status(p, **NONE) == PackageStatus.PENDING_REVIEW


def test_r02_status_requires_every_check_as_an_input():
    with pytest.raises(TypeError):
        package_status(wp())  # a check that wasn't run is never read as clean


@pytest.mark.parametrize("missing", ["certificate_findings", "judgment_flags", "schedule_findings"])
def test_r02_none_for_any_input_is_an_error_not_clean(missing):
    kw = dict(NONE, **{missing: None})
    with pytest.raises(ValueError, match=missing):
        package_status(wp(), **kw)


def test_r02_package_with_open_findings_is_has_findings_not_cleared():
    p = wp(hz=[H.HOT_WORK], sp=SC(), permits_required=SafetyPermitsRequired(hot_work_permit=True))
    certs, flags = check_certificates(p, []), judgment_flags([p])
    assert certs and flags
    assert package_status(p, certificate_findings=certs, judgment_flags=flags,
                          schedule_findings=[]) == PackageStatus.HAS_FINDINGS


def test_r02_findings_for_other_packages_do_not_count():
    other = wp("WP-OTHER", hz=[H.HOT_WORK], sp=SC())
    assert package_status(wp(), certificate_findings=[], judgment_flags=judgment_flags([other]),
                          schedule_findings=[]) == PackageStatus.CLEARED


def test_r02_rollup_passes_findings_through_and_ranks_has_findings():
    p = wp(hz=[H.HOT_WORK], sp=SC())
    proj = Project(project_id="PRJ-1", name="notional", work_package_ids=["WP-1"])
    r = rollup_project(proj, [p], as_of=T0, certificate_findings=[],
                       judgment_flags=judgment_flags([p]), schedule_findings=[])
    assert r.overall_status == PackageStatus.HAS_FINDINGS
    order = list(PackageStatus)
    assert order.index(PackageStatus.PENDING_REVIEW) < order.index(PackageStatus.HAS_FINDINGS) \
        < order.index(PackageStatus.UNSCHEDULED)


def test_r02_rollup_requires_every_input():
    proj = Project(project_id="PRJ-1", name="notional", work_package_ids=["WP-1"])
    with pytest.raises(TypeError):
        rollup_project(proj, [wp()], as_of=T0)


# --- R03 / R13: compare instants, and refuse mixed naive/aware ----------

LA = ZoneInfo("America/Los_Angeles")
PDT0, PDT1 = dt(2026, 11, 1, 1, 15, tzinfo=LA), dt(2026, 11, 1, 1, 45, tzinfo=LA)
PST0, PST1 = PDT0.replace(fold=1), PDT1.replace(fold=1)


def test_r03_permit_expiring_in_the_first_repeated_hour_does_not_cover_the_second():
    p = wp(start=PST0, end=PST1, permits_required=SafetyPermitsRequired(hot_work_permit=True))
    c = Certificate(certificate_id="C", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                    valid_from=PDT0, valid_until=PDT1)
    [f] = check_certificates(p, [c])
    assert f.uncovered and f.issue.value == "not_covered"


def test_r03_schedule_order_uses_real_time_across_the_repeated_hour():
    # 01:45 PDT (08:45Z) is genuinely before 01:15 PST (09:15Z): a valid schedule.
    p = wp(start=PDT1, end=PST0)
    assert p.scheduled_start == PDT1


def test_r03_overlap_uses_real_time():
    a = wp("A", [H.HOT_WORK], start=PDT0, end=PDT1)
    b = wp("B", [H.CONFINED_SPACE], start=PST0, end=PST1)
    assert check_conflict(a, b) is None  # 30 real minutes apart


def test_r13_mixed_naive_and_aware_raises_a_clear_error():
    p = wp(permits_required=SafetyPermitsRequired(hot_work_permit=True))
    c = Certificate(certificate_id="C", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                    valid_from=dt(2027, 1, 12, tzinfo=timezone.utc), valid_until=dt(2027, 1, 13, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="timezone"):
        check_certificates(p, [c])


def test_r13_mixed_due_date_and_schedule_raises_a_clear_error():
    proj = Project(project_id="PRJ-1", name="n", due_date=dt(2027, 1, 20, tzinfo=timezone.utc),
                   work_package_ids=["WP-1"])
    with pytest.raises(ValueError, match="timezone"):
        rollup_project(proj, [wp()], as_of=dt(2027, 1, 10, tzinfo=timezone.utc), **NONE)


# --- R04: unknown permit or spatial keys refuse to load -------------------


def test_r04_misspelled_permit_flag_is_rejected():
    with pytest.raises(ValueError):
        wp(permits_required={"hot_work_permti": True})


def test_r04_misspelled_spatial_flag_is_rejected():
    with pytest.raises(ValueError):
        SC(is_alof=True)


# --- R05 / R11: blank identifiers refuse to load ---------------------------


@pytest.mark.parametrize("bad", ["", "   "])
def test_r05_blank_ids_rejected_everywhere(bad):
    with pytest.raises(ValueError):
        wp(pid=bad)
    with pytest.raises(ValueError):
        Certificate(certificate_id=bad, work_package_id="WP-1", kind=K.HOT_WORK_PERMIT, valid_from=T0, valid_until=T1)
    with pytest.raises(ValueError):
        Certificate(certificate_id="C", work_package_id=bad, kind=K.HOT_WORK_PERMIT, valid_from=T0, valid_until=T1)
    with pytest.raises(ValueError):
        Crew(crew_id=bad, name="n")
    with pytest.raises(ValueError):
        Project(project_id=bad, name="n")
    with pytest.raises(ValueError):
        Shift(shift_id=bad, name="n", start=T0, end=T1)


@pytest.mark.parametrize("field", ["person_id", "display_name", "role"])
def test_r11_blank_roster_fields_rejected(field):
    p = dict(person_id="P-1", display_name="Riley Example", role="Gas Free Engineer", primary=True, notional=True)
    p[field] = "  "
    with pytest.raises(ValueError):
        RosterPerson(**p)


# --- R06: duplicate package IDs in a batch raise ---------------------------


def test_r06_duplicate_ids_raise_in_conflict_and_judgment_batches():
    a = wp("A", [H.HOT_WORK])
    b = wp("A", [H.CONFINED_SPACE])
    with pytest.raises(ValueError, match="duplicate"):
        find_all_conflicts([a, b])
    with pytest.raises(ValueError, match="duplicate"):
        judgment_flags([a, b])


# --- R07: no common coordinate, and whitespace compartments ---------------


def test_r07_concurrent_gas_free_pair_with_no_common_coordinate_is_flagged():
    a = wp("A", [H.HOT_WORK], SC(compartment_id="TANK-1"))
    b = wp("B", [H.CONFINED_SPACE], SC(frame_start=1, frame_end=3))
    assert check_conflict(a, b) is None
    assert "WS-JF-004" in {f.rule_id for f in judgment_flags([a, b])}


def test_r07_comparable_pair_is_not_a_no_common_coordinate_flag():
    a = wp("A", [H.HOT_WORK], SC(frame_start=1, frame_end=3))
    b = wp("B", [H.CONFINED_SPACE], SC(frame_start=50, frame_end=60))
    assert "WS-JF-004" not in {f.rule_id for f in judgment_flags([a, b])}


def test_r07_whitespace_compartment_is_no_location():
    assert SC(compartment_id="   ").compartment_id is None
    assert [f.rule_id for f in judgment_flags([wp("C", [H.HOT_WORK], SC(compartment_id="  "))])] == ["WS-JF-003"]


# --- R08: entry identified by spatial flag or permit, not hazard list -----


def test_r08_unlabelled_confined_entry_with_no_location_is_flagged():
    p = wp(sp=SC(is_enclosed_or_confined=True),
           permits_required=SafetyPermitsRequired(confined_space_entry_permit=True))
    ids = {f.rule_id for f in judgment_flags([p])}
    assert "WS-JF-003" in ids  # no location
    assert "WS-JF-005" in ids  # classification inconsistent


def test_r08_hot_work_permit_without_hot_work_hazard_is_inconsistent():
    p = wp(permits_required=SafetyPermitsRequired(hot_work_permit=True))
    assert "WS-JF-005" in {f.rule_id for f in judgment_flags([p])}


def test_r08_consistent_labels_raise_no_classification_flag():
    p = wp(hz=[H.CONFINED_SPACE], sp=SC(compartment_id="TANK-1", is_enclosed_or_confined=True),
           permits_required=SafetyPermitsRequired(confined_space_entry_permit=True))
    assert judgment_flags([p]) == []


def test_r08_spatial_signal_feeds_adjacency_trigger():
    a = wp("A", [H.HOT_WORK], SC(frame_start=100, frame_end=110))
    b = wp("B", [], SC(frame_start=112, frame_end=120, is_enclosed_or_confined=True))
    assert "WS-JF-001" in {f.rule_id for f in judgment_flags([a, b])}


# --- R09 (D2): one package overloading its own fire watch -----------------


def test_r09_single_package_overload_is_reported_and_routed_to_review():
    p = wp(hz=[H.HOT_WORK], fire_watch_id="FW-1", hot_worker_count=5)
    find_all_conflicts([p])
    assert p.conflict_rationale and "FW-1" in p.conflict_rationale
    out = deconfliction_node({"work_packages": [wp(hz=[H.HOT_WORK], fire_watch_id="FW-1", hot_worker_count=5)]})
    q = out["work_packages"][0]
    assert q.requires_hitl_review and not q.cleared_for_execution
    assert out["requires_hitl_review"] is True


def test_r09_at_the_limit_is_not_flagged():
    p = wp(hz=[H.HOT_WORK], fire_watch_id="FW-1", hot_worker_count=4)
    find_all_conflicts([p])
    assert not p.conflict_rationale


# --- R10: every applicable rule ID is returned ------------------------------


def test_r10_hazard_pair_and_overhead_both_reported():
    a = wp("A", [H.HOT_WORK], SC(frame_start=10, frame_end=12, is_aloft=True))
    b = wp("B", [H.CONFINED_SPACE], SC(frame_start=10, frame_end=12))
    assert conflict_rule_ids(a, b) == ["WS-HZ-001", "WS-OH-001"]


# --- R12: flag IDs can't collide --------------------------------------------


def test_r12_distinct_pairs_get_distinct_flag_ids():
    pk = [wp("A+B", [H.CONFINED_SPACE], SC(compartment_id="T1")), wp("C", [H.CONFINED_SPACE], SC(compartment_id="T1")),
          wp("A", [H.CONFINED_SPACE], SC(compartment_id="T2")), wp("B+C", [H.CONFINED_SPACE], SC(compartment_id="T2"))]
    ids = [f.flag_id for f in judgment_flags(pk) if f.rule_id == "WS-JF-002"]
    assert len(ids) == 2 and len(set(ids)) == 2


# --- R14: messages show seconds when they matter ---------------------------


def test_r14_sub_minute_gap_is_readable():
    p = wp(start=dt(2027, 1, 12, 6), end=dt(2027, 1, 12, 8), permits_required=SafetyPermitsRequired(hot_work_permit=True))
    cs = [Certificate(certificate_id="C1", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                      valid_from=dt(2027, 1, 12, 6), valid_until=dt(2027, 1, 12, 7, 0, 10)),
          Certificate(certificate_id="C2", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                      valid_from=dt(2027, 1, 12, 7, 0, 30), valid_until=dt(2027, 1, 12, 8))]
    [f] = check_certificates(p, cs)
    assert "07:00:10 to 2027-01-12 07:00:30" in f.message


# --- R17: judgment catalogue and implemented triggers match both ways -----


def test_r17_catalogue_judgment_ids_equal_implemented_triggers():
    catalogue = {r.rule_id for r in named_rules.RULES if r.category == named_rules.RuleCategory.JUDGMENT}
    assert catalogue == judgment.IMPLEMENTED_TRIGGERS


def test_r17_untriggered_catalogue_rule_refuses_to_run(monkeypatch):
    extra = named_rules.NamedRule(rule_id="WS-JF-099", title="untriggered", category="judgment",
                                  contact_role="Gas Free Engineer", note="probe")
    monkeypatch.setattr(named_rules, "RULES", named_rules.RULES + [extra])
    with pytest.raises(LookupError, match="WS-JF-099"):
        judgment_flags([wp()])


# ===== review-01 re-check (reopened R02, R06, R09, R13, R14; new N01-N05) =====

from datetime import timedelta  # noqa: E402

from agent_core import events  # noqa: E402
from agent_core.reasoning import reasoning_node  # noqa: E402
from agent_core.reschedule_suggestion import suggest_reschedule  # noqa: E402


def test_recheck_r02_one_shot_iterator_of_findings_is_refused():
    b = wp("B", permits_required=SafetyPermitsRequired(hot_work_permit=True))
    with pytest.raises(TypeError, match="collection"):
        package_status(b, certificate_findings=iter(check_certificates(b, [])),
                       judgment_flags=[], schedule_findings=[])


def test_recheck_r02_reusing_the_same_list_for_every_package_is_correct():
    a = wp("A")
    b = wp("B", permits_required=SafetyPermitsRequired(hot_work_permit=True))
    certs = check_certificates(b, [])
    kw = dict(certificate_findings=certs, judgment_flags=[], schedule_findings=[])
    assert package_status(a, **kw) == PackageStatus.CLEARED
    assert package_status(b, **kw) == PackageStatus.HAS_FINDINGS


def test_recheck_r06_distinct_records_sharing_an_id_raise_in_the_pair_api():
    a, b = wp("X", [H.HOT_WORK]), wp("X", [H.CONFINED_SPACE])
    with pytest.raises(ValueError, match="share work_package_id"):
        check_conflict(a, b)


def test_recheck_r06_true_self_comparison_is_still_no_conflict():
    a = wp("X", [H.HOT_WORK])
    assert check_conflict(a, a) is None


def _two_day_overload():
    return [wp("A", [H.HOT_WORK], fire_watch_id="F", hot_worker_count=5),
            wp("B", [H.HOT_WORK], fire_watch_id="F", hot_worker_count=5,
               start=dt(2027, 1, 13, 7), end=dt(2027, 1, 13, 15))]


def test_recheck_r09_every_overloaded_package_on_a_watch_goes_to_review():
    out = deconfliction_node({"work_packages": _two_day_overload()})["work_packages"]
    for p in out:
        assert p.requires_hitl_review and not p.cleared_for_execution, p.work_package_id


def test_recheck_r09_package_never_concurrent_with_the_overload_is_not_flagged():
    pkgs = [wp("A", [H.HOT_WORK], fire_watch_id="F", hot_worker_count=3),
            wp("B", [H.HOT_WORK], fire_watch_id="F", hot_worker_count=2, start=dt(2027, 1, 12, 9), end=dt(2027, 1, 12, 11)),
            wp("C", [H.HOT_WORK], fire_watch_id="F", hot_worker_count=1, start=dt(2027, 1, 14, 7), end=dt(2027, 1, 14, 9))]
    find_all_conflicts(pkgs)
    by = {p.work_package_id: p for p in pkgs}
    assert by["A"].conflict_rationale and by["B"].conflict_rationale
    assert not by["C"].conflict_rationale


def test_recheck_r13_mixed_certificate_times_give_a_descriptive_error():
    p = wp(permits_required=SafetyPermitsRequired(hot_work_permit=True))
    cs = [Certificate(certificate_id="C1", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                      valid_from=dt(2027, 1, 12, 7), valid_until=dt(2027, 1, 12, 11)),
          Certificate(certificate_id="C2", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                      valid_from=dt(2027, 1, 12, 11, tzinfo=timezone.utc),
                      valid_until=dt(2027, 1, 12, 16, tzinfo=timezone.utc))]
    with pytest.raises(ValueError, match="timezone"):
        check_certificates(p, cs)


def test_recheck_r14_microsecond_gap_is_readable():
    p = wp(start=dt(2027, 1, 12, 9), end=dt(2027, 1, 12, 10), permits_required=SafetyPermitsRequired(hot_work_permit=True))
    cs = [Certificate(certificate_id="C1", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                      valid_from=dt(2027, 1, 12, 9), valid_until=dt(2027, 1, 12, 9, 15, 10, 2)),
          Certificate(certificate_id="C2", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                      valid_from=dt(2027, 1, 12, 9, 15, 10, 8), valid_until=dt(2027, 1, 12, 10))]
    [f] = check_certificates(p, cs)
    assert "09:15:10.000002 to 2027-01-12 09:15:10.000008" in f.message


def test_recheck_n01_self_overload_is_in_the_event_and_gets_a_brief(monkeypatch):
    seen = []
    monkeypatch.setattr(events, "emit", lambda name, **kw: seen.append((name, kw)))
    state = deconfliction_node({"work_packages": [wp(hz=[H.HOT_WORK], fire_watch_id="F", hot_worker_count=5)]})
    state = reasoning_node(state)
    [result] = [kw for n, kw in seen if n == "deconfliction_result"]
    assert [c["work_package_id"] for c in result["conflicts"]] == ["WP-1"]
    assert result["conflicts"][0]["conflicts_with"] == []
    assert state["work_packages"][0].safety_brief is not None


def test_recheck_n02_self_overload_gets_no_reschedule_suggestion():
    p = wp(hz=[H.HOT_WORK], fire_watch_id="F", hot_worker_count=5)
    assert suggest_reschedule([p], "WP-1", step=timedelta(hours=1), max_shift=timedelta(days=1)) is None


def test_recheck_n02_suggestion_never_lands_in_an_overload_with_another_package():
    other = wp("B", [H.HOT_WORK], fire_watch_id="F", hot_worker_count=3, start=dt(2027, 1, 12, 15), end=dt(2027, 1, 12, 23))
    target = wp("A", [H.HOT_WORK], sp=SC(compartment_id="TANK-1"), fire_watch_id="F", hot_worker_count=3)
    blocker = wp("C", [H.CONFINED_SPACE], sp=SC(compartment_id="TANK-1"))
    s = suggest_reschedule([target, other, blocker], "A", step=timedelta(hours=1), max_shift=timedelta(hours=12))
    if s is not None:
        moved = target.model_copy(update={"scheduled_start": s.suggested_start, "scheduled_end": s.suggested_end})
        assert not [o for o in deconfliction.fire_watch_overloads([moved, other])
                    if "A" in [p.work_package_id for p in o[2]]]


def test_recheck_n03_suggestion_across_the_repeated_hour_keeps_its_real_duration():
    start, end = dt(2026, 11, 1, 1, 45, tzinfo=LA), dt(2026, 11, 1, 1, 15, fold=1, tzinfo=LA)
    a, b = wp("A", [H.HOT_WORK], start=start, end=end), wp("B", [H.CONFINED_SPACE], start=start, end=end)
    s = suggest_reschedule([a, b], "A", step=timedelta(hours=1), max_shift=timedelta(hours=3))
    assert s is not None
    real = lambda t: t.astimezone(timezone.utc)
    assert real(s.suggested_end) - real(s.suggested_start) == timedelta(minutes=30)
    assert s.suggested_start.tzinfo is LA


def test_recheck_n04_aware_gap_is_reported_in_the_work_zone_with_offset():
    s0, s1 = dt(2026, 11, 1, 1, 15, fold=1, tzinfo=LA), dt(2026, 11, 1, 1, 45, fold=1, tzinfo=LA)
    p = wp(start=s0, end=s1, permits_required=SafetyPermitsRequired(hot_work_permit=True))
    c = Certificate(certificate_id="C", work_package_id="WP-1", kind=K.HOT_WORK_PERMIT,
                    valid_from=dt(2026, 11, 1, 1, 15, tzinfo=LA), valid_until=dt(2026, 11, 1, 1, 45, tzinfo=LA))
    [f] = check_certificates(p, [c])
    assert "01:15 -08:00" in f.message and "01:45 -08:00" in f.message
    assert f.uncovered[0][0].utcoffset() == timedelta(hours=-8)


def test_recheck_n05_rollup_without_due_date_does_not_compare_unrelated_times():
    proj = Project(project_id="P", name="n", work_package_ids=["WP-1"])
    aware = wp(start=dt(2027, 1, 12, 7, tzinfo=timezone.utc), end=dt(2027, 1, 12, 15, tzinfo=timezone.utc))
    r = rollup_project(proj, [aware], as_of=dt(2027, 1, 10), **NONE)
    assert r.past_due is False and r.late_package_ids == []
