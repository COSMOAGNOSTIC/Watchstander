"""
Spatial & temporal deconfliction logic.

Pure, deterministic overlap detection lives here (no LLM call needed
for the mechanical geometry check — that's what makes conflicts
auditable and testable). An LLM reasoning layer can sit on top of
this to explain *why* a flagged overlap matters, citing the case
data in /case_data, but the detection itself should not depend on
a model call to be correct or repeatable.
"""

from __future__ import annotations

from itertools import combinations

from agent_core import events
from agent_core.state import HazardCategory, WorkPackageState

# Hazard category pairs that are unsafe to run concurrently in
# overlapping/adjacent spatial envelopes. Sourced from OSHA 1915
# Subpart D (hot work) and Subpart B (confined/enclosed spaces) --
# e.g. hot work in a space can ignite an adjacent, uncleared space.
INCOMPATIBLE_HAZARD_PAIRS: set[frozenset[HazardCategory]] = {
    frozenset({HazardCategory.HOT_WORK, HazardCategory.CONFINED_SPACE}),
    frozenset({HazardCategory.HOT_WORK, HazardCategory.WORKING_ALOFT}),
    frozenset({HazardCategory.WORKING_ALOFT, HazardCategory.FALL_PROTECTION}),
}


def _frame_ranges_overlap(a: WorkPackageState, b: WorkPackageState) -> bool:
    a_start, a_end = a.spatial.frame_start, a.spatial.frame_end
    b_start, b_end = b.spatial.frame_start, b.spatial.frame_end
    if None in (a_start, a_end, b_start, b_end):
        return False
    return a_start <= b_end and b_start <= a_end


def _same_compartment(a: WorkPackageState, b: WorkPackageState) -> bool:
    if not (a.spatial.compartment_id and b.spatial.compartment_id):
        return False
    return a.spatial.compartment_id == b.spatial.compartment_id


def _vertically_stacked(a: WorkPackageState, b: WorkPackageState) -> bool:
    """
    Flags the classic 'hot work directly below aloft staging' case:
    one package is aloft/over-the-side while the other occupies an
    overlapping frame range on a lower or unspecified deck level.
    """
    a_overhead = a.spatial.is_aloft or a.spatial.is_over_side
    b_overhead = b.spatial.is_aloft or b.spatial.is_over_side
    if a_overhead == b_overhead:
        return False
    return _frame_ranges_overlap(a, b)


def check_conflict(a: WorkPackageState, b: WorkPackageState) -> str | None:
    """
    Returns a human-readable conflict rationale if `a` and `b` should
    not run concurrently, or None if no conflict is detected.
    """
    if a.work_package_id == b.work_package_id:
        return None

    hazard_overlap = {
        pair
        for pair in INCOMPATIBLE_HAZARD_PAIRS
        if pair <= set(a.hazard_categories) | set(b.hazard_categories)
        and pair & set(a.hazard_categories)
        and pair & set(b.hazard_categories)
    }

    spatially_linked = _same_compartment(a, b) or _frame_ranges_overlap(a, b)

    if hazard_overlap and spatially_linked:
        pair_desc = ", ".join(sorted(h.value for p in hazard_overlap for h in p))
        return (
            f"Incompatible hazard categories ({pair_desc}) detected in overlapping "
            f"spatial envelope between {a.work_package_id} and {b.work_package_id}."
        )

    if _vertically_stacked(a, b):
        # _vertically_stacked only confirms a and b differ on overhead status,
        # not which one is actually overhead -- an independent code review
        # found this rationale unconditionally named `a` as "Overhead work"
        # regardless of which package actually carries is_aloft/is_over_side,
        # which is wrong whenever the non-overhead package happens to be `a`
        # (e.g. because of iteration order in find_all_conflicts). Determine
        # the actual overhead party explicitly instead of assuming positionally.
        a_overhead = a.spatial.is_aloft or a.spatial.is_over_side
        overhead, underlying = (a, b) if a_overhead else (b, a)
        return (
            f"Overhead work ({overhead.work_package_id}) and underlying work "
            f"({underlying.work_package_id}) share an overlapping frame range with "
            f"no vertical deconfliction confirmed."
        )

    return None


def _record_conflict(wp: WorkPackageState, other_id: str, rationale: str) -> None:
    """
    Records one side of a flagged conflict on `wp`, idempotently.

    Two things an independent code review found broken here: (1) a package
    conflicting with more than one other package only kept the *last*
    rationale it was assigned -- `conflict_rationale = rationale` overwrote
    whatever an earlier pair had already recorded, so the reviewer-facing
    explanation silently dropped earlier conflicts even though `.conflicts`
    itself stayed complete; (2) re-running `find_all_conflicts` on the same
    objects (a retry, a checkpoint replay) appended duplicate entries to
    `.conflicts` and duplicate text to `.conflict_rationale` with no
    idempotency guard at all. Both are fixed here: `other_id` is only
    appended if not already present, and `rationale` is only appended to
    the accumulated text if it isn't already part of it.
    """
    if other_id not in wp.conflicts:
        wp.conflicts.append(other_id)
    if not wp.conflict_rationale:
        wp.conflict_rationale = rationale
    elif rationale not in wp.conflict_rationale:
        wp.conflict_rationale = f"{wp.conflict_rationale} | {rationale}"


def find_all_conflicts(packages: list[WorkPackageState]) -> list[WorkPackageState]:
    """
    Evaluates every pair of concurrent work packages and populates
    `.conflicts` / `.conflict_rationale` on affected packages in place.
    Returns the same list for convenience. Safe to call more than once on
    the same objects -- see `_record_conflict`.
    """
    for a, b in combinations(packages, 2):
        rationale = check_conflict(a, b)
        if rationale:
            _record_conflict(a, b.work_package_id, rationale)
            _record_conflict(b, a.work_package_id, rationale)
    return packages


def deconfliction_node(state: dict) -> dict:
    """
    LangGraph node wrapper. Expects state["work_packages"] to be a
    list of WorkPackageState (or dicts coercible to it) and returns
    the same list annotated with conflicts, plus a routing flag for
    the HITL gate.
    """
    packages = [
        wp if isinstance(wp, WorkPackageState) else WorkPackageState(**wp)
        for wp in state["work_packages"]
    ]
    events.emit(
        "deconfliction_start",
        # Spatial/hazard metadata only -- frame numbers, deck level, and
        # hazard category, never `description` -- so a visualizer can
        # place each work package on a schematic deck plan before
        # conflicts are known. See ARCHITECTURE.md Section 8.
        work_packages=[
            {
                "work_package_id": wp.work_package_id,
                "hazard_categories": list(wp.hazard_categories),
                "frame_start": wp.spatial.frame_start,
                "frame_end": wp.spatial.frame_end,
                "deck_level": wp.spatial.deck_level,
                "is_aloft": wp.spatial.is_aloft,
                "is_over_side": wp.spatial.is_over_side,
            }
            for wp in packages
        ],
    )
    find_all_conflicts(packages)

    any_conflicts = any(wp.conflicts for wp in packages)
    for wp in packages:
        if wp.conflicts:
            wp.requires_hitl_review = True
            # Fail closed the moment a conflict is flagged, not just once the
            # HITL gate finishes. `cleared_for_execution` otherwise defaults
            # to True (see state.py), which an independent code review
            # correctly flagged as a window where any consumer reading state
            # between this node and hitl_gate_node -- or a graph that
            # crashes/terminates in that window -- would see an un-reviewed
            # flagged conflict as cleared. hitl_gate_node remains the sole
            # authority on the *final* value once review actually happens.
            wp.cleared_for_execution = False

    events.emit(
        "deconfliction_result",
        conflicts=[
            {
                "work_package_id": wp.work_package_id,
                "conflicts_with": wp.conflicts,
                "hazard_categories": list(wp.hazard_categories),
            }
            for wp in packages
            if wp.conflicts
        ],
    )

    return {
        "work_packages": packages,
        "requires_hitl_review": any_conflicts,
    }
