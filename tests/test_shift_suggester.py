"""Session 7: shift-aware fix suggester -- moves a whole crew to the next open shift,
re-checked against every rule, never auto-applied.

All data here is notional -- no real ship, yard, or personnel data.
"""

from datetime import date, datetime as dt, time, timedelta

import pytest

from agent_core.certificates import Certificate, CertificateKind as K
from agent_core.crews import Crew, ShiftCalendar, Window
from agent_core.shift_suggester import suggest_crew_shift
from agent_core.state import HazardCategory as H, SafetyPermitsRequired, SpatialCoordinates as SC, WorkPackageState as W

PATTERN = [("DAY", time(7), time(15, 30)), ("SWING", time(15, 30), time(0)), ("MID", time(0), time(7))]
CAL = ShiftCalendar.from_daily_pattern(date(2027, 1, 12), 3, PATTERN)
CREWS = [Crew(crew_id="CR-WELD", name="Notional weld crew"), Crew(crew_id="CR-TANK", name="Notional tank crew")]


def wp(pid, hz, start, end, crew="CR-WELD", comp="TANK-4", **kw):
    return W(work_package_id=pid, description=f"notional {pid}", hazard_categories=list(hz),
             spatial=SC(compartment_id=comp), scheduled_start=start, scheduled_end=end, crew_id=crew, **kw)


def day(h, m=0, d=12):
    return dt(2027, 1, d, h, m)


def weld_block():
    return [wp("WELD-1", [H.HOT_WORK], day(7), day(11)), wp("WELD-2", [H.HOT_WORK], day(12), day(15))]


def tank_entry(start=day(7), end=day(15), pid="TANK-ENTRY"):
    return wp(pid, [H.CONFINED_SPACE], start, end, crew="CR-TANK")


def run(pkgs, target="WELD-1", **kw):
    kw.setdefault("crews", CREWS)
    kw.setdefault("calendar", CAL)
    kw.setdefault("certificates", [])
    return suggest_crew_shift(pkgs, target, **kw)


# --- the core move -------------------------------------------------------


def test_moves_the_whole_crew_block_to_the_next_open_shift():
    out = run(weld_block() + [tank_entry()])
    s = out.suggestion
    assert s is not None
    assert (s.crew_id, s.from_shift_id, s.to_shift_id) == ("CR-WELD", "20270112-DAY", "20270112-SWING")
    assert [m.work_package_id for m in s.moves] == ["WELD-1", "WELD-2"]
    assert s.offset == timedelta(hours=8, minutes=30)
    w1, w2 = s.moves
    assert (w1.suggested_start, w1.suggested_end) == (day(15, 30), day(19, 30))
    assert (w2.suggested_start, w2.suggested_end) == (day(20, 30), day(23, 30))


def test_block_is_only_the_crews_packages_starting_in_that_shift():
    later = wp("WELD-3", [H.HOT_WORK], day(8, d=13), day(10, d=13), comp="TANK-9")
    other_crew = tank_entry()
    s = run(weld_block() + [later, other_crew]).suggestion
    assert [m.work_package_id for m in s.moves] == ["WELD-1", "WELD-2"]


def test_never_moves_earlier():
    s = run(weld_block() + [tank_entry()]).suggestion
    assert all(m.suggested_start > m.original_start for m in s.moves)


def test_no_conflict_means_nothing_to_fix_is_still_a_valid_query():
    # The suggester answers "where could this block go next"; it doesn't require a conflict.
    s = run(weld_block()).suggestion
    assert s is not None and s.to_shift_id == "20270112-SWING"


# --- every rule is re-checked; rejections are recorded ------------------


def test_skips_a_shift_where_the_block_would_hit_another_conflict():
    swing_entry = tank_entry(day(15, 30), day(23, 59), pid="TANK-SWING")
    out = run(weld_block() + [tank_entry(), swing_entry])
    assert out.suggestion.to_shift_id == "20270113-MID"
    [rej] = out.rejected
    assert rej.shift_id == "20270112-SWING" and "WS-HZ-001" in rej.rule_ids


def test_fire_watch_overload_in_the_new_shift_rejects_it():
    block = [wp("WELD-1", [H.HOT_WORK], day(7), day(11), fire_watch_id="FW-1", hot_worker_count=2)]
    swing_hot = wp("HOT-SWING", [H.HOT_WORK], day(15, 30), day(20), crew="CR-TANK", comp="TANK-9",
                   fire_watch_id="FW-1", hot_worker_count=3)
    out = run(block + [tank_entry(), swing_hot])
    assert "WS-FW-001" in out.rejected[0].rule_ids
    assert out.suggestion.to_shift_id == "20270113-MID"


def test_certificate_that_does_not_cover_the_new_shift_rejects_it():
    block = [wp("WELD-1", [H.HOT_WORK], day(7), day(11), permits_required=SafetyPermitsRequired(hot_work_permit=True))]
    permit = Certificate(certificate_id="HW-1", work_package_id="WELD-1", kind=K.HOT_WORK_PERMIT,
                         valid_from=day(6), valid_until=day(15, 30))
    out = run(block + [tank_entry()], certificates=[permit], max_shifts=2)
    assert out.suggestion is None
    assert all("WS-CT-001" in r.rule_ids for r in out.rejected)


def test_contractor_window_rejects_shifts_outside_it():
    k = Crew(crew_id="CR-K", name="Notional blast contractor", is_contractor=True,
             contractor_windows=[Window(start=day(7), end=day(15, 30)), Window(start=day(7, d=13), end=day(15, 30, d=13))])
    block = [wp("BLAST-1", [H.HOT_WORK], day(7), day(11), crew="CR-K")]
    out = run(block + [tank_entry()], target="BLAST-1", crews=CREWS + [k])
    assert out.suggestion.to_shift_id == "20270113-DAY"
    assert [r.shift_id for r in out.rejected] == ["20270112-SWING", "20270113-MID"]
    assert all("WS-SC-002" in r.rule_ids for r in out.rejected)


def test_crew_double_booking_in_the_new_shift_rejects_it():
    busy = wp("WELD-SWING", [], day(16), day(20), comp="TANK-9")
    out = run(weld_block() + [tank_entry(), busy])
    assert "WS-SC-004" in out.rejected[0].rule_ids


def test_judgment_flag_on_a_moved_package_rejects_every_shift():
    # An unlocated hot-work package can't be spatially checked anywhere, so no move is verifiable.
    block = [wp("WELD-1", [H.HOT_WORK], day(7), day(11), comp=None)]
    out = run(block, max_shifts=3)
    assert out.suggestion is None
    assert all("WS-JF-003" in r.rule_ids for r in out.rejected)


# --- refusals -------------------------------------------------------------


def test_locked_package_in_the_block_means_no_suggestion():
    block = [wp("WELD-1", [H.HOT_WORK], day(7), day(11)),
             wp("WELD-2", [H.HOT_WORK], day(12), day(15), locked=True, lock_reason="notional crane lift slot")]
    out = run(block + [tank_entry()])
    assert out.suggestion is None and out.rejected == []
    assert "WELD-2" in out.reason and "locked" in out.reason


def test_target_without_a_crew_means_no_suggestion():
    p = wp("WELD-1", [H.HOT_WORK], day(7), day(11), crew=None)
    out = run([p])
    assert out.suggestion is None and "crew" in out.reason


def test_unknown_crew_means_no_suggestion():
    out = run([wp("WELD-1", [H.HOT_WORK], day(7), day(11), crew="CR-GHOST")])
    assert out.suggestion is None and "CR-GHOST" in out.reason


def test_target_outside_the_calendar_means_no_suggestion():
    cal = ShiftCalendar.from_daily_pattern(date(2027, 1, 12), 2, [("DAY", time(7), time(15, 30))])
    out = run([wp("WELD-1", [H.HOT_WORK], day(18), day(20))], calendar=cal)
    assert out.suggestion is None and "shift" in out.reason


def test_unscheduled_target_means_no_suggestion():
    out = run([wp("WELD-1", [H.HOT_WORK], None, None)])
    assert out.suggestion is None and "schedule" in out.reason


def test_unknown_target_raises():
    with pytest.raises(ValueError, match="NOPE"):
        run(weld_block(), target="NOPE")


def test_duplicate_package_ids_raise():
    with pytest.raises(ValueError, match="duplicate"):
        run(weld_block() + [weld_block()[0]])


def test_search_is_bounded_and_reports_every_rejection():
    block = [wp("WELD-1", [H.HOT_WORK], day(7), day(11), comp=None)]
    out = run(block, max_shifts=2)
    assert out.suggestion is None and len(out.rejected) == 2


def test_runs_out_of_calendar_cleanly():
    out = run(weld_block() + [tank_entry()], calendar=ShiftCalendar.from_daily_pattern(date(2027, 1, 12), 1, [("DAY", time(7), time(15, 30))]))
    assert out.suggestion is None and out.rejected == [] and "no later shift" in out.reason


# --- never auto-applied, deterministic -----------------------------------


def test_never_mutates_inputs():
    pkgs = weld_block() + [tank_entry()]
    before = [p.model_dump() for p in pkgs]
    run(pkgs)
    assert [p.model_dump() for p in pkgs] == before


def test_suggestion_is_marked_not_applied_and_deterministic():
    s = run(weld_block() + [tank_entry()]).suggestion
    assert s.applied is False and s.source == "deterministic_shift_search"
    assert s.checks == ["conflicts", "fire_watch", "certificates", "schedule", "judgment"]


def test_input_order_does_not_change_the_answer():
    pkgs = weld_block() + [tank_entry()]
    assert run(pkgs).model_dump() == run(list(reversed(pkgs))).model_dump()


def test_touching_the_new_shift_start_counts_as_overlap():
    # Closed intervals (repo convention): an entry ending 15:30 overlaps a block moved to start 15:30.
    out = run(weld_block() + [tank_entry(end=day(15, 30))])
    assert out.rejected[0].shift_id == "20270112-SWING" and "WS-HZ-001" in out.rejected[0].rule_ids
