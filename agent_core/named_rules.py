"""
Named rules: a stable ID, citations, and who to call for everything the
deterministic engine checks.

Detection lives in `deconfliction.py` and `certificates.py`; this module
never decides anything. It is a catalogue those modules (and later the
brief and reviewer) look findings up in, so a finding can say "WS-HZ-001,
29 CFR 1915.14, call the Gas Free Engineer" instead of free text only.

Loaded from `case_data/named_rules_v1.json` and validated on import:
duplicate or malformed IDs, unknown hazard categories or certificate kinds,
a blank contact role, or an unexpected schema version all refuse to load,
the same fail-loud posture as `rules_config.load_hazard_rules()`.
Completeness (every hazard pair and certificate kind has exactly one
rule) is enforced by tests against the live detection constants, not
re-derived here, so this module needs no import of the detection code.

Contacts are roles, never named people (notional-data rule). A citation's
`verified` flag follows `navsea_8010_psns_v2014.json`: true only when
someone read the primary source for that entry.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from agent_core.state import HazardCategory, SafetyPermitsRequired

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "case_data" / "named_rules_v1.json"
SCHEMA_VERSION = 1


class RuleCategory(str, Enum):
    HAZARD_PAIR = "hazard_pair"
    OVERHEAD = "overhead"
    FIRE_WATCH = "fire_watch"
    CERTIFICATE = "certificate"


class Citation(BaseModel):
    source: str = Field(min_length=1)
    verified: bool = False


class NamedRule(BaseModel):
    rule_id: str = Field(pattern=r"^WS-[A-Z]{2}-\d{3}$")
    title: str = Field(min_length=1)
    category: RuleCategory
    applies_to: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    contact_role: str
    escalation_role: Optional[str] = None
    note: Optional[str] = None

    @field_validator("contact_role")
    @classmethod
    def _contact_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("contact_role must not be blank")
        return v

    @model_validator(mode="after")
    def _applies_to_matches_category(self) -> "NamedRule":
        if self.category == RuleCategory.HAZARD_PAIR:
            valid = {c.value for c in HazardCategory}
            if len(self.applies_to) != 2 or self.applies_to[0] == self.applies_to[1]:
                raise ValueError(f"{self.rule_id}: hazard_pair needs exactly 2 distinct categories")
            unknown = [h for h in self.applies_to if h not in valid]
            if unknown:
                raise ValueError(f"{self.rule_id}: unknown hazard categories {unknown}")
        elif self.category == RuleCategory.CERTIFICATE:
            valid = set(SafetyPermitsRequired.model_fields)
            if len(self.applies_to) != 1:
                raise ValueError(f"{self.rule_id}: certificate rule needs exactly 1 kind")
            if self.applies_to[0] not in valid:
                raise ValueError(f"{self.rule_id}: unknown certificate kind {self.applies_to[0]!r}")
        elif self.applies_to:
            raise ValueError(f"{self.rule_id}: {self.category.value} rules take no applies_to")
        if not self.citations and not (self.note and self.note.strip()):
            raise ValueError(f"{self.rule_id}: an uncited rule must carry a note saying why")
        return self


def load_named_rules(path: Optional[Path] = None) -> list[NamedRule]:
    with open(path or _DEFAULT_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"named rules schema_version {raw.get('schema_version')!r} != {SCHEMA_VERSION}"
        )
    rules = [NamedRule(**r) for r in raw["rules"]]
    seen: set[str] = set()
    for r in rules:
        if r.rule_id in seen:
            raise ValueError(f"duplicate rule_id: {r.rule_id}")
        seen.add(r.rule_id)
    return rules


RULES: list[NamedRule] = load_named_rules()
RULES_BY_ID: dict[str, NamedRule] = {r.rule_id: r for r in RULES}


def _only(category: RuleCategory, applies_to: Optional[frozenset[str]] = None) -> NamedRule:
    matches = [
        r for r in RULES
        if r.category == category
        and (applies_to is None or frozenset(r.applies_to) == applies_to)
    ]
    if len(matches) != 1:
        raise KeyError(
            f"expected exactly one {category.value} rule for {sorted(applies_to or [])}, "
            f"found {len(matches)}"
        )
    return matches[0]


def get_rule(rule_id: str) -> NamedRule:
    return RULES_BY_ID[rule_id]


def rule_for_hazard_pair(pair: frozenset[HazardCategory]) -> NamedRule:
    return _only(RuleCategory.HAZARD_PAIR, frozenset(HazardCategory(h).value for h in pair))


def rule_for_overhead_work() -> NamedRule:
    return _only(RuleCategory.OVERHEAD)


def rule_for_fire_watch_capacity() -> NamedRule:
    return _only(RuleCategory.FIRE_WATCH)


def rule_for_certificate_kind(kind) -> NamedRule:
    value = kind.value if hasattr(kind, "value") else str(kind)
    return _only(RuleCategory.CERTIFICATE, frozenset({value}))
