"""
Fixed evaluation scenarios for Watchstander's core deterministic pipeline.

Every scenario here is hand-authored, not generated or sampled, and every
one is checked into git so the suite itself has a diff history. Each
`ConflictScenario` documents not just what the code *does* today but
whether that's domain-correct -- the `correct` field is `False` on
scenarios that reproduce a known, already-documented gap (see
ARCHITECTURE.md's Known Debt table and the 2026-07-25 external review),
so the eval report can say plainly "here are N scenarios where the system
gets the right answer, and M scenarios where it currently doesn't, and
here specifically is why."

Categories used below:
  - true_positive             a real conflict, correctly flagged
  - true_negative              no real conflict, correctly not flagged
  - boundary                   an edge case in the overlap math, correctly handled
  - known_gap_false_negative   a real conflict the code currently misses
  - flagged_rationale_wrong    correctly flagged, but the human-facing
                               rationale text describes the geometry backwards
  - debatable_false_positive   flagged by the current hazard-pair table, but
                               the pair itself is domain-questionable (flags
                               a compliant configuration, not a real hazard)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from agent_core.state import HazardCategory, SpatialCoordinates, WorkPackageState


def _wp(
    work_package_id: str,
    hazards: list[HazardCategory],
    frame_start: Optional[int] = None,
    frame_end: Optional[int] = None,
    compartment_id: Optional[str] = None,
    deck_level: Optional[str] = None,
    is_aloft: bool = False,
    is_over_side: bool = False,
    is_enclosed_or_confined: bool = False,
    description: Optional[str] = None,
) -> WorkPackageState:
    return WorkPackageState(
        work_package_id=work_package_id,
        description=description or work_package_id,
        hazard_categories=hazards,
        spatial=SpatialCoordinates(
            frame_start=frame_start,
            frame_end=frame_end,
            compartment_id=compartment_id,
            deck_level=deck_level,
            is_aloft=is_aloft,
            is_over_side=is_over_side,
            is_enclosed_or_confined=is_enclosed_or_confined,
        ),
    )


@dataclass
class ConflictScenario:
    id: str
    category: str
    description: str
    packages: list[WorkPackageState]
    # The work_package_id pair the scenario is actually testing.
    pair: tuple[str, str]
    # Whether the CURRENT implementation is expected to flag `pair` as
    # conflicting. This is a behavioral assertion -- if this stops
    # matching the live code, the harness has caught a change.
    expected_conflict: bool
    # Whether `expected_conflict` is the domain-correct answer. False
    # means this scenario documents a known gap or a debatable rule, not
    # a bug in the harness.
    correct: bool
    notes: str
    # Optional callable(rationale_str) -> bool, checked only when
    # expected_conflict is True and a rationale exists. Used to pin
    # down the is_over_side mislabeling as a measured property instead
    # of prose.
    rationale_check: Optional[Callable[[str], bool]] = None


CONFLICT_SCENARIOS: list[ConflictScenario] = [
    # ---- true positives: real conflicts, correctly detected ----------
    ConflictScenario(
        id="tp-hotwork-confined-same-compartment",
        category="true_positive",
        description="Hot work and confined-space entry in the same compartment, overlapping frames.",
        packages=[
            _wp("WP-01A", [HazardCategory.HOT_WORK], 100, 110, compartment_id="FR-100-2-A"),
            _wp("WP-01B", [HazardCategory.CONFINED_SPACE], 102, 108, compartment_id="FR-100-2-A"),
        ],
        pair=("WP-01A", "WP-01B"),
        expected_conflict=True,
        correct=True,
        notes="Textbook incompatible-pair + same-compartment case; this is the pipeline's core job.",
    ),
    ConflictScenario(
        id="tp-hotwork-aloft-vertically-stacked",
        category="true_positive",
        description="Hot work directly below aloft staging, overlapping frame range, different compartments.",
        packages=[
            _wp("WP-02A", [HazardCategory.HOT_WORK], 200, 210, compartment_id="2ND-DECK-FR200"),
            _wp(
                "WP-02B",
                [HazardCategory.WORKING_ALOFT],
                204,
                208,
                compartment_id="MAIN-DECK-FR204",
                is_aloft=True,
            ),
        ],
        pair=("WP-02A", "WP-02B"),
        expected_conflict=True,
        correct=True,
        notes="The motivating scenario from the module's own docstring: caught via the "
        "HOT_WORK/WORKING_ALOFT hazard pair, reinforced by vertical-stacking logic.",
    ),
    ConflictScenario(
        id="tp-frame-overlap-different-compartments",
        category="true_positive",
        description="Incompatible hazard pair, overlapping frames, but different named compartments.",
        packages=[
            _wp("WP-03A", [HazardCategory.HOT_WORK], 50, 60, compartment_id="VOID-A"),
            _wp("WP-03B", [HazardCategory.CONFINED_SPACE], 55, 65, compartment_id="VOID-B"),
        ],
        pair=("WP-03A", "WP-03B"),
        expected_conflict=True,
        correct=True,
        notes="Frame overlap alone is sufficient to link two packages spatially even without "
        "a shared compartment_id -- confirms _same_compartment isn't required.",
    ),
    ConflictScenario(
        id="tp-over-side-vertically-stacked",
        category="true_positive",
        description="Over-the-side staging overlapping frames with non-overhead work below the waterline work area.",
        packages=[
            _wp("WP-04A", [HazardCategory.OVER_THE_SIDE], 300, 310, is_over_side=True),
            _wp("WP-04B", [HazardCategory.FALL_PROTECTION], 302, 306),
        ],
        pair=("WP-04A", "WP-04B"),
        expected_conflict=True,
        correct=True,
        notes="Caught by _vertically_stacked because is_over_side counts as 'overhead' in the "
        "current model, regardless of the rationale-wording issue tracked separately below.",
    ),
    ConflictScenario(
        id="tp-boundary-touching-frames",
        category="boundary",
        description="Frame ranges that touch at exactly one frame (A ends where B starts), not overlap.",
        packages=[
            _wp("WP-05A", [HazardCategory.HOT_WORK], 10, 20, compartment_id="X"),
            _wp("WP-05B", [HazardCategory.CONFINED_SPACE], 20, 30, compartment_id="Y"),
        ],
        pair=("WP-05A", "WP-05B"),
        expected_conflict=True,
        correct=True,
        notes="_frame_ranges_overlap uses <=/>=, so boundary-touching frames count as overlapping. "
        "Conservative and correct: two jobs sharing frame 20 are not spatially separate.",
    ),
    # ---- true negatives: no real conflict, correctly not flagged ------
    ConflictScenario(
        id="tn-unrelated-hazards-non-overlapping",
        category="true_negative",
        description="Unrelated hazard categories, non-overlapping frames, different compartments.",
        packages=[
            _wp("WP-06A", [HazardCategory.HOT_WORK], 1, 10, compartment_id="A"),
            _wp("WP-06B", [HazardCategory.CONFINED_SPACE], 500, 510, compartment_id="B"),
        ],
        pair=("WP-06A", "WP-06B"),
        expected_conflict=False,
        correct=True,
        notes="No spatial link, so the hazard pair never gets a chance to matter. Baseline sanity check.",
    ),
    ConflictScenario(
        id="tn-incompatible-pair-but-not-linked",
        category="true_negative",
        description="Incompatible hazard pair, but no compartment match and no frame overlap.",
        packages=[
            _wp("WP-07A", [HazardCategory.HOT_WORK], 1, 5, compartment_id="A"),
            _wp("WP-07B", [HazardCategory.CONFINED_SPACE], 900, 905, compartment_id="B"),
        ],
        pair=("WP-07A", "WP-07B"),
        expected_conflict=False,
        correct=True,
        notes="Confirms the hazard-pair check is gated on spatial linkage, not evaluated alone.",
    ),
    ConflictScenario(
        id="tn-missing-frame-data-different-compartments",
        category="true_negative",
        description="Both packages have no frame data at all, and no shared compartment.",
        packages=[
            _wp("WP-08A", [HazardCategory.HOT_WORK], compartment_id="A"),
            _wp("WP-08B", [HazardCategory.CONFINED_SPACE], compartment_id="B"),
        ],
        pair=("WP-08A", "WP-08B"),
        expected_conflict=False,
        correct=True,
        notes="_frame_ranges_overlap returns False whenever any of the four values is None -- "
        "confirms incomplete spatial data doesn't get treated as an overlap by default.",
    ),
    # ---- known gaps: real conflicts the code currently misses ---------
    ConflictScenario(
        id="gap-adjacent-frames-not-touching",
        category="known_gap_false_negative",
        description="Hot work one frame away (not touching) from an uncleared confined space -- "
        "the exact scenario INCOMPATIBLE_HAZARD_PAIRS's own comment cites as motivating.",
        packages=[
            _wp("WP-09A", [HazardCategory.HOT_WORK], 100, 110, compartment_id="A"),
            _wp("WP-09B", [HazardCategory.CONFINED_SPACE], 112, 120, compartment_id="B"),
        ],
        pair=("WP-09A", "WP-09B"),
        expected_conflict=False,
        correct=False,
        notes="ARCHITECTURE.md Known Debt: 'No adjacency tolerance on frame ranges.' Frame 110 "
        "and frame 112 are one frame apart -- a real shipyard safety officer would still care -- "
        "but _frame_ranges_overlap requires literal intersection, so this is a false negative today.",
    ),
    ConflictScenario(
        id="gap-two-aloft-packages-stacked",
        category="known_gap_false_negative",
        description="Two aloft work packages occupying the same frame range (one physically above "
        "the other), which _vertically_stacked cannot distinguish because deck_level is unused.",
        packages=[
            _wp(
                "WP-10A",
                [HazardCategory.WORKING_ALOFT],
                400,
                410,
                deck_level="01 Level",
                is_aloft=True,
            ),
            _wp(
                "WP-10B",
                [HazardCategory.WORKING_ALOFT],
                400,
                410,
                deck_level="02 Level",
                is_aloft=True,
            ),
        ],
        pair=("WP-10A", "WP-10B"),
        expected_conflict=False,
        correct=False,
        notes="ARCHITECTURE.md Known Debt: 'deck_level collected, never used.' _vertically_stacked "
        "line `a_overhead == b_overhead` returns False whenever both packages are aloft, so two "
        "aloft crews stacked on top of each other -- a real fall/struck-by risk -- go unflagged. "
        "Same hazard category also means INCOMPATIBLE_HAZARD_PAIRS never applies (no pair of two "
        "distinct categories to match), so neither branch of check_conflict catches this today.",
    ),
    ConflictScenario(
        id="gap-simultaneous-confined-space-entries",
        category="known_gap_false_negative",
        description="Two separate confined-space entries in the same compartment at the same time -- "
        "a same-category pair, which INCOMPATIBLE_HAZARD_PAIRS cannot represent (it only pairs two "
        "distinct categories).",
        packages=[
            _wp("WP-11A", [HazardCategory.CONFINED_SPACE], 60, 70, compartment_id="TANK-4"),
            _wp("WP-11B", [HazardCategory.CONFINED_SPACE], 62, 68, compartment_id="TANK-4"),
        ],
        pair=("WP-11A", "WP-11B"),
        expected_conflict=False,
        correct=False,
        notes="Fable review: 'CONFINED_SPACE/CONFINED_SPACE (multiple simultaneous entries sharing "
        "an atmosphere)' is a plausible real pair absent from INCOMPATIBLE_HAZARD_PAIRS, which is "
        "defined as a set of two-element frozensets and structurally cannot express a same-category "
        "rule. Two entrants sharing one atmosphere without knowing about each other is a real hazard.",
    ),
    # ---- flagged correctly, but the rationale text is domain-backwards
    ConflictScenario(
        id="rationale-over-side-labeled-overhead",
        category="flagged_rationale_wrong",
        description="Over-the-side staging is described as 'Overhead work' in the generated "
        "rationale, which is geometrically backwards -- over-the-side hangs below the deck edge.",
        packages=[
            _wp("WP-12A", [HazardCategory.OVER_THE_SIDE], 250, 260, is_over_side=True),
            _wp("WP-12B", [HazardCategory.FALL_PROTECTION], 252, 256),
        ],
        pair=("WP-12A", "WP-12B"),
        expected_conflict=True,
        correct=True,  # the conflict itself is correctly (conservatively) flagged
        notes="ARCHITECTURE.md / Fable review: is_over_side is modeled identically to is_aloft as "
        "the 'overhead' party in _vertically_stacked, so the rationale string calls WP-12A "
        "'Overhead work' when it is in fact staged below the deck edge, over water. The conflict "
        "gets flagged (conservative, good); the human-facing explanation of *why* is wrong "
        "(rationale_check below pins this down as a measured property, not just prose).",
        rationale_check=lambda text: "Overhead work (WP-12A)" in text,
    ),
    # ---- debatable rule: flags a configuration that may be compliant --
    ConflictScenario(
        id="debatable-aloft-fall-protection-compliant-config",
        category="debatable_false_positive",
        description="Working aloft directly alongside a fall-protection work package in the same "
        "envelope -- which may just mean the aloft crew IS using fall protection, the compliant "
        "configuration under 29 CFR 1915.159/.77, not a hazard pair.",
        packages=[
            _wp(
                "WP-13A",
                [HazardCategory.WORKING_ALOFT],
                150,
                160,
                compartment_id="MAST-1",
                is_aloft=True,
            ),
            _wp("WP-13B", [HazardCategory.FALL_PROTECTION], 152, 158, compartment_id="MAST-1"),
        ],
        pair=("WP-13A", "WP-13B"),
        expected_conflict=True,
        correct=False,
        notes="Fable review: '{WORKING_ALOFT, FALL_PROTECTION} is odd: working aloft *requires* "
        "fall protection ... a fall-protection work package near aloft work is the compliant "
        "configuration, not an incompatibility.' Flagged today by INCOMPATIBLE_HAZARD_PAIRS; "
        "marked incorrect here because what actually needs catching is aloft work above "
        "*unprotected* personnel, which is a different rule than 'these two categories co-occur.'",
    ),
    # ---- multi-conflict: one package conflicting with more than one ---
    ConflictScenario(
        id="tp-multi-conflict-single-package",
        category="true_positive",
        description="One hot-work package overlapping both a confined-space package and an "
        "aloft package in the same frame range -- confirms conflicts accumulate, not overwrite.",
        packages=[
            _wp("WP-14A", [HazardCategory.HOT_WORK], 700, 710, compartment_id="C1"),
            _wp("WP-14B", [HazardCategory.CONFINED_SPACE], 702, 706, compartment_id="C1"),
            _wp("WP-14C", [HazardCategory.WORKING_ALOFT], 703, 705, is_aloft=True),
        ],
        pair=("WP-14A", "WP-14B"),
        expected_conflict=True,
        correct=True,
        notes="Primary pair asserted here; run_eval.py additionally checks WP-14A also conflicts "
        "with WP-14C and that WP-14A.conflicts ends up with length 2, not 1.",
    ),
]


@dataclass
class RetrievalScenario:
    id: str
    description: str
    query: str
    hazards: list[HazardCategory]
    expected_case_id: str
    notes: str


# Retrieval scenarios exercise agent_core/retrieval.py's TF-IDF ranking
# against the real, checked-in case_data/cases_v1.json -- no synthetic
# case data. fall_protection has three candidate cases on file
# (FALL-DETYENS-2024, STRUCK-DETYENS-2020, PATTERN-DETYENS-2015), which
# is exactly the "real choice to make" scenario the module's own
# docstring says TF-IDF ranking exists for.
RETRIEVAL_SCENARIOS: list[RetrievalScenario] = [
    RetrievalScenario(
        id="retrieval-confined-space-single-candidate",
        description="Only one confined_space case on file -- should return it regardless of "
        "query wording, confirming the single-candidate path works.",
        query="welder overcome oxygen deficiency hull space",
        hazards=[HazardCategory.CONFINED_SPACE],
        expected_case_id="CS-2023-STJOHNS",
        notes="Sanity check: no ranking decision to make when there's exactly one candidate.",
    ),
    RetrievalScenario(
        id="retrieval-hotwork-two-candidates-explosion",
        description="Two hot_work cases on file; query text should pull the explosion/fatality "
        "case, not the fire/no-fatality one.",
        query="explosion welding cutting flammable gas atmosphere fatalities confined space not tested",
        hazards=[HazardCategory.HOT_WORK],
        expected_case_id="HW-FIRSTMARINE",
        notes="Confirms ranking distinguishes between two same-category cases based on query "
        "term overlap, not just 'first case in the file.'",
    ),
    RetrievalScenario(
        id="retrieval-hotwork-two-candidates-fire",
        description="Same two hot_work candidates, query text pointed at the other one instead.",
        query="fire welding paint removal cargo hold competent person marine chemist certificate",
        hazards=[HazardCategory.HOT_WORK],
        expected_case_id="HW-ASHTABULA-2024",
        notes="Paired with the scenario above -- together they prove the ranking actually moves "
        "with the query rather than returning a fixed case for the category.",
    ),
    RetrievalScenario(
        id="retrieval-fall-protection-three-candidates-fall",
        description="Three fall_protection cases on file; query text should select the unguarded "
        "platform fall, not the struck-by or the pattern-of-noncompliance case.",
        query="fell from unguarded platform edge gas tank ladder no guardrails inadequate lighting",
        hazards=[HazardCategory.FALL_PROTECTION],
        expected_case_id="FALL-DETYENS-2024",
        notes="The three-candidate case the retrieval.py docstring specifically calls out as the "
        "motivation for TF-IDF ranking over 'always cite the first one.'",
    ),
    RetrievalScenario(
        id="retrieval-fall-protection-three-candidates-struck",
        description="Same three fall_protection candidates, query text pointed at the lifting/"
        "struck-by incident instead.",
        query="struck by shackle lifting operation rudder shaft caught between guardrail",
        hazards=[HazardCategory.FALL_PROTECTION],
        expected_case_id="STRUCK-DETYENS-2020",
        notes="Confirms the three-candidate ranking correctly separates a struck-by case from a "
        "fall case even though both are filed under the same fall_protection hazard_category.",
    ),
    RetrievalScenario(
        id="retrieval-fall-protection-three-candidates-pattern",
        description="Same three fall_protection candidates, query pointed at the systemic "
        "noncompliance case rather than a single incident.",
        query="regional emphasis program maritime inspection repeated serious citations electrical "
        "amputation systemic noncompliance",
        hazards=[HazardCategory.FALL_PROTECTION],
        expected_case_id="PATTERN-DETYENS-2015",
        notes="Third leg of the three-candidate check -- all three fall_protection cases are each "
        "correctly retrievable by their own distinguishing language.",
    ),
    RetrievalScenario(
        id="retrieval-no-signal-falls-back-to-first",
        description="Empty query string against the three-candidate fall_protection category.",
        query="",
        hazards=[HazardCategory.FALL_PROTECTION],
        expected_case_id="FALL-DETYENS-2024",
        notes="retrieval.py's documented fallback: an empty/no-signal query returns the first "
        "sourced case for the hazard rather than an arbitrary or unstable ranking. Pins that "
        "contract down as a measured behavior, not just a docstring claim.",
    ),
]
