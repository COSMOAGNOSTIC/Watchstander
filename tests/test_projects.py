"""Session 2: projects, priority, due dates, status rollup.

All data here is notional -- no real ship, yard, or personnel data.
"""

from datetime import datetime

import pytest

from agent_core.projects import (
    PackageStatus,
    Priority,
    Project,
    package_status as _package_status,
    rollup_project as _rollup_project,
    sort_projects,
)
from agent_core.state import HitlDisposition, RiskLevel, WorkPackageState

AS_OF = datetime(2027, 1, 10, 8, 0)

# These tests exercise the review/schedule half of the status gate, so every
# other check is passed as "ran, found nothing". The findings half and the
# missing-input refusal are tested in tests/test_review01_fixes.py (R01/R02).
NO_FINDINGS = dict(certificate_findings=[], judgment_flags=[], schedule_findings=[])


def package_status(p):
    return _package_status(p, **NO_FINDINGS)


def rollup_project(*args, **kwargs):
    return _rollup_project(*args, **NO_FINDINGS, **kwargs)


def _pkg(pid, start=datetime(2027, 1, 12, 7), end=datetime(2027, 1, 12, 15), **kw):
    return WorkPackageState(
        work_package_id=pid,
        description=f"notional package {pid}",
        scheduled_start=start,
        scheduled_end=end,
        **kw,
    )


# --- package_status -------------------------------------------------------


def test_scheduled_package_needing_no_review_is_cleared():
    assert package_status(_pkg("WP-1")) == PackageStatus.CLEARED


def test_package_with_no_schedule_is_unscheduled():
    assert package_status(_pkg("WP-1", start=None, end=None)) == PackageStatus.UNSCHEDULED


def test_package_with_only_one_schedule_bound_is_unscheduled():
    assert package_status(_pkg("WP-1", end=None)) == PackageStatus.UNSCHEDULED


def test_package_awaiting_review_is_pending_review():
    assert package_status(_pkg("WP-1", requires_hitl_review=True)) == PackageStatus.PENDING_REVIEW


def test_critical_package_with_no_disposition_is_pending_review():
    assert package_status(_pkg("WP-1", risk_level=RiskLevel.CRITICAL)) == PackageStatus.PENDING_REVIEW


@pytest.mark.parametrize("disp", [HitlDisposition.REJECTED, HitlDisposition.INVALID])
def test_rejected_or_invalid_review_is_blocked(disp):
    p = _pkg("WP-1", requires_hitl_review=True, hitl_disposition=disp, cleared_for_execution=False)
    assert package_status(p) == PackageStatus.BLOCKED


def test_approved_review_is_cleared():
    p = _pkg("WP-1", requires_hitl_review=True, hitl_disposition=HitlDisposition.APPROVED)
    assert package_status(p) == PackageStatus.CLEARED


def test_not_cleared_without_disposition_is_never_reported_cleared():
    # Fail closed: any package not cleared for execution must not roll up as CLEARED,
    # even if no field explains why.
    p = _pkg("WP-1", cleared_for_execution=False)
    assert package_status(p) != PackageStatus.CLEARED


def test_blocked_outranks_unscheduled():
    p = _pkg(
        "WP-1", start=None, end=None, requires_hitl_review=True,
        hitl_disposition=HitlDisposition.REJECTED, cleared_for_execution=False,
    )
    assert package_status(p) == PackageStatus.BLOCKED


def test_pending_review_outranks_unscheduled():
    p = _pkg("WP-1", start=None, end=None, requires_hitl_review=True)
    assert package_status(p) == PackageStatus.PENDING_REVIEW


# --- Project model --------------------------------------------------------


def test_project_rejects_duplicate_package_ids():
    with pytest.raises(ValueError, match="duplicate"):
        Project(project_id="PRJ-1", name="Notional", priority=Priority.ROUTINE,
                work_package_ids=["WP-1", "WP-1"])


def test_project_priority_defaults_to_routine():
    assert Project(project_id="PRJ-1", name="Notional").priority == Priority.ROUTINE


# --- rollup_project -------------------------------------------------------


def _project(ids, due=datetime(2027, 1, 20, 16), priority=Priority.HIGH):
    return Project(project_id="PRJ-1", name="Notional tank blast and coat",
                   priority=priority, due_date=due, work_package_ids=ids)


def test_rollup_all_cleared_is_cleared_and_counts_every_status():
    r = rollup_project(_project(["WP-1", "WP-2"]), [_pkg("WP-1"), _pkg("WP-2")], as_of=AS_OF)
    assert r.overall_status == PackageStatus.CLEARED
    assert r.status_counts == {
        PackageStatus.BLOCKED: 0, PackageStatus.PENDING_REVIEW: 0, PackageStatus.HAS_FINDINGS: 0,
        PackageStatus.UNSCHEDULED: 0, PackageStatus.CLEARED: 2,
    }
    assert r.package_count == 2


def test_rollup_overall_status_is_the_worst_package_status():
    pkgs = [
        _pkg("WP-1"),
        _pkg("WP-2", start=None, end=None),
        _pkg("WP-3", requires_hitl_review=True),
    ]
    r = rollup_project(_project(["WP-1", "WP-2", "WP-3"]), pkgs, as_of=AS_OF)
    assert r.overall_status == PackageStatus.PENDING_REVIEW
    assert r.package_ids_by_status[PackageStatus.PENDING_REVIEW] == ["WP-3"]
    assert r.package_ids_by_status[PackageStatus.UNSCHEDULED] == ["WP-2"]


def test_rollup_ignores_packages_not_in_the_project():
    pkgs = [_pkg("WP-1"), _pkg("WP-OTHER", requires_hitl_review=True)]
    r = rollup_project(_project(["WP-1"]), pkgs, as_of=AS_OF)
    assert r.overall_status == PackageStatus.CLEARED
    assert r.package_count == 1


def test_rollup_raises_on_unknown_package_id():
    with pytest.raises(ValueError, match="WP-MISSING"):
        rollup_project(_project(["WP-1", "WP-MISSING"]), [_pkg("WP-1")], as_of=AS_OF)


def test_rollup_raises_on_duplicate_package_ids_in_input():
    with pytest.raises(ValueError, match="duplicate"):
        rollup_project(_project(["WP-1"]), [_pkg("WP-1"), _pkg("WP-1")], as_of=AS_OF)


def test_empty_project_rolls_up_unscheduled_not_cleared():
    # A project with no work packages has nothing cleared -- never report it green.
    r = rollup_project(_project([]), [], as_of=AS_OF)
    assert r.overall_status == PackageStatus.UNSCHEDULED
    assert r.package_count == 0


def test_package_finishing_after_due_date_is_listed_late():
    pkgs = [_pkg("WP-1"), _pkg("WP-2", start=datetime(2027, 1, 20, 7), end=datetime(2027, 1, 21, 15))]
    r = rollup_project(_project(["WP-1", "WP-2"]), pkgs, as_of=AS_OF)
    assert r.late_package_ids == ["WP-2"]


def test_package_ending_exactly_on_due_date_is_not_late():
    due = datetime(2027, 1, 12, 15)
    r = rollup_project(_project(["WP-1"], due=due), [_pkg("WP-1")], as_of=AS_OF)
    assert r.late_package_ids == []


def test_no_due_date_means_nothing_late_and_not_past_due():
    r = rollup_project(_project(["WP-1"], due=None), [_pkg("WP-1")], as_of=datetime(2099, 1, 1))
    assert r.late_package_ids == []
    assert r.past_due is False


def test_past_due_is_judged_against_as_of_not_the_clock():
    due = datetime(2027, 1, 20, 16)
    before = rollup_project(_project(["WP-1"], due=due), [_pkg("WP-1")], as_of=datetime(2027, 1, 20, 16))
    after = rollup_project(_project(["WP-1"], due=due), [_pkg("WP-1")], as_of=datetime(2027, 1, 20, 16, 1))
    assert before.past_due is False
    assert after.past_due is True


# --- sort_projects --------------------------------------------------------


def test_sort_by_priority_then_due_date_then_id():
    p = lambda pid, pr, due: Project(project_id=pid, name=pid, priority=pr, due_date=due)
    projects = [
        p("C", Priority.ROUTINE, datetime(2027, 1, 5)),
        p("B", Priority.URGENT, datetime(2027, 2, 1)),
        p("A", Priority.URGENT, datetime(2027, 2, 1)),
        p("D", Priority.URGENT, datetime(2027, 1, 15)),
        p("E", Priority.URGENT, None),
        p("F", Priority.LOW, datetime(2027, 1, 1)),
        p("G", Priority.HIGH, None),
    ]
    assert [x.project_id for x in sort_projects(projects)] == ["D", "A", "B", "E", "G", "C", "F"]


def test_sort_does_not_mutate_input():
    projects = [Project(project_id="B", name="B"), Project(project_id="A", name="A")]
    sort_projects(projects)
    assert [x.project_id for x in projects] == ["B", "A"]
