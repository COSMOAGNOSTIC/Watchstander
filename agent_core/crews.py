"""
Crews, a shift calendar, locked packages, and contractor windows.

The data model Session 7's shift-aware suggester needs, plus report-only
planning checks. Nothing here moves or changes a package.

- `ShiftCalendar` is a list of concrete, non-overlapping shifts (built by
  hand or from a daily pattern; a shift whose end time is earlier than its
  start crosses midnight). Membership is half-open, [start, end), so 1530
  belongs to the shift that starts at 1530, not the one that ends there.
- `Crew` is organic or contractor. A contractor crew may only work inside
  its `contractor_windows`; a contractor with no windows may work nowhere.
- `WorkPackageState.locked` (state.py) marks a schedule as fixed; a lock
  requires a `lock_reason`. `is_movable()` is the one place suggesters ask.

`check_schedule_constraints()` reports four named rules (category
`schedule`, case_data/named_rules_v1.json): WS-SC-001 unknown crew,
WS-SC-002 contractor work outside its windows (whole window, and an
unscheduled contractor package can't be verified), WS-SC-003 work outside
the shift calendar, WS-SC-004 one crew on overlapping packages. These are
planning constraints, not safety rules, and they never touch detection.

Coverage of a work window uses the same closed-interval helper as the
certificate check (agent_core/intervals.py). Double-booking uses strict
overlap on purpose: a crew finishing one job at 1100 and starting the
next at 1100 is normal sequencing, not a conflict.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import Enum
from itertools import combinations
from typing import Iterable, Optional

from pydantic import ConfigDict, BaseModel, Field, model_validator

from agent_core import named_rules
from agent_core.intervals import uncovered
from agent_core.validation import NonBlankStr, fmt_time, instant, require_comparable
from agent_core.state import WorkPackageState


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid")  # review-05 R05-04
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _ordered(self) -> "Window":
        require_comparable([("start", self.start), ("end", self.end)])
        if instant(self.start) > instant(self.end):
            raise ValueError(f"window start ({self.start}) must be <= end ({self.end})")
        return self


class Shift(BaseModel):
    model_config = ConfigDict(extra="forbid")  # review-05 R05-04
    shift_id: NonBlankStr
    name: str
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _has_length(self) -> "Shift":
        require_comparable([("start", self.start), ("end", self.end)])
        if instant(self.start) >= instant(self.end):
            raise ValueError(f"shift {self.shift_id}: start must be before end")
        return self


class ShiftCalendar(BaseModel):
    model_config = ConfigDict(extra="forbid")  # review-05 R05-04
    shifts: list[Shift]

    @model_validator(mode="after")
    def _sorted_unique_non_overlapping(self) -> "ShiftCalendar":
        ids = [s.shift_id for s in self.shifts]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate shift_id: {dupes}")
        require_comparable([(s.shift_id, s.start) for s in self.shifts])
        self.shifts = sorted(self.shifts, key=lambda s: (instant(s.start), s.shift_id))
        for prev, cur in zip(self.shifts, self.shifts[1:]):
            if instant(prev.end) > instant(cur.start):
                raise ValueError(f"shifts {prev.shift_id} and {cur.shift_id} overlap")
        return self

    @classmethod
    def from_daily_pattern(
        cls, first_day: date, days: int, pattern: list[tuple[str, time, time]]
    ) -> "ShiftCalendar":
        shifts = []
        for n in range(days):
            d = first_day + timedelta(days=n)
            for name, s, e in pattern:
                start = datetime.combine(d, s)
                end = datetime.combine(d if e > s else d + timedelta(days=1), e)
                shifts.append(Shift(shift_id=f"{d:%Y%m%d}-{name}", name=name, start=start, end=end))
        return cls(shifts=shifts)

    def shift_at(self, t: datetime) -> Optional[Shift]:
        return next((s for s in self.shifts if instant(s.start) <= instant(t) < instant(s.end)), None)

    def next_shift(self, after: datetime) -> Optional[Shift]:
        """First shift starting at or after `after`."""
        return next((s for s in self.shifts if instant(s.start) >= instant(after)), None)


class Crew(BaseModel):
    model_config = ConfigDict(extra="forbid")  # review-05 R05-04
    crew_id: NonBlankStr
    name: str
    is_contractor: bool = False
    contractor_windows: list[Window] = Field(default_factory=list)

    @model_validator(mode="after")
    def _windows_only_for_contractors(self) -> "Crew":
        if self.contractor_windows and not self.is_contractor:
            raise ValueError(f"crew {self.crew_id}: only a contractor crew has contractor_windows")
        return self


def is_movable(pkg: WorkPackageState) -> bool:
    """False for a locked package. The one check a suggester must make."""
    return not pkg.locked


class ScheduleIssue(str, Enum):
    UNKNOWN_CREW = "unknown_crew"
    OUTSIDE_CONTRACTOR_WINDOW = "outside_contractor_window"
    UNSCHEDULED = "unscheduled"
    OUTSIDE_SHIFT_CALENDAR = "outside_shift_calendar"
    CREW_DOUBLE_BOOKED = "crew_double_booked"


class ScheduleFinding(BaseModel):
    rule_id: str
    issue: ScheduleIssue
    work_package_ids: list[str]
    crew_id: Optional[str]
    uncovered: list[tuple[datetime, datetime]] = Field(default_factory=list)
    message: str


def _fmt(t: datetime) -> str:
    return fmt_time(t)


def _spans(gaps: list[tuple[datetime, datetime]]) -> str:
    return "; ".join(f"{_fmt(a)} to {_fmt(b)}" for a, b in gaps)


def _finding(rid, issue, ids, crew_id, detail, gaps=()) -> ScheduleFinding:
    rule = named_rules.get_rule(rid)
    return ScheduleFinding(
        rule_id=rid, issue=issue, work_package_ids=sorted(ids), crew_id=crew_id,
        uncovered=list(gaps),
        message=f"{rid} ({rule.title}) for {', '.join(sorted(ids))}: {detail} Contact: {rule.contact_role}.",
    )


def check_schedule_constraints(
    packages: Iterable[WorkPackageState], crews: Iterable[Crew], calendar: Optional[ShiftCalendar]
) -> list[ScheduleFinding]:
    """Report-only. Sorted by (rule_id, package IDs). Raises on duplicate crew or package IDs.
    review-05 R05-10: with no calendar, only WS-SC-003 (needs the calendar) is skipped."""
    crew_list, pkgs = list(crews), sorted(packages, key=lambda p: p.work_package_id)
    for label, ids in (("crew_id", [c.crew_id for c in crew_list]),
                       ("work_package_id", [p.work_package_id for p in pkgs])):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate {label}: {dupes}")
    by_id = {c.crew_id: c for c in crew_list}
    shift_windows = [(s.start, s.end) for s in calendar.shifts] if calendar is not None else None
    out: list[ScheduleFinding] = []

    for p in pkgs:
        pid, cid = p.work_package_id, p.crew_id
        scheduled = p.scheduled_start is not None and p.scheduled_end is not None
        crew = by_id.get(cid) if cid else None

        if cid and crew is None:
            out.append(_finding("WS-SC-001", ScheduleIssue.UNKNOWN_CREW, [pid], cid,
                                f"crew {cid!r} is not in the crew list."))

        if crew is not None and crew.is_contractor:
            if not scheduled:
                out.append(_finding("WS-SC-002", ScheduleIssue.UNSCHEDULED, [pid], cid,
                                    "contractor package has no complete schedule, so its window "
                                    "cannot be verified."))
            else:
                gaps = uncovered(p.scheduled_start, p.scheduled_end,
                                 [(w.start, w.end) for w in crew.contractor_windows])
                if gaps:
                    out.append(_finding("WS-SC-002", ScheduleIssue.OUTSIDE_CONTRACTOR_WINDOW, [pid], cid,
                                        f"outside contractor windows for {_spans(gaps)}.", gaps))

        if scheduled and shift_windows is not None:
            gaps = uncovered(p.scheduled_start, p.scheduled_end, shift_windows)
            if gaps:
                out.append(_finding("WS-SC-003", ScheduleIssue.OUTSIDE_SHIFT_CALENDAR, [pid], cid,
                                    f"no shift covers {_spans(gaps)}.", gaps))

    for a, b in combinations(pkgs, 2):
        if not a.crew_id or a.crew_id != b.crew_id or a.crew_id not in by_id:
            continue
        if None in (a.scheduled_start, a.scheduled_end, b.scheduled_start, b.scheduled_end):
            continue
        if instant(a.scheduled_start) < instant(b.scheduled_end) and instant(b.scheduled_start) < instant(a.scheduled_end):
            out.append(_finding("WS-SC-004", ScheduleIssue.CREW_DOUBLE_BOOKED,
                                [a.work_package_id, b.work_package_id], a.crew_id,
                                f"crew {a.crew_id} is on both at once."))

    return sorted(out, key=lambda f: (f.rule_id, f.work_package_ids))
