"""
Declarative hazard rules — data, not code, and every load is auditable.

`deconfliction.py`'s hazard-pair rules and fire-watch capacity limit used
to live as Python constants in the module that also enforces them --
correct, but not editable by anyone who isn't a Python-literate reviewer
of that module's diff.

They now live in `case_data/hazard_rules_v1.json`, validated against a real
schema (`HazardRuleSet`) on load -- an unrecognized hazard category name, a
pair that isn't exactly two distinct categories, or a non-positive limit
fails loudly at import time, not silently at the first flagged conflict.
`deconfliction.py` still exposes `INCOMPATIBLE_HAZARD_PAIRS` and
`MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH` as module-level names -- every
existing import and test keeps working unchanged -- but their values now
come from this loader instead of being hand-typed twice.

Grounded, never invented (the same principle `reasoning.py`'s
`_grounding_context()` already enforces elsewhere): every rule in the
checked-in file carries `source_citation`, and nothing in this module ever
fabricates a rule that isn't in the file. A future rule-editing GUI, not yet built, is
expected to call `rules_audit.record_rule_change()` (see that module) for
every edit it makes -- this loader itself only reads, it never writes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from agent_core.state import HazardCategory

_DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "case_data" / "hazard_rules_v1.json"


class HazardRuleSet(BaseModel):
    """
    Validated in-memory form of a hazard-rules config file.

    `incompatible_hazard_pairs` is kept as the raw list-of-2-lists shape
    from the JSON (schema-friendly, diff-friendly, easy for a future
    non-Python editor to hand-edit) -- `as_pair_set()` below converts it
    to the `frozenset[HazardCategory]` shape `deconfliction.py` actually
    consumes. Keeping the two representations separate means the on-disk
    schema never has to match the in-memory data structure the detection
    code happens to want today.
    """

    schema_version: int
    incompatible_hazard_pairs: list[list[str]]
    max_concurrent_hot_workers_per_fire_watch: int = Field(ge=1)
    source_citation: str

    @model_validator(mode="after")
    def _pairs_are_well_formed(self) -> "HazardRuleSet":
        valid_categories = {c.value for c in HazardCategory}
        for pair in self.incompatible_hazard_pairs:
            if len(pair) != 2:
                raise ValueError(
                    f"incompatible_hazard_pairs entry {pair!r} must have exactly 2 "
                    "hazard categories, not a self-pair or an N-way group"
                )
            if pair[0] == pair[1]:
                raise ValueError(
                    f"incompatible_hazard_pairs entry {pair!r} pairs a hazard category "
                    "with itself -- not a meaningful conflict rule"
                )
            unknown = [h for h in pair if h not in valid_categories]
            if unknown:
                raise ValueError(
                    f"incompatible_hazard_pairs entry {pair!r} references unknown hazard "
                    f"categor{'y' if len(unknown) == 1 else 'ies'} {unknown!r} -- must be one "
                    f"of {sorted(valid_categories)}. A rule referencing a category that "
                    "doesn't exist would silently never match anything, which is a worse "
                    "failure than refusing to load"
                )
        return self

    def as_pair_set(self) -> set[frozenset[HazardCategory]]:
        """The `deconfliction.py`-native shape: a set of 2-element frozensets."""
        return {
            frozenset({HazardCategory(pair[0]), HazardCategory(pair[1])})
            for pair in self.incompatible_hazard_pairs
        }


def load_hazard_rules(path: Optional[Path] = None) -> HazardRuleSet:
    """
    Loads and validates the hazard rules config. Defaults to the checked-in
    `case_data/hazard_rules_v1.json`. Raises (does not silently fall back
    to a hardcoded default) on a missing file or a schema violation --
    a safety-rule config that fails to load must stop the program, not
    quietly run with a guessed or partial ruleset.
    """
    rules_path = path or _DEFAULT_RULES_PATH
    with open(rules_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return HazardRuleSet(**raw)
