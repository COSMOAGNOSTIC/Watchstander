from datetime import datetime, timedelta

from agent_core.deconfliction import (
    MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH,
    check_conflict,
    deconfliction_node,
    find_all_conflicts,
)
from agent_core.state import HazardCategory, SpatialCoordinates, WorkPackageState


def make_wp(**overrides) -> WorkPackageState:
    defaults = dict(
        work_package_id="WP-001",
        description="test package",
    )
    defaults.update(overrides)
    return WorkPackageState(**defaults)


def test_no_conflict_when_spatially_isolated():
    a = make_wp(
        work_package_id="WP-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=10, frame_end=15),
    )
    b = make_wp(
        work_package_id="WP-B",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=90, frame_end=95),
    )
    assert check_conflict(a, b) is None


def test_hot_work_confined_space_overlap_flagged():
    """
    Mirrors the First Marine LLC / Calvert City pattern: hot work
    performed in or adjacent to a confined space that hasn't been
    cleared, in overlapping frames.
    """
    a = make_wp(
        work_package_id="WP-HOTWORK",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=40, frame_end=48, compartment_id="FR-44-TANK"),
    )
    b = make_wp(
        work_package_id="WP-CONFINED",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=42, frame_end=50, compartment_id="FR-44-TANK"),
    )
    rationale = check_conflict(a, b)
    assert rationale is not None
    assert "hot_work" in rationale and "confined_space" in rationale


def test_aloft_over_underlying_work_flagged():
    """
    Mirrors the 'hard hat / struck-by' pattern from the Detyens case:
    overhead work and work below it sharing a frame range with no
    confirmed vertical deconfliction.
    """
    aloft = make_wp(
        work_package_id="WP-ALOFT",
        spatial=SpatialCoordinates(frame_start=60, frame_end=70, is_aloft=True),
    )
    below = make_wp(
        work_package_id="WP-BELOW",
        spatial=SpatialCoordinates(frame_start=62, frame_end=65, is_aloft=False),
    )
    rationale = check_conflict(aloft, below)
    assert rationale is not None
    assert "Overhead work" in rationale


def test_find_all_conflicts_populates_both_sides():
    a = make_wp(
        work_package_id="WP-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="X"),
    )
    b = make_wp(
        work_package_id="WP-B",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="X"),
    )
    find_all_conflicts([a, b])
    assert "WP-B" in a.conflicts
    assert "WP-A" in b.conflicts
    assert a.conflict_rationale is not None


def test_overhead_underlying_labeled_correctly_regardless_of_pair_order():
    """
    An independent code review found the rationale text unconditionally
    named the *first* argument to check_conflict() as "Overhead work",
    regardless of which package actually carries is_aloft/is_over_side --
    wrong whenever the non-overhead package happened to be first (e.g. due
    to iteration order in find_all_conflicts). Regression test: the label
    must track the actual overhead party, not argument position.
    """
    aloft = make_wp(
        work_package_id="WP-ALOFT",
        spatial=SpatialCoordinates(frame_start=60, frame_end=70, is_aloft=True),
    )
    below = make_wp(
        work_package_id="WP-BELOW",
        spatial=SpatialCoordinates(frame_start=62, frame_end=65, is_aloft=False),
    )

    # Aloft package passed second this time -- the bug this regresses would
    # have called WP-BELOW "Overhead work" here.
    rationale = check_conflict(below, aloft)
    assert rationale is not None
    assert "Overhead work (WP-ALOFT)" in rationale
    assert "underlying work (WP-BELOW)" in rationale


def test_conflict_rationale_accumulates_across_multiple_conflicts_not_overwritten():
    """
    An independent code review found `find_all_conflicts` overwrote
    `conflict_rationale` on every matching pair, so a package conflicting
    with two others only kept the *last* pair's explanation even though
    `.conflicts` itself stayed complete. Regression test: a package
    conflicting with two others must retain both rationales.
    """
    a = make_wp(
        work_package_id="WP-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=700, frame_end=710, compartment_id="C1"),
    )
    b = make_wp(
        work_package_id="WP-B",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=702, frame_end=706, compartment_id="C1"),
    )
    c = make_wp(
        work_package_id="WP-C",
        hazard_categories=[HazardCategory.WORKING_ALOFT],
        spatial=SpatialCoordinates(frame_start=703, frame_end=705, is_aloft=True),
    )

    find_all_conflicts([a, b, c])

    assert set(a.conflicts) == {"WP-B", "WP-C"}
    assert "WP-B" in a.conflict_rationale
    assert "WP-C" in a.conflict_rationale


def test_find_all_conflicts_is_idempotent_on_repeated_invocation():
    """
    An independent code review found re-running find_all_conflicts on the
    same objects (a retry, a checkpoint replay) appended duplicate entries
    to `.conflicts` and duplicate text to `.conflict_rationale`, with no
    idempotency guard. Regression test: calling it twice must produce the
    same result as calling it once.
    """
    a = make_wp(
        work_package_id="WP-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="X"),
    )
    b = make_wp(
        work_package_id="WP-B",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="X"),
    )

    find_all_conflicts([a, b])
    first_rationale = a.conflict_rationale
    find_all_conflicts([a, b])

    assert a.conflicts == ["WP-B"]
    assert b.conflicts == ["WP-A"]
    assert a.conflict_rationale == first_rationale


def test_deconfliction_node_fails_closed_immediately_on_flagging_a_conflict():
    """
    An independent code review found `cleared_for_execution` stayed True
    (its default) on a freshly flagged package all the way until
    hitl_gate_node ran -- a window where any consumer reading state
    between this node and the gate, or a graph that crashes/terminates in
    that window, would see an un-reviewed flagged conflict as cleared.
    Regression test: deconfliction_node must flip cleared_for_execution to
    False the moment it flags a conflict, before the HITL gate ever runs.
    """
    a = {
        "work_package_id": "WP-A",
        "description": "x",
        "hazard_categories": [HazardCategory.HOT_WORK],
        "spatial": SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="X"),
    }
    b = {
        "work_package_id": "WP-B",
        "description": "x",
        "hazard_categories": [HazardCategory.CONFINED_SPACE],
        "spatial": SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="X"),
    }

    result = deconfliction_node({"work_packages": [a, b]})

    for wp in result["work_packages"]:
        assert wp.requires_hitl_review is True
        assert wp.cleared_for_execution is False


def test_no_conflict_when_spatially_linked_but_scheduled_weeks_apart():
    """
    ARCHITECTURE.md Known Debt: README and this module's own docstring
    claimed spatial *and* temporal deconfliction, but `check_conflict()`
    never read `scheduled_start`/`scheduled_end` -- two packages
    scheduled weeks apart in the same compartment were still flagged.
    Regression test for the fix: spatially/hazard-linked packages with
    non-overlapping schedules must not be flagged.
    """
    week1_start = datetime(2026, 8, 3, 7, 0)
    week1_end = datetime(2026, 8, 3, 15, 0)
    week3_start = datetime(2026, 8, 17, 7, 0)
    week3_end = datetime(2026, 8, 17, 15, 0)

    a = make_wp(
        work_package_id="WP-HOTWORK",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=40, frame_end=48, compartment_id="FR-44-TANK"),
        scheduled_start=week1_start,
        scheduled_end=week1_end,
    )
    b = make_wp(
        work_package_id="WP-CONFINED",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=42, frame_end=50, compartment_id="FR-44-TANK"),
        scheduled_start=week3_start,
        scheduled_end=week3_end,
    )
    assert check_conflict(a, b) is None


def test_conflict_still_flagged_when_schedules_actually_overlap():
    same_day_am = datetime(2026, 8, 3, 7, 0)
    same_day_noon = datetime(2026, 8, 3, 12, 0)
    same_day_pm = datetime(2026, 8, 3, 15, 0)

    a = make_wp(
        work_package_id="WP-HOTWORK",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=40, frame_end=48, compartment_id="FR-44-TANK"),
        scheduled_start=same_day_am,
        scheduled_end=same_day_noon,
    )
    b = make_wp(
        work_package_id="WP-CONFINED",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=42, frame_end=50, compartment_id="FR-44-TANK"),
        scheduled_start=same_day_noon,
        scheduled_end=same_day_pm,
    )
    rationale = check_conflict(a, b)
    assert rationale is not None
    assert "hot_work" in rationale and "confined_space" in rationale


def _hot_work_group(count: int, fire_watch_id: str, start, end) -> list[WorkPackageState]:
    """
    Builds `count` spatially-unrelated hot-work packages sharing one
    fire watch and one overlapping schedule window -- the minimal shape
    needed to exercise `_fire_watch_capacity_conflicts` without a
    spatial/hazard-pair conflict also being in play. Frame ranges are
    spread far apart (1000 frames per package) specifically so no pair
    is spatially linked -- this is meant to isolate the N-way capacity
    check, not the pairwise geometry check.
    """
    return [
        make_wp(
            work_package_id=f"WP-HOT-{i}",
            hazard_categories=[HazardCategory.HOT_WORK],
            spatial=SpatialCoordinates(frame_start=i * 1000, frame_end=i * 1000 + 5),
            fire_watch_id=fire_watch_id,
            scheduled_start=start,
            scheduled_end=end,
        )
        for i in range(count)
    ]


def test_fire_watch_capacity_flagged_when_exceeded():
    """
    NAVSEA8010-4.4.3, verified against primary source 2026-08-08: "No
    more than four hot workers shall be attended by a single fire
    watch." Five spatially-unrelated hot-work packages sharing one fire
    watch and an overlapping schedule must be flagged -- this is a
    capacity constraint, not a geometry one -- while four must not be
    (see test_fire_watch_capacity_not_flagged_at_exactly_the_limit).
    """
    assert MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH == 4

    same_day_am = datetime(2026, 8, 3, 7, 0)
    same_day_pm = datetime(2026, 8, 3, 15, 0)

    group = _hot_work_group(5, "FW-1", same_day_am, same_day_pm)
    find_all_conflicts(group)

    a = group[0]
    assert len(a.conflicts) == 4
    assert "NAVSEA8010-4.4.3" in a.conflict_rationale
    assert "No more than four hot workers" in a.conflict_rationale


def test_fire_watch_capacity_not_flagged_at_exactly_the_limit():
    """
    Regression guard for an off-by-one: exactly four hot workers on one
    fire watch is within NAVSEA8010-4.4.3's stated limit, not over it --
    `_fire_watch_capacity_conflicts` must use `<=`, not `<`, when
    deciding a group is within bounds.
    """
    same_day_am = datetime(2026, 8, 3, 7, 0)
    same_day_pm = datetime(2026, 8, 3, 15, 0)

    group = _hot_work_group(4, "FW-1", same_day_am, same_day_pm)
    find_all_conflicts(group)

    for wp in group:
        assert wp.conflicts == []


def test_fire_watch_capacity_not_flagged_when_schedules_dont_overlap():
    """
    Five packages assigned to one fire watch is over the limit of 4 by
    raw count, but if the five are spread across five mutually
    non-overlapping days, no two of them are ever concurrently active --
    the fire watch never actually covers more than one at a time.
    `_fire_watch_capacity_conflicts` must not flag any pair here.

    Deliberately gives every package its own disjoint day (not two
    packages sharing week1 and three sharing week3, or similar) --
    `_fire_watch_capacity_conflicts`'s current implementation gates on
    raw per-fire-watch package count before checking pairwise schedule
    overlap, so a subgroup of >=2 packages that *do* overlap each other
    within a >4-package total would still get flagged even though that
    subgroup alone never exceeds the limit. That's a real, separate gap
    (see ARCHITECTURE.md Known Debt) -- this test is scoped to the
    already-correct "genuinely never concurrent" case, not that one.
    """
    days = [datetime(2026, 8, 3 + 7 * i, 7, 0) for i in range(5)]
    packages = [
        make_wp(
            work_package_id=f"WP-HOT-{i}",
            hazard_categories=[HazardCategory.HOT_WORK],
            spatial=SpatialCoordinates(frame_start=i * 1000, frame_end=i * 1000 + 5),
            fire_watch_id="FW-1",
            scheduled_start=day,
            scheduled_end=day.replace(hour=15),
        )
        for i, day in enumerate(days)
    ]

    find_all_conflicts(packages)
    for wp in packages:
        assert wp.conflicts == []


def test_fire_watch_capacity_not_flagged_without_shared_fire_watch_id():
    a = make_wp(
        work_package_id="WP-HOT-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5),
    )
    b = make_wp(
        work_package_id="WP-HOT-B",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=900, frame_end=905),
    )
    find_all_conflicts([a, b])
    assert a.conflicts == []
    assert b.conflicts == []


def test_fire_watch_capacity_conflicts_are_idempotent_on_repeated_invocation():
    same_day_am = datetime(2026, 8, 3, 7, 0)
    same_day_pm = datetime(2026, 8, 3, 15, 0)
    group = _hot_work_group(5, "FW-1", same_day_am, same_day_pm)
    find_all_conflicts(group)
    a = group[0]
    first_conflicts = list(a.conflicts)
    first_rationale = a.conflict_rationale
    find_all_conflicts(group)
    assert a.conflicts == first_conflicts
    assert a.conflict_rationale == first_rationale


def test_fire_watch_capacity_flagged_by_worker_count_not_package_count():
    """
    AUD-01 (AOSE Round 5, Grok), unit half of the finding. Two packages,
    three hot workers each, sharing a fire watch and an overlapping
    schedule: raw package count is 2 (under the limit of 4), but the
    fire watch is actually covering 6 concurrent hot workers -- over the
    limit. Before the fix, `_fire_watch_capacity_conflicts` compared
    `len(group)` and never flagged this at all.
    """
    same_day_am = datetime(2026, 8, 3, 7, 0)
    same_day_pm = datetime(2026, 8, 3, 15, 0)
    a = make_wp(
        work_package_id="WP-HOT-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5),
        fire_watch_id="FW-1",
        hot_worker_count=3,
        scheduled_start=same_day_am,
        scheduled_end=same_day_pm,
    )
    b = make_wp(
        work_package_id="WP-HOT-B",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=900, frame_end=905),
        fire_watch_id="FW-1",
        hot_worker_count=3,
        scheduled_start=same_day_am,
        scheduled_end=same_day_pm,
    )
    find_all_conflicts([a, b])
    assert a.conflicts == ["WP-HOT-B"]
    assert "6 concurrent hot workers" in a.conflict_rationale


def test_fire_watch_capacity_not_flagged_for_subgroup_that_never_peaks_over_limit():
    """
    AUD-01, shape half of the finding -- the exact gap named in
    `test_fire_watch_capacity_not_flagged_when_schedules_dont_overlap`'s
    own docstring before this fix existed. Six single-worker packages
    share one fire watch: three overlap each other in the morning, three
    separate ones overlap each other in the afternoon, and the two
    trios never overlap each other. Raw group count is 6 (over the old
    package-count limit), but peak concurrent coverage is only 3 at any
    single instant -- under the limit of 4. Must not be flagged.
    """
    morning_start = datetime(2026, 8, 3, 7, 0)
    morning_end = datetime(2026, 8, 3, 11, 0)
    afternoon_start = datetime(2026, 8, 3, 12, 0)
    afternoon_end = datetime(2026, 8, 3, 16, 0)

    morning = _hot_work_group(3, "FW-1", morning_start, morning_end)
    afternoon = _hot_work_group(3, "FW-1", afternoon_start, afternoon_end)
    for i, wp in enumerate(afternoon):
        wp.work_package_id = f"WP-HOT-PM-{i}"
        wp.spatial.frame_start += 100_000
        wp.spatial.frame_end += 100_000

    group = morning + afternoon
    find_all_conflicts(group)
    for wp in group:
        assert wp.conflicts == []


def test_fire_watch_capacity_touching_endpoints_count_as_overlapping():
    """
    Closed-interval convention consistency with AUD-04
    (`_schedule_is_ordered`, state.py): a package ending exactly when
    another starts must still count as concurrent at that instant, same
    as `_schedules_overlap`'s `a_start <= b_end and b_start <= a_end`.
    Four 1-worker packages ending/starting back-to-back at the same
    instant plus one more overlapping all of them at that instant must
    read as 5 concurrent workers at that boundary point, over the limit.
    """
    t0 = datetime(2026, 8, 3, 7, 0)
    t1 = datetime(2026, 8, 3, 9, 0)
    t2 = datetime(2026, 8, 3, 11, 0)

    early = [
        make_wp(
            work_package_id=f"WP-EARLY-{i}",
            hazard_categories=[HazardCategory.HOT_WORK],
            spatial=SpatialCoordinates(frame_start=i * 1000, frame_end=i * 1000 + 5),
            fire_watch_id="FW-1",
            scheduled_start=t0,
            scheduled_end=t1,
        )
        for i in range(4)
    ]
    late = make_wp(
        work_package_id="WP-LATE",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=9000, frame_end=9005),
        fire_watch_id="FW-1",
        scheduled_start=t1,
        scheduled_end=t2,
    )
    group = early + [late]
    find_all_conflicts(group)
    assert late.conflicts != []
    assert "5 concurrent hot workers" in late.conflict_rationale


def test_fire_watch_capacity_unscheduled_package_contributes_a_baseline():
    """
    A package missing `scheduled_start`/`scheduled_end` can't be placed
    on the sweep-line, but the rest of this module treats missing
    schedule data as unknown, not "no overlap" (`_schedules_overlap`
    returns True) -- the same posture applies here: its
    `hot_worker_count` is added as a constant baseline present at every
    point on the line, not silently dropped. Three single-worker
    scheduled packages (under the limit alone) plus one unscheduled
    2-worker package pushes the peak to 5, over the limit.
    """
    same_day_am = datetime(2026, 8, 3, 7, 0)
    same_day_pm = datetime(2026, 8, 3, 15, 0)
    scheduled = _hot_work_group(3, "FW-1", same_day_am, same_day_pm)
    unscheduled = make_wp(
        work_package_id="WP-HOT-UNSCHEDULED",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=9000, frame_end=9005),
        fire_watch_id="FW-1",
        hot_worker_count=2,
        # no scheduled_start/scheduled_end set
    )
    group = scheduled + [unscheduled]
    find_all_conflicts(group)
    assert unscheduled.conflicts != []
    assert "5 concurrent hot workers" in unscheduled.conflict_rationale


def test_conflict_still_flagged_when_schedule_data_is_missing():
    """
    Missing schedule data must default to "temporally linked" (unknown
    treated as overlapping) -- the same over-flagging-is-safe posture as
    the rest of the module -- not silently clear a package that just
    hasn't had its schedule filled in yet.
    """
    a = make_wp(
        work_package_id="WP-HOTWORK",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=40, frame_end=48, compartment_id="FR-44-TANK"),
        # no scheduled_start/scheduled_end set
    )
    b = make_wp(
        work_package_id="WP-CONFINED",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=42, frame_end=50, compartment_id="FR-44-TANK"),
        scheduled_start=datetime(2026, 8, 3, 7, 0),
        scheduled_end=datetime(2026, 8, 3, 15, 0),
    )
    rationale = check_conflict(a, b)
    assert rationale is not None
