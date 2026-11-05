"""
Shift-aware fix suggester: move a whole crew's block of work to the next open
shift, re-checked against every rule, never applied.

`reschedule_suggestion.suggest_reschedule()` nudges one package by the
smallest whole step in either direction. That ignores how yard work is
actually organized: a crew works a shift, and moving one of its jobs
without the others splits the crew or double-books it. This module moves
the crew's whole block -- every package that crew starts in the target's
shift -- by one offset, so it lands at the same position in a later shift.

    target -> its crew + the shift it starts in -> BLOCK
    any package in BLOCK locked                    -> no suggestion (reason)
    for each later shift, in order, up to max_shifts:
        move BLOCK by (shift.start - current_shift.start)
        no conflict rule on a moved package    --+
        no fire-watch overload on one           --+
        certificates still cover each           --+--[AND]--> suggest this shift
        crew/shift/contractor rules pass        --+
        no judgment flag on a moved package     --+
        otherwise record (shift, failing rule IDs) and try the next
    none pass -> no suggestion, every rejection listed

Design choices:
- Forward only. Moving work earlier is usually harder to staff and to
  permit (AOSE Round 6, Opus), and "the next open shift" means later.
- Only findings that name a moved package count. A violation elsewhere in
  the yard never blocks this crew's move (same rule as ADR-034).
- A judgment flag on a moved package rejects the candidate. A move that
  can't be checked (for example an unlocated hot-work package) is never
  suggested.
- Certificates and contractor windows never move. They're hard limits
  (ADR-031); only the work is shifted.
- Pure. Nothing here writes to a WorkPackageState. `applied` is always
  False; applying a suggestion is a separate, human-approved step
  (Session 8).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, Field

from agent_core.certificates import Certificate, check_certificates
from agent_core.crews import Crew, ShiftCalendar, check_schedule_constraints, is_movable
from agent_core.deconfliction import conflict_rule_ids, fire_watch_overloads
from agent_core.judgment import judgment_flags
from agent_core.named_rules import rule_for_fire_watch_capacity
from agent_core.reschedule_suggestion import _shifted_copy
from agent_core.state import WorkPackageState
from agent_core.validation import instant

CHECKS = ["conflicts", "fire_watch", "certificates", "schedule", "judgment"]


class PackageMove(BaseModel):
    work_package_id: str
    original_start: datetime
    original_end: datetime
    suggested_start: datetime
    suggested_end: datetime


class CrewShiftSuggestion(BaseModel):
    crew_id: str
    from_shift_id: str
    to_shift_id: str
    offset: timedelta
    moves: list[PackageMove]
    checks: list[str] = Field(default_factory=lambda: list(CHECKS))
    source: Literal["deterministic_shift_search"] = "deterministic_shift_search"
    applied: Literal[False] = False


class RejectedShift(BaseModel):
    shift_id: str
    rule_ids: list[str]


class CrewShiftOutcome(BaseModel):
    suggestion: Optional[CrewShiftSuggestion] = None
    rejected: list[RejectedShift] = Field(default_factory=list)
    reason: Optional[str] = None


def _failures(trial: list[WorkPackageState], moved_ids: set[str], crews: list[Crew],
              calendar: ShiftCalendar, certificates: list[Certificate]) -> list[str]:
    """Rule IDs of every finding that names a moved package in the trial arrangement."""
    by_id = {p.work_package_id: p for p in trial}
    failed: set[str] = set()

    for mid in sorted(moved_ids):
        m = by_id[mid]
        for other in trial:
            if other is not m:
                failed.update(conflict_rule_ids(m, other))

    if any(moved_ids & {w.work_package_id for w in over} for _, _, over in fire_watch_overloads(trial)):
        failed.add(rule_for_fire_watch_capacity().rule_id)

    for mid in moved_ids:
        failed.update(f.rule_id for f in check_certificates(by_id[mid], certificates))

    failed.update(f.rule_id for f in check_schedule_constraints(trial, crews, calendar)
                  if moved_ids & set(f.work_package_ids))

    failed.update(f.rule_id for f in judgment_flags(trial)
                  if moved_ids & set(f.work_package_ids))

    return sorted(failed)


def suggest_crew_shift(
    packages: list[WorkPackageState],
    target_id: str,
    *,
    crews: list[Crew],
    calendar: ShiftCalendar,
    certificates: list[Certificate],
    max_shifts: int = 6,
) -> CrewShiftOutcome:
    """
    Suggest moving `target_id`'s crew block to the first later shift (at most
    `max_shifts` tried) where every check passes. Returns an outcome with the
    suggestion, every rejected shift and its failing rule IDs, or a reason
    there is nothing to search. Raises ValueError for an unknown target or
    duplicate package IDs.
    """
    ids = [p.work_package_id for p in packages]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate work_package_id: {dupes}")
    pkgs = sorted(packages, key=lambda p: p.work_package_id)
    target = next((p for p in pkgs if p.work_package_id == target_id), None)
    if target is None:
        raise ValueError(f"no package with id {target_id!r}")

    if target.scheduled_start is None or target.scheduled_end is None:
        return CrewShiftOutcome(reason=f"{target_id} has no complete schedule to move.")
    if not target.crew_id:
        return CrewShiftOutcome(reason=f"{target_id} has no crew assigned, so there is no crew block to move.")
    if target.crew_id not in {c.crew_id for c in crews}:
        return CrewShiftOutcome(reason=f"{target_id}'s crew {target.crew_id!r} is not in the crew list.")

    current = calendar.shift_at(target.scheduled_start)
    if current is None:
        return CrewShiftOutcome(reason=f"{target_id} starts outside every shift in the calendar.")

    block = [p for p in pkgs
             if p.crew_id == target.crew_id and p.scheduled_start is not None and p.scheduled_end is not None
             and instant(current.start) <= instant(p.scheduled_start) < instant(current.end)]
    locked = [p.work_package_id for p in block if not is_movable(p)]
    if locked:
        return CrewShiftOutcome(reason=f"crew block can't move: {', '.join(locked)} is locked.")

    block_ids = {p.work_package_id for p in block}
    others = [p for p in pkgs if p.work_package_id not in block_ids]
    later = [s for s in calendar.shifts if instant(s.start) >= instant(current.end)][:max_shifts]
    if not later:
        return CrewShiftOutcome(reason=f"no later shift in the calendar after {current.shift_id}.")

    rejected: list[RejectedShift] = []
    for shift in later:
        offset = instant(shift.start) - instant(current.start)
        moved = [_shifted_copy(p, offset) for p in block]
        failed = _failures(others + moved, block_ids, crews, calendar, certificates)
        if failed:
            rejected.append(RejectedShift(shift_id=shift.shift_id, rule_ids=failed))
            continue
        return CrewShiftOutcome(
            suggestion=CrewShiftSuggestion(
                crew_id=target.crew_id, from_shift_id=current.shift_id, to_shift_id=shift.shift_id,
                offset=offset,
                moves=[PackageMove(work_package_id=o.work_package_id,
                                   original_start=o.scheduled_start, original_end=o.scheduled_end,
                                   suggested_start=m.scheduled_start, suggested_end=m.scheduled_end)
                       for o, m in zip(block, moved)],
            ),
            rejected=rejected,
        )

    return CrewShiftOutcome(
        rejected=rejected,
        reason=f"no shift among the next {len(later)} passes every check for crew {target.crew_id}.",
    )
