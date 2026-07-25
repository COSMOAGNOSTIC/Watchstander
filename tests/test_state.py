"""
Tests for agent_core/state.py's WorkPackageState invariants.

`cleared_for_execution` didn't have any direct coverage before this --
its correctness was only exercised indirectly through hitl.py/graph.py
tests, which never happened to construct a CRITICAL-risk package and
inspect the field before the HITL gate ran on it.
"""

from agent_core.state import HitlDisposition, RiskLevel, WorkPackageState


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
