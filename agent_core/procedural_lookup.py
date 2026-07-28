"""
Governing-procedure lookup for grounding conflict rationale in the actual
Navy/command instruction that applies at a given installation -- distinct
from `case_lookup.py`'s OSHA/DOL incident precedent.

Site-scoped by design: a work package's `governing_installation` field
selects which ruleset file to consult (see `_RULESET_FILES` below). This
is deliberately not a universal Navy-wide rules engine -- different
installations and type commands (NASNI, NAVSTA Everett, SURFPAC vs AIRPAC
vs AIRLANT, etc.) operate under different governing instructions, and
nothing here assumes PSNS's ruleset applies anywhere else. Adding a new
site means adding a new ruleset file and a new `_RULESET_FILES` entry, not
changing this module's logic. A work package with no
`governing_installation` set gets no procedural citation at all --
silently assuming a default site would be exactly the kind of
unverified claim this project's documentation culture argues against.

Only `hot_work` has any entries in the PSNS ruleset as of this writing --
the NAVSEA 8010 Manual this is sourced from covers fire prevention only,
not confined_space/working_aloft/fall_protection/over_the_side. Pure
lookup -- no LLM call, same discipline as case_lookup.py.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from agent_core.state import HazardCategory

_CASE_DATA_DIR = Path(__file__).resolve().parent.parent / "case_data"

# Maps a governing_installation value to its ruleset file. Add a new
# installation by adding a new sourced, versioned JSON file under
# case_data/ (same shape as navsea_8010_psns_v2014.json) and a new entry
# here -- do not point two installations at the same file just because no
# second ruleset exists yet.
_RULESET_FILES: dict[str, str] = {
    "PSNS": "navsea_8010_psns_v2014.json",
}


@lru_cache(maxsize=None)
def _load_ruleset(installation: str) -> dict | None:
    filename = _RULESET_FILES.get(installation)
    if filename is None:
        return None
    path = _CASE_DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def procedures_for_hazard(
    installation: str, hazard: HazardCategory | str
) -> list[dict]:
    """
    Returns all governing-procedure entries tagged with the given hazard
    category for the given installation's ruleset. Empty list if the
    installation has no ruleset on file, or the ruleset has no entries
    for that hazard category (expected for most hazard/installation
    combinations -- rulesets are added incrementally, per-source, the
    same way case_data is).
    """
    ruleset = _load_ruleset(installation)
    if ruleset is None:
        return []
    hazard_value = hazard.value if isinstance(hazard, HazardCategory) else hazard
    return [p for p in ruleset["procedures"] if p["hazard_category"] == hazard_value]


def cite_governing_procedure(
    installation: str | None, hazards: list[HazardCategory | str]
) -> str | None:
    """
    Returns a short, human-readable citation for the first governing
    procedure matching any of the given hazard categories at the given
    installation, or None if `installation` is unset, has no ruleset on
    file, or the ruleset has no entry for any of the given hazards.

    An entry's `verified=false` is surfaced directly in the citation
    text -- see navsea_8010_psns_v2014.json's `verification_note`: these
    were extracted from document structure, not confirmed verbatim
    against the primary-source PDF for exact numeric/procedural
    specifics, and a reviewer reading this citation must be able to see
    that at a glance, not have it silently presented as a confirmed
    exact requirement.
    """
    if not installation:
        return None
    for hazard in hazards:
        matches = procedures_for_hazard(installation, hazard)
        if matches:
            proc = matches[0]
            caveat = (
                " [UNVERIFIED: extracted from document structure, not confirmed "
                "verbatim against primary source -- treat as pointer to the "
                "governing section, not a citable exact requirement]"
                if not proc.get("verified", True)
                else ""
            )
            return (
                f"Governing procedure ({installation}): {proc['section']} -- "
                f"{proc['summary']}{caveat}"
            )
    return None
