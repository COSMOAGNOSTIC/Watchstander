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


def test_fire_watch_capacity_flagged_when_exceeded():
    """
    NAVSEA8010-4.4.3: a single fire watch cannot supervise unlimited
    concurrent hot work. Two spatially-unrelated hot-work packages
    sharing the same fire_watch_id and overlapping schedule must still
    be flagged -- this is a capacity constraint, not a geometry one.
    """
    assert MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH == 1

    same_day_am = datetime(2026, 8, 3, 7, 0)
    same_day_pm = datetime(2026, 8, 3, 15, 0)

    a = make_wp(
        work_package_id="WP-HOT-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5),
        fire_watch_id="FW-1",
        scheduled_start=same_day_am,
        scheduled_end=same_day_pm,
    )
    b = make_wp(
        work_package_id="WP-HOT-B",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=900, frame_end=905),  # far away, no geometry link
        fire_watch_id="FW-1",
        scheduled_start=same_day_am,
        scheduled_end=same_day_pm,
    )

    find_all_conflicts([a, b])

    assert "WP-HOT-B" in a.conflicts
    assert "NAVSEA8010-4.4.3" in a.conflict_rationale


def test_fire_watch_capacity_not_flagged_when_schedules_dont_overlap():
    week1 = datetime(2026, 8, 3, 7, 0)
    week1_end = datetime(2026, 8, 3, 15, 0)
    week3 = datetime(2026, 8, 17, 7, 0)
    week3_end = datetime(2026, 8, 17, 15, 0)

    a = make_wp(
        work_package_id="WP-HOT-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        fire_watch_id="FW-1",
        scheduled_start=week1,
        scheduled_end=week1_end,
    )
    b = make_wp(
        work_package_id="WP-HOT-B",
        hazard_categories=[HazardCategory.HOT_WORK],
        fire_watch_id="FW-1",
        scheduled_start=week3,
        scheduled_end=week3_end,
    )

    find_all_conflicts([a, b])
    assert a.conflicts == []
    assert b.conflicts == []


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
    a = make_wp(
        work_package_id="WP-HOT-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        fire_watch_id="FW-1",
        scheduled_start=same_day_am,
        scheduled_end=same_day_pm,
    )
    b = make_wp(
        work_package_id="WP-HOT-B",
        hazard_categories=[HazardCategory.HOT_WORK],
        fire_watch_id="FW-1",
        scheduled_start=same_day_am,
        scheduled_end=same_day_pm,
    )
    find_all_conflicts([a, b])
    first_rationale = a.conflict_rationale
    find_all_conflicts([a, b])
    assert a.conflicts == ["WP-HOT-B"]
    assert a.conflict_rationale == first_rationale


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
