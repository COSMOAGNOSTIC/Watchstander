"""
Notional carrier dataset (Session 10): the default demo, invented end to end.

The only demo dataset. AGENTS.md rule 6 says all demo data is notional; the earlier
real-ship demo (compartments read off public drawings of a real cutter) was deleted
in Session 10 (ADR-049). The reviewer's seed button and the visualizer both use this.

The data lives in `case_data/carrier_notional_v1.json`. The loader refuses it unless
it is marked `notional: true`, and refuses any reference that doesn't resolve
(a project or certificate naming a package that isn't there, a package naming a crew
that isn't there would be a schedule finding, so that one is left to the checks).
Nothing here decides anything: it only loads and validates data.
"""

from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from agent_core.certificates import Certificate
from agent_core.crews import Crew, ShiftCalendar
from agent_core.projects import Project
from agent_core.state import WorkPackageState

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "case_data" / "carrier_notional_v1.json"
SCHEMA_VERSION = 1


class ShiftPatternEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")  # review-05 R05-04
    name: str
    start: time
    end: time


class CarrierDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")  # review-05 R05-04
    schema_version: int
    notional: StrictBool  # Session 10: "yes" must not coerce to True
    source_note: str
    site: str
    first_day: date
    days: int = Field(ge=1)
    shift_pattern: list[ShiftPatternEntry]
    crews: list[Crew]
    packages: list[WorkPackageState]
    certificates: list[Certificate]
    projects: list[Project]

    @model_validator(mode="after")
    def _notional_and_consistent(self) -> "CarrierDataset":
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"carrier dataset schema_version {self.schema_version} != {SCHEMA_VERSION}")
        if self.notional is not True:
            raise ValueError("carrier dataset must be marked notional=true (AGENTS.md rule 6)")
        ids = [p.work_package_id for p in self.packages]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate work_package_id in dataset: {dupes}")
        known = set(ids)
        for pr in self.projects:
            missing = [i for i in pr.work_package_ids if i not in known]
            if missing:
                raise ValueError(f"project {pr.project_id} names unknown packages: {missing}")
        for c in self.certificates:
            if c.work_package_id is not None and c.work_package_id not in known:
                raise ValueError(f"certificate {c.certificate_id} names unknown package {c.work_package_id}")
        return self

    @property
    def calendar(self) -> ShiftCalendar:
        return ShiftCalendar.from_daily_pattern(
            self.first_day, self.days, [(s.name, s.start, s.end) for s in self.shift_pattern])

    def fresh_packages(self) -> list[WorkPackageState]:
        """Deep copies, so a run can annotate them without touching the dataset."""
        return [p.model_copy(deep=True) for p in self.packages]


def load_carrier_dataset(path: Optional[Path] = None) -> CarrierDataset:
    return CarrierDataset.model_validate(json.loads(Path(path or DEFAULT_PATH).read_text()))
