"""
Projects, priority, due dates, and a deterministic status rollup.

A Project groups existing WorkPackageStates by ID. Nothing here changes
a work package or decides anything about safety: `package_status()` only
reads fields the deconfliction and HITL machinery already set, and the
rollup only aggregates those readings.

Status is derived, never stored, so it cannot drift from the fields it
summarizes. There is deliberately no DONE/COMPLETED status -- the
package schema has no completion field, and inventing one here would
let a rollup report work as finished that nothing ever recorded as
finished.

Every function is a pure function of its arguments. "Now" is always
passed in as `as_of`, never read from the clock, so the same inputs
always give the same rollup.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Iterable, Optional

from pydantic import BaseModel, Field, field_validator

from agent_core.state import HitlDisposition, RiskLevel, WorkPackageState


class Priority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    ROUTINE = "routine"
    LOW = "low"


_PRIORITY_RANK = {Priority.URGENT: 0, Priority.HIGH: 1, Priority.ROUTINE: 2, Priority.LOW: 3}


class PackageStatus(str, Enum):
    """Listed worst-first; a project's overall status is its worst package's."""

    BLOCKED = "blocked"  # reviewed and not approved, or not cleared for an unknown reason
    PENDING_REVIEW = "pending_review"  # needs a HITL decision that hasn't been made
    UNSCHEDULED = "unscheduled"  # cleared, but missing a start or end time
    CLEARED = "cleared"  # cleared for execution and fully scheduled


_SEVERITY = list(PackageStatus)  # worst first


class Project(BaseModel):
    project_id: str
    name: str
    priority: Priority = Priority.ROUTINE
    due_date: Optional[datetime] = None
    work_package_ids: list[str] = Field(default_factory=list)

    @field_validator("work_package_ids")
    @classmethod
    def _no_duplicate_ids(cls, ids: list[str]) -> list[str]:
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate work_package_ids in project: {dupes}")
        return ids


class ProjectRollup(BaseModel):
    project_id: str
    priority: Priority
    due_date: Optional[datetime]
    as_of: datetime
    package_count: int
    overall_status: PackageStatus
    status_counts: dict[PackageStatus, int]
    package_ids_by_status: dict[PackageStatus, list[str]]
    late_package_ids: list[str] = Field(
        description="Packages whose scheduled_end is after the project due date. "
        "Unscheduled packages can't be judged late; they appear under UNSCHEDULED."
    )
    past_due: bool = Field(description="True when as_of is after the project due date.")


def package_status(pkg: WorkPackageState) -> PackageStatus:
    """
    Derive one package's status from fields already on it. Fails closed:
    a package with `cleared_for_execution=False` is never reported CLEARED
    or UNSCHEDULED, even when no other field explains why.
    """
    if pkg.hitl_disposition is not None and pkg.hitl_disposition != HitlDisposition.APPROVED:
        return PackageStatus.BLOCKED
    if not pkg.cleared_for_execution:
        awaiting_review = pkg.hitl_disposition is None and (
            pkg.requires_hitl_review or pkg.risk_level == RiskLevel.CRITICAL
        )
        return PackageStatus.PENDING_REVIEW if awaiting_review else PackageStatus.BLOCKED
    if pkg.scheduled_start is None or pkg.scheduled_end is None:
        return PackageStatus.UNSCHEDULED
    return PackageStatus.CLEARED


def rollup_project(
    project: Project, packages: Iterable[WorkPackageState], as_of: datetime
) -> ProjectRollup:
    """
    Roll up the project's packages. `packages` may contain packages from
    other projects; only the project's own IDs are read. Raises ValueError
    if a project ID has no matching package, or if `packages` repeats an
    ID -- a rollup that silently skipped a package would understate risk.
    """
    by_id: dict[str, WorkPackageState] = {}
    for p in packages:
        if p.work_package_id in by_id:
            raise ValueError(f"duplicate work_package_id in packages: {p.work_package_id}")
        by_id[p.work_package_id] = p

    missing = [i for i in project.work_package_ids if i not in by_id]
    if missing:
        raise ValueError(f"project {project.project_id} references unknown work packages: {missing}")

    members = [by_id[i] for i in project.work_package_ids]
    ids_by_status: dict[PackageStatus, list[str]] = {s: [] for s in _SEVERITY}
    for p in members:
        ids_by_status[package_status(p)].append(p.work_package_id)

    if members:
        overall = next(s for s in _SEVERITY if ids_by_status[s])
    else:
        overall = PackageStatus.UNSCHEDULED  # nothing scheduled, so never green

    due = project.due_date
    late = (
        [p.work_package_id for p in members if p.scheduled_end is not None and p.scheduled_end > due]
        if due is not None
        else []
    )

    return ProjectRollup(
        project_id=project.project_id,
        priority=project.priority,
        due_date=due,
        as_of=as_of,
        package_count=len(members),
        overall_status=overall,
        status_counts={s: len(ids_by_status[s]) for s in _SEVERITY},
        package_ids_by_status=ids_by_status,
        late_package_ids=late,
        past_due=due is not None and as_of > due,
    )


def sort_projects(projects: Iterable[Project]) -> list[Project]:
    """Priority first, then earliest due date (none last), then project_id."""
    return sorted(
        projects,
        key=lambda p: (
            _PRIORITY_RANK[p.priority],
            p.due_date is None,
            p.due_date or datetime.min,
            p.project_id,
        ),
    )
