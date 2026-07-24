"""
Case-data lookup for grounding conflict rationale in real precedent.

Loads case_data/cases_v1.json once and provides lookup by hazard
category so a flagged conflict can cite a real, sourced case instead
of a bare rule reference. Pure lookup -- no LLM call, keeps Phase 1
deterministic and testable per MIGRATION.md.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from agent_core.state import HazardCategory

_CASE_DATA_PATH = Path(__file__).resolve().parent.parent / "case_data" / "cases_v1.json"


@lru_cache(maxsize=1)
def _load_cases() -> list[dict]:
    with open(_CASE_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


def cases_for_hazard(hazard: HazardCategory | str) -> list[dict]:
    """Returns all sourced cases tagged with the given hazard category."""
    hazard_value = hazard.value if isinstance(hazard, HazardCategory) else hazard
    return [c for c in _load_cases() if c["hazard_category"] == hazard_value]


def cite_case(hazard: HazardCategory | str) -> str | None:
    """
    Returns a short, human-readable citation for the first sourced case
    matching the given hazard category, or None if no case is on file
    for that category yet (expected -- case_data is still being built
    out per MIGRATION.md Phase 4).
    """
    matches = cases_for_hazard(hazard)
    if not matches:
        return None
    case = matches[0]
    return (
        f"Precedent: {case['case_id']} ({case['shipyard']}) -- {case['summary']} "
        f"Root cause: {case['root_cause']} [{case['osha_subpart']}]"
    )


def cite_best_case(hazards: list[HazardCategory | str]) -> str | None:
    """
    Given multiple hazard categories involved in a flagged conflict,
    returns a citation for the first one that has a sourced case on
    file. Returns None if none of the given hazards have a case yet.
    """
    for hazard in hazards:
        citation = cite_case(hazard)
        if citation:
            return citation
    return None