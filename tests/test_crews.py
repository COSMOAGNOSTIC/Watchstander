"""Session 6: crews, a shift calendar, locked packages, contractor windows.

All data here is notional -- no real ship, yard, or personnel data.
"""

from datetime import date, datetime as dt, time

import pytest

from agent_core.crews import (
    Crew,
    ScheduleIssue,
    Shift,
    ShiftCalendar,
    Window,
    check_schedule_constraints,
    is_movable,
)
from agent_core.intervals import uncovered
from agent_core.named_rules import RuleCategory, get_rule
from agent_core.state import WorkPackageState

PATTERN = [("DAY", time(7), time(15, 30)), ("SWING", time(15, 30), time(0)), ("MID", time(0), time(7))]
DAY_ONLY = [("DAY", time(7), time(15, 30))]


def _cal(pattern=DAY_ONLY, days=3):
    return ShiftCalendar.from_daily_pattern(date(2027, 1, 11), days, pattern)


def _wp(pid, start=dt(2027, 1, 12, 7), end=dt(2027, 1, 12, 15), **kw):
    return WorkPackageState(work_package_id=pid, description=f"notional {pid}",
                            scheduled_start=start, scheduled_end=end, **kw)


ORGANIC = Crew(crew_id="CR-PIPE-1", name="Notional pipefitter crew 1")
CONTRACTOR = Crew(crew_id="CR-BLAST-K", name="Notional blast contractor", is_contractor=True,
                  contractor_windows=[Window(start=dt(2027, 1, 12, 7), end=dt(2027, 1, 12, 15, 30))])


def _check(pkgs, crews=(ORGANIC, CONTRACTOR), cal=None):
    return check_schedule_constraints(pkgs, list(crews), cal or _cal())


# --- shared interval helper ---------------------------------------------


def test_uncovered_reports_gaps_and_treats_touching_windows_as_continuous():
    a, b, c = dt(2027, 1, 1, 0), dt(2027, 1, 1, 12), dt(2027, 1, 2, 0)
    assert uncovered(a, c, [(a, b), (b, c)]) == []
    assert uncovered(a, c, [(a, b)]) == [(b, c)]
    assert uncovered(a, a, []) == [(a, a)]


# --- shift calendar -----------------------------------------------------


def test_daily_pattern_builds_ids_and_crosses_midnight():
    cal = _cal(PATTERN, days=1)
    assert [s.shift_id for s in cal.shifts] == ["20270111-MID", "20270111-DAY", "20270111-SWING"]
    swing = cal.shifts[-1]
    assert (swing.start, swing.end) == (dt(2027, 1, 11, 15, 30), dt(2027, 1, 12, 0))


def test_overnight_shift_ends_next_day():
    cal = ShiftCalendar.from_daily_pattern(date(2027, 1, 11), 1, [("NIGHT", time(23), time(7))])
    assert (cal.shifts[0].start, cal.shifts[0].end) == (dt(2027, 1, 11, 23), dt(2027, 1, 12, 7))


def test_overlapping_shifts_refuse_to_build():
    with pytest.raises(ValueError, match="overlap"):
        ShiftCalendar(shifts=[
            Shift(shift_id="A", name="A", start=dt(2027, 1, 1, 7), end=dt(2027, 1, 1, 16)),
            Shift(shift_id="B", name="B", start=dt(2027, 1, 1, 15), end=dt(2027, 1, 1, 23)),
        ])


def test_zero_length_shift_is_rejected():
    with pytest.raises(ValueError):
        Shift(shift_id="A", name="A", start=dt(2027, 1, 1, 7), end=dt(2027, 1, 1, 7))


def test_duplicate_shift_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        ShiftCalendar(shifts=[
            Shift(shift_id="A", name="A", start=dt(2027, 1, 1, 7), end=dt(2027, 1, 1, 8)),
            Shift(shift_id="A", name="A", start=dt(2027, 1, 2, 7), end=dt(2027, 1, 2, 8)),
        ])


def test_shift_at_uses_half_open_membership():
    cal = _cal(PATTERN, days=1)
    assert cal.shift_at(dt(2027, 1, 11, 15, 30)).name == "SWING"
    assert cal.shift_at(dt(2027, 1, 11, 15, 29)).name == "DAY"
    assert _cal(DAY_ONLY).shift_at(dt(2027, 1, 11, 20)) is None


def test_next_shift_starts_at_or_after_the_given_time():
    cal = _cal()
    assert cal.next_shift(dt(2027, 1, 11, 9)).shift_id == "20270112-DAY"
    assert cal.next_shift(dt(2027, 1, 12, 7)).shift_id == "20270112-DAY"
    assert cal.next_shift(dt(2027, 1, 13, 8)) is None


# --- crews and locks ----------------------------------------------------


def test_organic_crew_cannot_carry_contractor_windows():
    with pytest.raises(ValueError, match="contractor"):
        Crew(crew_id="CR-1", name="x", contractor_windows=[Window(start=dt(2027, 1, 1), end=dt(2027, 1, 2))])


def test_window_must_be_ordered():
    with pytest.raises(ValueError):
        Window(start=dt(2027, 1, 2), end=dt(2027, 1, 1))


def test_locked_package_requires_a_reason():
    with pytest.raises(ValueError, match="lock_reason"):
        _wp("WP-1", locked=True)


def test_is_movable_respects_lock():
    assert is_movable(_wp("WP-1")) is True
    assert is_movable(_wp("WP-1", locked=True, lock_reason="notional dry-dock flood-up milestone")) is False


def test_new_package_fields_default_to_unassigned_and_unlocked():
    p = _wp("WP-1")
    assert (p.crew_id, p.locked, p.lock_reason) == (None, False, None)


# --- WS-SC-001 unknown crew ---------------------------------------------


def test_unknown_crew_is_flagged():
    [f] = _check([_wp("WP-1", crew_id="CR-GHOST")])
    assert (f.issue, f.rule_id) == (ScheduleIssue.UNKNOWN_CREW, "WS-SC-001")


def test_unassigned_package_is_not_flagged():
    assert _check([_wp("WP-1")]) == []


# --- WS-SC-002 contractor windows ---------------------------------------


def test_contractor_work_inside_window_passes():
    assert _check([_wp("WP-1", crew_id="CR-BLAST-K")]) == []


def test_contractor_work_running_past_window_reports_the_overrun():
    # Window is 0700-1530; job runs 0700-1800. Calendar has all three shifts so
    # only the contractor window can fire.
    [f] = _check([_wp("WP-1", end=dt(2027, 1, 12, 18), crew_id="CR-BLAST-K")], cal=_cal(PATTERN))
    assert (f.issue, f.rule_id, f.work_package_ids) == (
        ScheduleIssue.OUTSIDE_CONTRACTOR_WINDOW, "WS-SC-002", ["WP-1"])
    assert f.uncovered == [(dt(2027, 1, 12, 15, 30), dt(2027, 1, 12, 18))]


def test_contractor_work_ending_exactly_at_window_close_passes():
    assert _check([_wp("WP-1", end=dt(2027, 1, 12, 15, 30), crew_id="CR-BLAST-K")]) == []


def test_contractor_with_no_windows_flags_every_package():
    c = Crew(crew_id="CR-K2", name="Notional contractor 2", is_contractor=True)
    [f] = _check([_wp("WP-1", crew_id="CR-K2")], crews=[c])
    assert f.issue == ScheduleIssue.OUTSIDE_CONTRACTOR_WINDOW


def test_unscheduled_contractor_package_cannot_be_verified():
    [f] = _check([_wp("WP-1", start=None, end=None, crew_id="CR-BLAST-K")])
    assert (f.issue, f.rule_id) == (ScheduleIssue.UNSCHEDULED, "WS-SC-002")


def test_organic_crew_has_no_window_constraint():
    assert _check([_wp("WP-1", start=dt(2027, 1, 13, 7), end=dt(2027, 1, 13, 15), crew_id="CR-PIPE-1")]) == []


# --- WS-SC-003 outside the shift calendar -------------------------------


def test_work_outside_any_shift_is_flagged_with_the_gap():
    [f] = _check([_wp("WP-1", start=dt(2027, 1, 12, 14), end=dt(2027, 1, 12, 18))])
    assert (f.issue, f.rule_id) == (ScheduleIssue.OUTSIDE_SHIFT_CALENDAR, "WS-SC-003")
    assert f.uncovered == [(dt(2027, 1, 12, 15, 30), dt(2027, 1, 12, 18))]


def test_work_spanning_consecutive_shifts_is_covered():
    assert _check([_wp("WP-1", start=dt(2027, 1, 12, 14), end=dt(2027, 1, 12, 18))], cal=_cal(PATTERN)) == []


def test_unscheduled_package_is_not_judged_against_the_calendar():
    assert _check([_wp("WP-1", start=None, end=None)]) == []


# --- WS-SC-004 crew double-booked ---------------------------------------


def test_same_crew_on_overlapping_packages_is_double_booked():
    pkgs = [_wp("WP-2", crew_id="CR-PIPE-1"),
            _wp("WP-1", start=dt(2027, 1, 12, 10), end=dt(2027, 1, 12, 15, 30), crew_id="CR-PIPE-1")]
    [f] = _check(pkgs)
    assert (f.issue, f.rule_id, f.work_package_ids) == (ScheduleIssue.CREW_DOUBLE_BOOKED, "WS-SC-004", ["WP-1", "WP-2"])


def test_back_to_back_packages_for_one_crew_are_not_double_booked():
    pkgs = [_wp("WP-1", end=dt(2027, 1, 12, 11), crew_id="CR-PIPE-1"),
            _wp("WP-2", start=dt(2027, 1, 12, 11), crew_id="CR-PIPE-1")]
    assert _check(pkgs) == []


def test_different_crews_overlapping_is_fine():
    assert _check([_wp("WP-1", crew_id="CR-PIPE-1"), _wp("WP-2", crew_id="CR-BLAST-K")]) == []


# --- catalogue, determinism, purity -------------------------------------


@pytest.mark.parametrize("rid", ["WS-SC-001", "WS-SC-002", "WS-SC-003", "WS-SC-004"])
def test_schedule_rules_exist(rid):
    r = get_rule(rid)
    assert r.category == RuleCategory.SCHEDULE and r.contact_role.strip()


def test_duplicate_crew_ids_raise():
    with pytest.raises(ValueError, match="duplicate"):
        _check([_wp("WP-1")], crews=[ORGANIC, ORGANIC])


def test_duplicate_package_ids_raise():
    with pytest.raises(ValueError, match="duplicate"):
        _check([_wp("WP-1"), _wp("WP-1")])


def test_findings_are_sorted_and_order_independent():
    pkgs = [_wp("WP-B", crew_id="CR-GHOST"), _wp("WP-A", start=dt(2027, 1, 12, 14), end=dt(2027, 1, 12, 18))]
    fwd = [(f.rule_id, f.work_package_ids) for f in _check(pkgs)]
    assert fwd == [(f.rule_id, f.work_package_ids) for f in _check(list(reversed(pkgs)))]
    assert fwd == [("WS-SC-001", ["WP-B"]), ("WS-SC-003", ["WP-A"])]


def test_checks_never_mutate_packages():
    pkgs = [_wp("WP-1", crew_id="CR-GHOST")]
    before = [p.model_dump() for p in pkgs]
    _check(pkgs)
    assert [p.model_dump() for p in pkgs] == before
