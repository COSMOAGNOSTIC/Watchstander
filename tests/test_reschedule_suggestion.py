from datetime import datetime, timedelta

import pytest

from agent_core.reschedule_suggestion import suggest_reschedule
from agent_core.state import HazardCategory, SpatialCoordinates, WorkPackageState


def make_wp(**overrides) -> WorkPackageState:
    defaults = dict(
        work_package_id="WP-001",
        description="test package",
    )
    defaults.update(overrides)
    return WorkPackageState(**defaults)


def test_suggests_smallest_conflict_free_shift():
    """
    WP-HOTWORK overlaps WP-CONFINED in schedule, frame range, and an
    incompatible hazard pair -- a real flagged conflict. Shifting
    WP-HOTWORK 3 hours later clears the schedule overlap entirely and
    should be the first thing found searching outward in 1-hour steps.
    """
    hotwork = make_wp(
        work_package_id="WP-HOTWORK",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=40, frame_end=48, compartment_id="FR-44-TANK"),
        scheduled_start=datetime(2026, 9, 1, 8, 0),
        scheduled_end=datetime(2026, 9, 1, 12, 0),
    )
    confined = make_wp(
        work_package_id="WP-CONFINED",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=40, frame_end=48, compartment_id="FR-44-TANK"),
        scheduled_start=datetime(2026, 9, 1, 8, 0),
        scheduled_end=datetime(2026, 9, 1, 12, 0),
    )

    suggestion = suggest_reschedule([hotwork, confined], "WP-HOTWORK", max_shift=timedelta(days=2))

    assert suggestion is not None
    assert suggestion.work_package_id == "WP-HOTWORK"
    assert suggestion.source == "deterministic_search"
    # confined runs 08:00-12:00; hotwork must clear that window entirely
    assert (
        suggestion.suggested_start >= confined.scheduled_end
        or suggestion.suggested_end <= confined.scheduled_start
    )
    # never mutates the inputs
    assert hotwork.scheduled_start == datetime(2026, 9, 1, 8, 0)


def test_nearest_offset_wins_over_a_further_one():
    """
    A trivially-clear slot exists 2 steps away in one direction; the
    search must return that one, not a further offset that would also
    work. (Not 1 step: closed-interval convention means a package shifted
    to exactly touch the other's boundary still counts as overlapping --
    see deconfliction.py's AUD-04 convention -- so the nearest genuinely
    clear offset here is +/-2 hours, not +/-1.)
    """
    a = make_wp(
        work_package_id="WP-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 9, 1, 10, 0),
        scheduled_end=datetime(2026, 9, 1, 11, 0),
    )
    b = make_wp(
        work_package_id="WP-B",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 9, 1, 10, 0),
        scheduled_end=datetime(2026, 9, 1, 11, 0),
    )

    suggestion = suggest_reschedule(
        [a, b], "WP-A", step=timedelta(hours=1), max_shift=timedelta(days=1)
    )

    assert suggestion is not None
    assert abs(suggestion.shift) == timedelta(hours=2)


def test_returns_none_when_no_conflict_free_slot_within_search_window():
    """
    B occupies every hour of a 30-day window in the same space/hazard
    pair as A; searching only 2 days out must fail to find anything.
    """
    a = make_wp(
        work_package_id="WP-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 9, 1, 8, 0),
        scheduled_end=datetime(2026, 9, 1, 9, 0),
    )
    b = make_wp(
        work_package_id="WP-B",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 8, 1, 0, 0),
        scheduled_end=datetime(2026, 10, 1, 0, 0),
    )

    suggestion = suggest_reschedule(
        [a, b], "WP-A", step=timedelta(hours=6), max_shift=timedelta(days=2)
    )

    assert suggestion is None


def test_returns_none_when_target_has_no_schedule_to_shift():
    a = make_wp(work_package_id="WP-A")  # no scheduled_start/end at all
    b = make_wp(work_package_id="WP-B")

    assert suggest_reschedule([a, b], "WP-A") is None


def test_raises_when_target_id_not_present():
    a = make_wp(work_package_id="WP-A")

    with pytest.raises(ValueError):
        suggest_reschedule([a], "WP-DOES-NOT-EXIST")


def test_unrelated_preexisting_fire_watch_violation_does_not_block_a_suggestion():
    """
    Regression for AUD-10 (AOSE Round 6, Fable cross-review): a pre-existing
    fire-watch capacity violation between two packages that have nothing to
    do with the search target must not veto an otherwise-clean offset for
    the target. Before the fix, _fire_watch_capacity_conflicts() was called
    against the whole trial group and any non-empty result -- regardless of
    which packages it actually named -- rejected the candidate outright.
    """
    a = make_wp(
        work_package_id="WP-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 9, 1, 10, 0),
        scheduled_end=datetime(2026, 9, 1, 11, 0),
    )
    b = make_wp(
        work_package_id="WP-B",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 9, 1, 10, 0),
        scheduled_end=datetime(2026, 9, 1, 11, 0),
    )
    # C and D: an unrelated, already-over-capacity fire watch weeks later.
    # 3 hot workers each on the same fire_watch_id, fully overlapping --
    # peaks at 6, over MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH (4) --
    # with zero spatial or temporal relationship to WP-A/WP-B.
    c = make_wp(
        work_package_id="WP-C",
        hazard_categories=[HazardCategory.HOT_WORK],
        fire_watch_id="FW-UNRELATED",
        hot_worker_count=3,
        spatial=SpatialCoordinates(frame_start=90, frame_end=95, compartment_id="FAR-AWAY"),
        scheduled_start=datetime(2026, 10, 1, 8, 0),
        scheduled_end=datetime(2026, 10, 1, 16, 0),
    )
    d = make_wp(
        work_package_id="WP-D",
        hazard_categories=[HazardCategory.HOT_WORK],
        fire_watch_id="FW-UNRELATED",
        hot_worker_count=3,
        spatial=SpatialCoordinates(frame_start=90, frame_end=95, compartment_id="FAR-AWAY"),
        scheduled_start=datetime(2026, 10, 1, 8, 0),
        scheduled_end=datetime(2026, 10, 1, 16, 0),
    )

    suggestion = suggest_reschedule(
        [a, b, c, d], "WP-A", step=timedelta(hours=1), max_shift=timedelta(days=1)
    )

    assert suggestion is not None, (
        "an unrelated fire-watch violation elsewhere in the yard must not "
        "block a clean suggestion for WP-A"
    )


def test_fire_watch_violation_actually_involving_the_target_still_blocks_it():
    """
    The other half of AUD-10: scoping the check to the candidate must not
    over-correct into ignoring a real fire-watch capacity problem the
    candidate itself would create or join.
    """
    a = make_wp(
        work_package_id="WP-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        fire_watch_id="FW-1",
        hot_worker_count=3,
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 9, 1, 10, 0),
        scheduled_end=datetime(2026, 9, 1, 11, 0),
    )
    # B forces the *original* schedule conflict via hazard pair, so the
    # search has to move off of 10:00-11:00 in the first place.
    b = make_wp(
        work_package_id="WP-B",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 9, 1, 10, 0),
        scheduled_end=datetime(2026, 9, 1, 11, 0),
    )
    # C shares WP-A's fire watch and overlaps every hour of the search
    # window with 2 more hot workers -- any offset for A joins a group
    # peaking at 5, over the limit of 4, for as long as C runs.
    c = make_wp(
        work_package_id="WP-C",
        hazard_categories=[HazardCategory.HOT_WORK],
        fire_watch_id="FW-1",
        hot_worker_count=2,
        spatial=SpatialCoordinates(frame_start=50, frame_end=55, compartment_id="ELSEWHERE"),
        scheduled_start=datetime(2026, 8, 25, 0, 0),
        scheduled_end=datetime(2026, 9, 10, 0, 0),
    )

    suggestion = suggest_reschedule(
        [a, b, c], "WP-A", step=timedelta(hours=1), max_shift=timedelta(days=1)
    )

    assert suggestion is None, (
        "every reachable offset joins WP-C's fire watch over capacity -- "
        "the search must not paper over a capacity violation it would "
        "itself create"
    )


def test_shift_never_reintroduces_a_conflict_with_a_third_package():
    """
    A conflicts with B at the original schedule. The nearest offset that
    clears B happens to land A on top of C -- a package that wasn't
    conflicting before. The search must reject that offset and keep
    looking rather than return a shift that trades one conflict for
    another.
    """
    a = make_wp(
        work_package_id="WP-A",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 9, 1, 10, 0),
        scheduled_end=datetime(2026, 9, 1, 11, 0),
    )
    b = make_wp(
        work_package_id="WP-B",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 9, 1, 10, 0),
        scheduled_end=datetime(2026, 9, 1, 11, 0),
    )
    # occupies the +1hr slot that would otherwise be the nearest fix
    c = make_wp(
        work_package_id="WP-C",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="Z"),
        scheduled_start=datetime(2026, 9, 1, 11, 0),
        scheduled_end=datetime(2026, 9, 1, 12, 0),
    )

    suggestion = suggest_reschedule(
        [a, b, c], "WP-A", step=timedelta(hours=1), max_shift=timedelta(days=1)
    )

    assert suggestion is not None
    assert suggestion.shift != timedelta(hours=1)
    # confirm whatever was returned really clears both other packages
    assert suggestion.suggested_start >= c.scheduled_end or suggestion.suggested_end <= datetime(
        2026, 9, 1, 10, 0
    )
