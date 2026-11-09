"""Session 7: shift-aware fix suggester -- moves a whole crew to the next open shift,
re-checked against every rule, never auto-applied.

All data here is notional -- no real ship, yard, or personnel data.
"""

from datetime import date, datetime as dt, time, timedelta

import pytest

from agent_core.certificates import Certificate, CertificateKind as K
from agent_core.crews import Crew, ShiftCalendar, Window
from agent_core.shift_suggester import suggest_crew_shift
from notional_permits import permits_on_file
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
    kw.setdefault("certificates", permits_on_file(pkgs))  # review-05: hazards imply permits
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
    out = run(block + [tank_entry()], certificates=[permit] + permits_on_file([tank_entry()]), max_shifts=2)
    assert out.suggestion is None
    # review-02 S07-05: prove both candidates were assessed before checking why.
    assert [r.shift_id for r in out.rejected] == ["20270112-SWING", "20270113-MID"]
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
    assert [r.shift_id for r in out.rejected] == ["20270112-SWING", "20270113-MID", "20270113-DAY"]
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


# ===== review-02 (Codex, Session 7) =====

from agent_core.crews import Shift  # noqa: E402


def test_s07_01_crew_member_with_no_end_blocks_the_suggestion():
    pkgs = [wp("WELD-1", [H.HOT_WORK], day(7), day(8)),
            wp("PARTIAL", [], day(14), None, locked=True, lock_reason="notional fixed ongoing assignment")]
    out = run(pkgs, max_shifts=1)
    assert out.suggestion is None and out.rejected == []
    assert "PARTIAL" in out.reason and "incomplete schedule" in out.reason


def test_s07_01_unscheduled_crew_member_blocks_the_suggestion():
    pkgs = [wp("WELD-1", [H.HOT_WORK], day(7), day(8)), wp("FLOAT", [], None, None)]
    out = run(pkgs)
    assert out.suggestion is None and "FLOAT" in out.reason


def test_s07_01_other_crews_incomplete_schedules_do_not_block():
    pkgs = [wp("WELD-1", [H.HOT_WORK], day(7), day(8)), wp("TANK-X", [], None, None, crew="CR-TANK", comp="TANK-9")]
    assert run(pkgs).suggestion is not None


def test_s07_02_candidate_where_the_block_starts_outside_that_shift_is_rejected():
    cal = ShiftCalendar(shifts=[Shift(shift_id="LONG", name="LONG", start=day(7), end=day(15)),
                                Shift(shift_id="SHORT", name="SHORT", start=day(15), end=day(16)),
                                Shift(shift_id="FOLLOWING", name="FOLLOWING", start=day(16), end=day(23))])
    out = run([wp("JOB", [], day(14), day(14, 30))], target="JOB", calendar=cal, max_shifts=1)
    assert out.suggestion is None
    [r] = out.rejected
    assert r.shift_id == "SHORT" and r.rule_ids == [] and any("does not start" in x for x in r.reasons)


def test_s07_02_every_suggested_move_starts_inside_the_named_shift():
    s = run(weld_block() + [tank_entry()]).suggestion
    shift = next(x for x in CAL.shifts if x.shift_id == s.to_shift_id)
    assert all(shift.start <= m.suggested_start < shift.end for m in s.moves)


def test_s07_03_unlocated_overhead_work_gets_no_suggestion():
    aloft = wp("ALOFT", [H.WORKING_ALOFT], day(7), day(8), comp=None)
    aloft = aloft.model_copy(update={"spatial": SC(is_aloft=True)})
    other = wp("OTHER", [], day(15, 30), day(17), crew="CR-TANK")
    out = run([aloft, other], target="ALOFT", max_shifts=2)
    assert out.suggestion is None
    assert len(out.rejected) == 2 and all(any("overhead" in x for x in r.reasons) for r in out.rejected)


def test_s07_03_aloft_hazard_without_flag_or_frames_is_also_unverifiable():
    p = wp("ALOFT", [H.WORKING_ALOFT], day(7), day(8))
    out = run([p], target="ALOFT", max_shifts=1)
    assert out.suggestion is None and any("overhead" in x for x in out.rejected[0].reasons)


def test_s07_03_overhead_with_frames_next_to_a_concurrent_frameless_package_is_unverifiable():
    aloft = W(work_package_id="ALOFT", description="n", hazard_categories=[H.WORKING_ALOFT],
              spatial=SC(frame_start=40, frame_end=44, is_aloft=True),
              scheduled_start=day(7), scheduled_end=day(8), crew_id="CR-WELD")
    below = wp("BELOW", [], day(15, 30), day(17), crew="CR-TANK", comp="TANK-9")
    out = run([aloft, below], target="ALOFT", max_shifts=1)
    assert out.suggestion is None and any("overhead" in x for x in out.rejected[0].reasons)


def test_s07_03_overhead_with_frames_on_both_sides_and_no_overlap_passes():
    aloft = W(work_package_id="ALOFT", description="n", hazard_categories=[H.WORKING_ALOFT],
              spatial=SC(frame_start=40, frame_end=44, is_aloft=True),
              scheduled_start=day(7), scheduled_end=day(8), crew_id="CR-WELD")
    below = W(work_package_id="BELOW", description="n", spatial=SC(frame_start=90, frame_end=95),
              scheduled_start=day(15, 30), scheduled_end=day(17), crew_id="CR-TANK")
    assert run([aloft, below], target="ALOFT").suggestion is not None


@pytest.mark.parametrize("bad", [0, -1])
def test_s07_04_non_positive_max_shifts_raises(bad):
    with pytest.raises(ValueError, match="max_shifts"):
        run(weld_block(), max_shifts=bad)


def test_s07_03_moving_under_a_fixed_unlocated_overhead_job_is_unverifiable():
    # Builder-found while fixing S07-03: neither package has frames and the overhead one is fixed.
    mover = wp("WELD-1", [], day(7), day(8), comp=None)
    fixed_aloft = W(work_package_id="ALOFT-FIXED", description="n", hazard_categories=[H.WORKING_ALOFT],
                    spatial=SC(is_aloft=True), scheduled_start=day(15, 30), scheduled_end=day(17), crew_id="CR-TANK")
    out = run([mover, fixed_aloft], max_shifts=1)
    assert out.suggestion is None and any("ALOFT-FIXED" in x for x in out.rejected[0].reasons)


# ===== review-02 re-check: S07-03 reopened =====


def _framed(pid, hz, crew, start, end, aloft=False):
    return W(work_package_id=pid, description="n", hazard_categories=hz,
             spatial=SC(frame_start=40, frame_end=44, is_aloft=aloft), scheduled_start=start, scheduled_end=end, crew_id=crew)


@pytest.mark.parametrize("hz", [H.WORKING_ALOFT, H.OVER_THE_SIDE])
def test_recheck_s07_03_hazard_labelled_overhead_over_framed_work_is_rejected(hz):
    a = _framed("ALOFT", [hz], "CR-WELD", day(7), day(8))
    b = _framed("BELOW", [], "CR-TANK", day(15, 30), day(17))
    out = run([a, b], target="ALOFT", max_shifts=1)
    assert out.suggestion is None
    assert any("ALOFT is overhead work over BELOW" in x for x in out.rejected[0].reasons)


def test_recheck_s07_03_moving_under_a_fixed_hazard_labelled_overhead_job_is_rejected():
    mover = _framed("MOVER", [], "CR-WELD", day(7), day(8))
    fixed = _framed("ALOFT-FIXED", [H.WORKING_ALOFT], "CR-TANK", day(15, 30), day(17))
    out = run([mover, fixed], target="MOVER", max_shifts=1)
    assert out.suggestion is None
    assert any("ALOFT-FIXED is overhead work over MOVER" in x for x in out.rejected[0].reasons)


def test_recheck_s07_03_labelled_overhead_with_non_overlapping_frames_passes():
    a = _framed("ALOFT", [H.WORKING_ALOFT], "CR-WELD", day(7), day(8))
    b = W(work_package_id="BELOW", description="n", spatial=SC(frame_start=90, frame_end=95),
          scheduled_start=day(15, 30), scheduled_end=day(17), crew_id="CR-TANK")
    assert run([a, b], target="ALOFT").suggestion is not None


def test_recheck_s07_03_flagged_overhead_still_reports_the_catalogue_rule():
    a = _framed("ALOFT", [H.WORKING_ALOFT], "CR-WELD", day(7), day(8), aloft=True)
    b = _framed("BELOW", [], "CR-TANK", day(15, 30), day(17))
    out = run([a, b], target="ALOFT", max_shifts=1)
    assert "WS-OH-001" in out.rejected[0].rule_ids
