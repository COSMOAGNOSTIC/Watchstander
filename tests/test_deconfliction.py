from agent_core.deconfliction import check_conflict, find_all_conflicts
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
