"""
Reschedule suggestion — decision-support only, never auto-applied.

A flagged conflict from `deconfliction.py` previously came with only a
rationale for why it was blocked, never a concrete alternative. This
module closes that gap: `suggest_reschedule()` searches nearest-offset-first
for the smallest whole-step schedule shift that clears every conflict for
one target package, re-checked against `deconfliction.py`'s own
`check_conflict()` and `_fire_watch_capacity_conflicts()` rather than
reimplementing them.
`suggest_reschedule()` only ever returns a suggestion; nothing in this
module writes to a WorkPackageState or clears a conflict. The existing
HITL gate (agent_core/hitl.py) remains the sole authority, same as ADR-002.

Deliberately NOT built on a constraint-solver library (OR-Tools CP-SAT,
etc.), even though ARCHITECTURE.md's Extraction Candidates table already
flags CP-SAT as the candidate substrate for the *harder* temporal
chit-expiration engine (independent-clock permit validity, still
pre-design). Two reasons this problem doesn't warrant that dependency:

1. Scope is materially smaller. This module answers one question --
   "does shifting exactly one flagged package by some whole step, holding
   every other package's schedule fixed, produce a conflict-free
   arrangement" -- not a many-package joint optimization. A bounded,
   deterministic search over candidate offsets is the correct-sized tool,
   not an under-use of a heavier one.
2. It matches this repo's own precedent (ADR-004: hand-rolled TF-IDF over
   a vector DB) and its Design Principle 7 policy (ADR-020/021: evaluate
   before hand-rolling, don't reach for a dependency the problem doesn't
   need). Zero new runtime dependencies, zero network access, fully
   auditable -- the search space and the exact conflict check it validates
   against are both already in this codebase (`deconfliction.check_conflict`,
   `deconfliction._fire_watch_capacity_conflicts`), not a black box.

If a future multi-package joint-optimization need actually materializes
(the temporal chit-expiration engine, or a "resequence this whole
availability" ask), OR-Tools CP-SAT is still the right substrate to
evaluate then -- this module is not a rejection of that, just a claim
that today's single-package-shift problem doesn't need it yet.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator, Optional

from pydantic import BaseModel, Field

from agent_core.deconfliction import _fire_watch_capacity_conflicts, check_conflict
from agent_core.state import WorkPackageState


class RescheduleSuggestion(BaseModel):
    """
    A single candidate alternative schedule for one flagged work package.

    `source` is fixed at `"deterministic_search"` -- never `"llm"` -- for
    the same reason `SafetyBrief.source` is tagged (ADR-003): a reviewer
    must always be able to tell how a suggestion was produced. This one
    is always produced by exhaustively checking real offsets against the
    same deterministic conflict logic the rest of the pipeline uses, so
    there is nothing to hedge here the way an LLM-sourced brief would.
    """

    work_package_id: str
    original_start: datetime
    original_end: datetime
    suggested_start: datetime
    suggested_end: datetime
    shift: timedelta = Field(
        description="Signed offset applied to both scheduled_start and scheduled_end. "
        "Positive is later, negative is earlier."
    )
    source: str = "deterministic_search"


def _shifted_copy(wp: WorkPackageState, shift: timedelta) -> WorkPackageState:
    """
    Returns a new WorkPackageState with both schedule bounds shifted by
    `shift`, duration held exactly constant. Never mutates `wp` -- callers
    (including `suggest_reschedule` itself) must not accidentally treat a
    trial candidate as the real, current state of the package.
    """
    assert wp.scheduled_start is not None and wp.scheduled_end is not None
    return wp.model_copy(
        update={
            "scheduled_start": wp.scheduled_start + shift,
            "scheduled_end": wp.scheduled_end + shift,
        }
    )


def _candidate_offsets(step: timedelta, max_shift: timedelta) -> Iterator[timedelta]:
    """
    Yields +step, -step, +2*step, -2*step, ... up to max_shift, nearest
    first. Zero offset is deliberately never yielded -- the whole point of
    a search is to move away from the schedule that's already flagged, and
    a caller re-checking offset 0 would just rediscover the original
    conflict. Nearest-first search means the first accepted offset is
    always the smallest schedule disruption available within the search
    window, not merely *some* conflict-free one further out.
    """
    n = 1
    while step * n <= max_shift:
        yield step * n
        yield -(step * n)
        n += 1


def suggest_reschedule(
    packages: list[WorkPackageState],
    target_id: str,
    step: timedelta = timedelta(hours=1),
    max_shift: timedelta = timedelta(days=14),
) -> Optional[RescheduleSuggestion]:
    """
    Searches for the smallest whole-`step` shift to `target_id`'s schedule
    (holding every other package in `packages` fixed) that produces zero
    conflicts against every other package, re-checked against the exact
    same deterministic rules `deconfliction.py` already enforces:
    pairwise `check_conflict` (hazard-pair + spatial + temporal) and the
    N-way fire-watch capacity constraint -- scoped to violations that
    actually involve the candidate (AUD-10, AOSE Round 6): a pre-existing
    fire-watch capacity problem elsewhere in `packages`, unrelated to
    `target_id`, is never grounds to reject an otherwise-clean offset.

    Returns `None` if: `target_id` isn't in `packages`, the target has no
    schedule to shift (nothing to search from), or no conflict-free offset
    exists within `max_shift` in either direction. A `None` result is not
    silently treated as "package is now fine" anywhere -- it just means
    this function found no suggestion; the flagged conflict and the HITL
    gate are unaffected either way.

    Never mutates `packages` or any WorkPackageState in it, and never
    writes a result back onto the target package -- this is a pure query.
    Wiring a returned suggestion into `SafetyBrief.recommended_action` or
    the HITL reviewer UI is not done by this module; see PASSDOWN.md for
    why that's left as a deliberate next step, not an oversight.
    """
    target = next((wp for wp in packages if wp.work_package_id == target_id), None)
    if target is None:
        raise ValueError(f"no package with id {target_id!r} in packages")
    if target.scheduled_start is None or target.scheduled_end is None:
        return None

    others = [wp for wp in packages if wp.work_package_id != target_id]

    for offset in _candidate_offsets(step, max_shift):
        candidate = _shifted_copy(target, offset)

        if any(check_conflict(candidate, other) for other in others):
            continue

        # AUD-10 (AOSE Round 6, Fable): _fire_watch_capacity_conflicts()
        # reports every over-capacity fire-watch group across the whole
        # list it's given, not just ones involving `candidate` -- a naive
        # `if _fire_watch_capacity_conflicts(trial_group):` check therefore
        # rejects every offset the moment *any* pre-existing, unrelated
        # capacity violation exists anywhere in `others`, even one the
        # target package has nothing to do with. Reproduced: two packages
        # A/B conflict (the flagged pair being searched); unrelated
        # packages C/D share a different, already-over-capacity fire watch
        # weeks later. The naive check vetoed every offset for A/B solely
        # because of C/D. Scoped here to violations that actually name
        # `candidate` -- a pre-existing violation elsewhere in the yard
        # must never block a suggestion for an unrelated package, and this
        # function has no business reporting on or fixing violations
        # outside its own search target.
        trial_group = others + [candidate]
        violations = _fire_watch_capacity_conflicts(trial_group)
        if any(
            candidate.work_package_id in (a.work_package_id, b.work_package_id)
            for a, b, _ in violations
        ):
            continue

        return RescheduleSuggestion(
            work_package_id=target.work_package_id,
            original_start=target.scheduled_start,
            original_end=target.scheduled_end,
            suggested_start=candidate.scheduled_start,
            suggested_end=candidate.scheduled_end,
            shift=offset,
        )

    return None
