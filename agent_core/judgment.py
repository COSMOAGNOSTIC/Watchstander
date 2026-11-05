"""
Judgment flags: calls the deterministic engine can't make, routed to a named person.

A conflict from `deconfliction.py` says "these two must not run together."
A judgment flag says something weaker and different: "the engine can't
tell, and a qualified person has to look." Three triggers, each a named
rule in `case_data/named_rules_v1.json` (category `judgment`), all routed
to the Gas Free Engineer:

- WS-JF-001  hot work and a confined space run concurrently within
             JUDGMENT_ADJACENCY_FRAMES frames of each other but don't
             overlap, so WS-HZ-001 never fires (Known Debt: no adjacency
             tolerance). Not raised when detection already flags the pair.
- WS-JF-002  two concurrent confined-space packages in the same space;
             detection has no confined_space/confined_space pair.
- WS-JF-003  a hot-work or confined-space package with no location, which
             can never be spatially deconflicted.

Flags are deterministic, sorted, and never mutate a package. They don't
change detection or `check_conflict()` -- they are a separate channel so
known blind spots reach a person instead of passing silently. Nothing
here (or in any LLM layer) decides the call; the person does.

Routing reads a notional roster (`case_data/roster_notional_v1.json`):
each flag goes to the primary person for its rule's `contact_role`. A
roster with no primary for a judgment rule's role fails loudly before any
flag is produced -- a flag routed to nobody is the failure this prevents.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Iterable, Optional

from pydantic import BaseModel, model_validator

from agent_core import named_rules
from agent_core.deconfliction import (
    _frame_ranges_overlap,
    _same_compartment,
    _schedules_overlap,
    check_conflict,
)
from agent_core.named_rules import NamedRule, RuleCategory
from agent_core.state import HazardCategory, WorkPackageState

_DEFAULT_ROSTER = Path(__file__).resolve().parent.parent / "case_data" / "roster_notional_v1.json"
ROSTER_SCHEMA_VERSION = 1

# Notional review-prompt threshold, NOT a regulatory distance. Frames between
# the nearer ends of two non-overlapping ranges (110 and 112 -> 2).
JUDGMENT_ADJACENCY_FRAMES = 3

_GAS_FREE_HAZARDS = {HazardCategory.HOT_WORK, HazardCategory.CONFINED_SPACE}


class RosterPerson(BaseModel):
    person_id: str
    display_name: str
    role: str
    primary: bool = False
    notional: bool

    @model_validator(mode="after")
    def _must_be_notional(self) -> "RosterPerson":
        if self.notional is not True:
            raise ValueError(f"roster entry {self.person_id} must be marked notional=true")
        return self


class Roster(BaseModel):
    people: list[RosterPerson]

    @model_validator(mode="after")
    def _ids_unique_one_primary_per_role(self) -> "Roster":
        ids = [p.person_id for p in self.people]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate person_id in roster: {dupes}")
        primaries: dict[str, str] = {}
        for p in self.people:
            if p.primary:
                if p.role in primaries:
                    raise ValueError(
                        f"two primary entries for role {p.role!r}: "
                        f"{primaries[p.role]} and {p.person_id}"
                    )
                primaries[p.role] = p.person_id
        return self

    def primary_for(self, role: str) -> RosterPerson:
        for p in self.people:
            if p.primary and p.role == role:
                return p
        raise LookupError(f"no primary roster entry for role {role!r}")


def load_roster(path: Optional[Path] = None) -> Roster:
    with open(path or _DEFAULT_ROSTER, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if raw.get("schema_version") != ROSTER_SCHEMA_VERSION:
        raise ValueError(f"roster schema_version {raw.get('schema_version')!r} != {ROSTER_SCHEMA_VERSION}")
    return Roster(people=raw["people"])


class JudgmentFlag(BaseModel):
    flag_id: str
    rule_id: str
    work_package_ids: list[str]
    reason: str
    routed_to: RosterPerson
    escalation_role: Optional[str]
    message: str


def _hazards(p: WorkPackageState) -> set[HazardCategory]:
    return {HazardCategory(h) for h in p.hazard_categories}


def _located(p: WorkPackageState) -> bool:
    s = p.spatial
    return bool(s.compartment_id) or (s.frame_start is not None and s.frame_end is not None)


def _frame_gap(a: WorkPackageState, b: WorkPackageState) -> Optional[int]:
    """Frames between two non-overlapping ranges; None if either lacks frames or they overlap."""
    sa, sb = a.spatial, b.spatial
    if None in (sa.frame_start, sa.frame_end, sb.frame_start, sb.frame_end):
        return None
    if _frame_ranges_overlap(a, b):
        return None
    return max(sa.frame_start, sb.frame_start) - min(sa.frame_end, sb.frame_end)


def _flag(rule: NamedRule, ids: list[str], reason: str, roster: Roster) -> JudgmentFlag:
    ids = sorted(ids)
    person = roster.primary_for(rule.contact_role)
    return JudgmentFlag(
        flag_id=f"{rule.rule_id}:{'+'.join(ids)}",
        rule_id=rule.rule_id,
        work_package_ids=ids,
        reason=reason,
        routed_to=person,
        escalation_role=rule.escalation_role,
        message=(
            f"{rule.rule_id} ({rule.title}) for {', '.join(ids)}: {reason} "
            f"Judgment call for {rule.contact_role} {person.display_name} ({person.person_id})."
        ),
    )


def judgment_flags(
    packages: Iterable[WorkPackageState], roster: Optional[Roster] = None
) -> list[JudgmentFlag]:
    """All judgment flags for `packages`, sorted by flag_id. Pure; never mutates input."""
    roster = roster or load_roster()
    for r in named_rules.RULES:
        if r.category == RuleCategory.JUDGMENT:
            roster.primary_for(r.contact_role)  # fail before producing anything

    pkgs = sorted(packages, key=lambda p: p.work_package_id)
    jf1, jf2, jf3 = (named_rules.get_rule(i) for i in ("WS-JF-001", "WS-JF-002", "WS-JF-003"))
    flags: list[JudgmentFlag] = []

    for a, b in combinations(pkgs, 2):
        if a.work_package_id == b.work_package_id or not _schedules_overlap(a, b):
            continue
        ha, hb = _hazards(a), _hazards(b)

        hot_and_cs = (HazardCategory.HOT_WORK in ha and HazardCategory.CONFINED_SPACE in hb) or (
            HazardCategory.HOT_WORK in hb and HazardCategory.CONFINED_SPACE in ha
        )
        gap = _frame_gap(a, b)
        if hot_and_cs and gap is not None and gap <= JUDGMENT_ADJACENCY_FRAMES and check_conflict(a, b) is None:
            flags.append(_flag(jf1, [a.work_package_id, b.work_package_id],
                               f"hot work and confined space are {gap} frame(s) apart and concurrent; "
                               "detection does not flag adjacency.", roster))

        if (HazardCategory.CONFINED_SPACE in ha and HazardCategory.CONFINED_SPACE in hb
                and (_same_compartment(a, b) or _frame_ranges_overlap(a, b))):
            flags.append(_flag(jf2, [a.work_package_id, b.work_package_id],
                               "two confined-space entries share a space at the same time.", roster))

    for p in pkgs:
        if _hazards(p) & _GAS_FREE_HAZARDS and not _located(p):
            flags.append(_flag(jf3, [p.work_package_id],
                               "no compartment and no complete frame range, so it cannot be "
                               "spatially deconflicted.", roster))

    return sorted(flags, key=lambda f: f.flag_id)
