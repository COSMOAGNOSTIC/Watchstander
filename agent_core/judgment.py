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
- WS-JF-004  two concurrent gas-free packages with no common coordinate
             (one has only a compartment, the other only frames).
- WS-JF-005  gas-free work signalled by a spatial flag or permit but missing
             from the hazard list, which detection reads exclusively.
- WS-JF-006  overhead work (deconfliction.is_overhead) with no complete frame
             range. Routed to the Safety Officer, not the GFE (Session 8a).

"Gas-free" signals (review-01 R08) come from all three places the data can
say it: the hazard list, `spatial.is_enclosed_or_confined`, and the
permits (hot-work permit; confined-space entry permit). The catalogue's
judgment rule IDs must equal IMPLEMENTED_TRIGGERS exactly (R17), and a
batch with duplicate package IDs is refused (R06).

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

from pydantic import BaseModel, StrictBool, model_validator

from agent_core import named_rules
from agent_core.deconfliction import (
    is_overhead,
    _frame_ranges_overlap,
    _same_compartment,
    _schedules_overlap,
    check_conflict,
)
from agent_core.named_rules import NamedRule, RuleCategory
from agent_core.state import HazardCategory, WorkPackageState
from agent_core.validation import NonBlankStr

_DEFAULT_ROSTER = Path(__file__).resolve().parent.parent / "case_data" / "roster_notional_v1.json"
ROSTER_SCHEMA_VERSION = 1

# Notional review-prompt threshold, NOT a regulatory distance. Frames between
# the nearer ends of two non-overlapping ranges (110 and 112 -> 2).
JUDGMENT_ADJACENCY_FRAMES = 3

IMPLEMENTED_TRIGGERS = frozenset({"WS-JF-001", "WS-JF-002", "WS-JF-003", "WS-JF-004", "WS-JF-005", "WS-JF-006"})


class RosterPerson(BaseModel):
    person_id: NonBlankStr  # review-01 R11: a flag must name someone identifiable
    display_name: NonBlankStr
    role: NonBlankStr
    primary: bool = False
    notional: StrictBool  # Session 10: "yes" must not coerce to True

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


def _is_hot_work(p: WorkPackageState) -> bool:
    return HazardCategory.HOT_WORK in _hazards(p) or p.permits_required.hot_work_permit


def _is_confined(p: WorkPackageState) -> bool:
    return (HazardCategory.CONFINED_SPACE in _hazards(p)
            or p.spatial.is_enclosed_or_confined
            or p.permits_required.confined_space_entry_permit)


def _is_gas_free(p: WorkPackageState) -> bool:
    return _is_hot_work(p) or _is_confined(p)


def _has_frames(p: WorkPackageState) -> bool:
    return p.spatial.frame_start is not None and p.spatial.frame_end is not None


def _located(p: WorkPackageState) -> bool:
    return bool(p.spatial.compartment_id) or _has_frames(p)


def _comparable(a: WorkPackageState, b: WorkPackageState) -> bool:
    """True if the two share at least one coordinate system to compare positions in."""
    both_compartment = bool(a.spatial.compartment_id) and bool(b.spatial.compartment_id)
    return both_compartment or (_has_frames(a) and _has_frames(b))


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
        # review-01 R12: JSON-encode the ID list so "A+B","C" and "A","B+C" differ.
        flag_id=f"{rule.rule_id}:{json.dumps(ids, separators=(',', ':'))}",
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
    catalogue = {r.rule_id for r in named_rules.RULES if r.category == RuleCategory.JUDGMENT}
    if catalogue != IMPLEMENTED_TRIGGERS:
        raise LookupError(
            "judgment catalogue and implemented triggers differ: "
            f"in catalogue only {sorted(catalogue - IMPLEMENTED_TRIGGERS)}, "
            f"implemented only {sorted(IMPLEMENTED_TRIGGERS - catalogue)}"
        )
    for r in named_rules.RULES:
        if r.category == RuleCategory.JUDGMENT:
            roster.primary_for(r.contact_role)  # fail before producing anything

    pkgs = sorted(packages, key=lambda p: p.work_package_id)
    ids = [p.work_package_id for p in pkgs]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate work_package_id in batch: {dupes}")

    rule = {i: named_rules.get_rule(i) for i in IMPLEMENTED_TRIGGERS}
    flags: list[JudgmentFlag] = []

    for a, b in combinations(pkgs, 2):
        if not _schedules_overlap(a, b):
            continue
        pair = [a.work_package_id, b.work_package_id]
        hot_and_cs = (_is_hot_work(a) and _is_confined(b)) or (_is_hot_work(b) and _is_confined(a))
        both_cs = _is_confined(a) and _is_confined(b)

        gap = _frame_gap(a, b)
        if hot_and_cs and gap is not None and gap <= JUDGMENT_ADJACENCY_FRAMES and check_conflict(a, b) is None:
            flags.append(_flag(rule["WS-JF-001"], pair,
                               f"hot work and confined space are {gap} frame(s) apart and concurrent; "
                               "detection does not flag adjacency.", roster))

        if both_cs and (_same_compartment(a, b) or _frame_ranges_overlap(a, b)):
            flags.append(_flag(rule["WS-JF-002"], pair,
                               "two confined-space entries share a space at the same time.", roster))

        if (hot_and_cs or both_cs) and _located(a) and _located(b) and not _comparable(a, b):
            flags.append(_flag(rule["WS-JF-004"], pair,
                               "one is located only by compartment and the other only by frames, "
                               "so their positions can't be compared.", roster))

    for p in pkgs:
        if _is_gas_free(p) and not _located(p):
            flags.append(_flag(rule["WS-JF-003"], [p.work_package_id],
                               "no compartment and no complete frame range, so it cannot be "
                               "spatially deconflicted.", roster))
        if is_overhead(p) and not _has_frames(p):
            flags.append(_flag(rule["WS-JF-006"], [p.work_package_id],
                               "overhead work with no complete frame range, so work below it "
                               "can't be detected.", roster))
        missing = []
        if _is_hot_work(p) and HazardCategory.HOT_WORK not in _hazards(p):
            missing.append("hot_work")
        if _is_confined(p) and HazardCategory.CONFINED_SPACE not in _hazards(p):
            missing.append("confined_space")
        if missing:
            flags.append(_flag(rule["WS-JF-005"], [p.work_package_id],
                               f"permit or spatial flag indicates {', '.join(missing)} but the hazard "
                               "list omits it, so conflict detection cannot see it.", roster))

    return sorted(flags, key=lambda f: f.flag_id)


def judgment_node(state: dict) -> dict:
    """
    review-03 S08-04: graph step between detection and reasoning. Every package named
    by a judgment flag (any WS-JF rule) is routed to human review, with the rule, the
    reason, and the person it routes to recorded in its rationale, so it reaches the
    HITL gate and gets a brief. Before this, judgment flags were only computed inside
    the shift suggester, so a standalone flag (e.g. unlocated overhead work) reached
    nobody. Fails closed: a flagged package is never left cleared.
    """
    packages = state["work_packages"]
    flags = judgment_flags(packages)
    by_id = {p.work_package_id: p for p in packages}
    for f in flags:
        note = (f"Judgment flag {f.rule_id}: {f.reason} Route to {f.routed_to.role} "
                f"{f.routed_to.display_name} ({f.routed_to.person_id}).")
        for pid in f.work_package_ids:
            wp = by_id[pid]
            wp.requires_hitl_review = True
            wp.cleared_for_execution = False
            if not wp.conflict_rationale:
                wp.conflict_rationale = note
            elif note not in wp.conflict_rationale:
                wp.conflict_rationale = f"{wp.conflict_rationale} | {note}"
    return {
        "work_packages": packages,
        "requires_hitl_review": bool(state.get("requires_hitl_review")) or bool(flags),
    }
