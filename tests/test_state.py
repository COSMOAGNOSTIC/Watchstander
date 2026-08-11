"""
Tests for agent_core/state.py's WorkPackageState invariants.

`cleared_for_execution` didn't have any direct coverage before this --
its correctness was only exercised indirectly through hitl.py/graph.py
tests, which never happened to construct a CRITICAL-risk package and
inspect the field before the HITL gate ran on it.
"""

import pytest
from pydantic import ValidationError

from agent_core.state import HitlDisposition, RiskLevel, SpatialCoordinates, WorkPackageState


def test_cleared_for_execution_defaults_true_for_a_package_that_never_needs_review():
    wp = WorkPackageState(work_package_id="WP-CLEAN", description="routine work, low risk")
    assert wp.cleared_for_execution is True


def test_cleared_for_execution_fails_closed_for_an_unreviewed_critical_package():
    """
    An independent code review found `cleared_for_execution` defaulted to
    True even for a RiskLevel.CRITICAL package that hasn't been reviewed
    yet -- any consumer checking only that field (exactly what its own
    docstring instructs) would treat an unreviewed critical package as
    cleared, from the moment it's constructed, before it even enters the
    graph. Regression test for the model_validator fix.
    """
    wp = WorkPackageState(
        work_package_id="WP-CRIT",
        description="independently critical risk, no review yet",
        risk_level=RiskLevel.CRITICAL,
    )
    assert wp.hitl_disposition is None
    assert wp.cleared_for_execution is False


def test_cleared_for_execution_still_settable_once_a_disposition_exists():
    """
    The fail-closed validator must only tighten the *pending-review*
    default -- it must never fight hitl_gate_node's actual, authoritative
    decision once one has been recorded.
    """
    wp = WorkPackageState(
        work_package_id="WP-CRIT-APPROVED",
        description="critical risk, already reviewed and approved",
        risk_level=RiskLevel.CRITICAL,
        hitl_disposition=HitlDisposition.APPROVED,
        cleared_for_execution=True,
    )
    assert wp.cleared_for_execution is True


def test_cleared_for_execution_fails_closed_for_a_non_critical_review_required_package():
    """
    AUD-09 residual gap (AOSE Round 4, `aose-round4-crossreview-gemini-aud09.md`
    §3.1). The CRITICAL-risk case above was already closed; a package that
    is NOT critical risk, has no recorded conflict, but has
    `requires_hitl_review=True` set directly (e.g. a submitter flagging it
    for review for a reason outside risk-level/conflict machinery) was not
    -- it read `cleared_for_execution=True` from construction until an
    actual disposition landed. Regression test for the validator's fix.
    """
    wp = WorkPackageState(
        work_package_id="WP-FLAGGED",
        description="low risk, no conflict, but flagged for review directly",
        risk_level=RiskLevel.LOW,
        requires_hitl_review=True,
    )
    assert wp.hitl_disposition is None
    assert wp.cleared_for_execution is False


def test_cleared_for_execution_still_settable_for_a_review_required_package_once_decided():
    """Same non-fighting-the-authoritative-decision guarantee as the
    CRITICAL case, for the requires_hitl_review path."""
    wp = WorkPackageState(
        work_package_id="WP-FLAGGED-APPROVED",
        description="flagged for review, already reviewed and approved",
        requires_hitl_review=True,
        hitl_disposition=HitlDisposition.APPROVED,
        cleared_for_execution=True,
    )
    assert wp.cleared_for_execution is True


def test_frame_start_after_frame_end_is_rejected():
    """
    AOSE Round 5 (Grok AUD-04, reproduced and confirmed). Before this
    validator existed, a transposed frame_start/frame_end silently changed
    what _frame_ranges_overlap() reported in deconfliction.py instead of
    being caught at the door.
    """
    with pytest.raises(ValidationError, match="frame_start"):
        SpatialCoordinates(frame_start=90, frame_end=80)


def test_frame_start_equal_to_frame_end_is_allowed():
    """Closed interval [start, end] -- a single-frame package is valid."""
    coords = SpatialCoordinates(frame_start=85, frame_end=85)
    assert coords.frame_start == coords.frame_end == 85


def test_frame_range_with_one_side_unset_is_allowed():
    """Partial frame data is a known, accepted state -- only reject when
    both sides are present and actually inverted."""
    coords = SpatialCoordinates(frame_start=85)
    assert coords.frame_end is None


def test_scheduled_start_after_scheduled_end_is_rejected():
    """
    AOSE Round 5 (Grok AUD-04, reproduced and confirmed). Before this
    validator existed, a transposed scheduled_start/scheduled_end made
    check_conflict() return "no conflict" for a genuinely overlapping,
    incompatible-hazard-pair pair of packages -- a real under-flag from a
    single data-entry typo, with nothing downstream able to catch it.
    """
    with pytest.raises(ValidationError, match="scheduled_start"):
        WorkPackageState(
            work_package_id="WP-BAD-SCHEDULE",
            description="typo'd schedule, start after end",
            scheduled_start="2026-08-15T15:00:00",
            scheduled_end="2026-08-15T07:00:00",
        )


def test_scheduled_start_equal_to_scheduled_end_is_allowed():
    """Closed interval [start, end] -- a zero-duration/instant task is valid."""
    wp = WorkPackageState(
        work_package_id="WP-INSTANT",
        description="point-in-time task",
        scheduled_start="2026-08-15T07:00:00",
        scheduled_end="2026-08-15T07:00:00",
    )
    assert wp.scheduled_start == wp.scheduled_end


def test_schedule_with_one_side_unset_is_allowed():
    """Partial schedule data is a known, accepted state (treated as
    over-flagging/unknown by _schedules_overlap) -- only reject when both
    sides are present and actually inverted."""
    wp = WorkPackageState(
        work_package_id="WP-PARTIAL-SCHEDULE",
        description="only a start date filled in so far",
        scheduled_start="2026-08-15T07:00:00",
    )
    assert wp.scheduled_end is None
