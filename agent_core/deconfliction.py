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

from collections import defaultdict
from itertools import combinations

from agent_core import events, named_rules
from agent_core.rules_config import load_hazard_rules
from agent_core.state import HazardCategory, WorkPackageState
from agent_core.validation import instant, require_comparable

# ADR-030: hazard-pair rules and the fire-watch capacity limit used to be
# hand-typed constants here. They're now sourced from
# case_data/hazard_rules_v1.json via rules_config.load_hazard_rules(),
# validated against a real schema at import time -- this module no longer
# has two independent places (this file, and whatever a future rule editor
# writes to) that could silently drift out of sync. Both names below are
# kept exactly as before so every existing import/test is unaffected; only
# where the values come from has changed. See rules_config.py and
# ARCHITECTURE.md ADR-030/031 for the full rationale, and
# case_data/hazard_rules_v1.json's own source_citation field for where
# each rule traces back to (OSHA 1915 Subpart D/B for the hazard pairs,
# NAVSEA8010-4.4.3 for the fire-watch limit -- verified against the
# primary-source PDF 2026-08-08, see ADR-023).
_HAZARD_RULES = load_hazard_rules()
INCOMPATIBLE_HAZARD_PAIRS: set[frozenset[HazardCategory]] = _HAZARD_RULES.as_pair_set()
MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH = (
    _HAZARD_RULES.max_concurrent_hot_workers_per_fire_watch
)


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


def _schedules_overlap(a: WorkPackageState, b: WorkPackageState) -> bool:
    """
    Temporal counterpart to `_frame_ranges_overlap`. README and this
    module's docstring have claimed spatial *and* temporal overlap
    detection since Phase 1, but `check_conflict()` never read
    `scheduled_start`/`scheduled_end` at all -- two packages scheduled
    weeks apart in the same compartment were still flagged (see
    ARCHITECTURE.md Known Debt: '"Temporal deconfliction" is advertised,
    not implemented').

    Deliberately the opposite default from `_frame_ranges_overlap`, which
    treats missing frame data as "no spatial link" (returns False).
    Missing schedule data on either side is treated as unknown, not as
    "no overlap" -- a work package with no schedule filled in yet cannot
    be assumed safe to run concurrently with anything, so this returns
    True (over-flagging, the documented safe direction) when either side
    is missing a start or end.
    """
    a_start, a_end = a.scheduled_start, a.scheduled_end
    b_start, b_end = b.scheduled_start, b.scheduled_end
    if None in (a_start, a_end, b_start, b_end):
        return True
    # review-01 R03/R13: real time, and never a silent naive/aware comparison.
    require_comparable([(f"{a.work_package_id}.scheduled_start", a_start),
                        (f"{a.work_package_id}.scheduled_end", a_end),
                        (f"{b.work_package_id}.scheduled_start", b_start),
                        (f"{b.work_package_id}.scheduled_end", b_end)])
    return instant(a_start) <= instant(b_end) and instant(b_start) <= instant(a_end)


_OVERHEAD_HAZARDS = {HazardCategory.WORKING_ALOFT, HazardCategory.OVER_THE_SIDE}


def is_overhead(wp: WorkPackageState) -> bool:
    """
    The single definition of "overhead work" (Session 8a, Donnie's decision after
    review-02): the spatial aloft/over-side flag OR a working_aloft / over_the_side
    hazard label. Detection used the flag alone, so hazard-labelled overhead work
    was invisible to WS-OH-001. The shift suggester uses this same function.
    """
    return (wp.spatial.is_aloft or wp.spatial.is_over_side
            or bool(_OVERHEAD_HAZARDS & {HazardCategory(h) for h in wp.hazard_categories}))


def _vertically_stacked(a: WorkPackageState, b: WorkPackageState) -> bool:
    """
    Flags the classic 'hot work directly below aloft staging' case:
    one package is aloft/over-the-side while the other occupies an
    overlapping frame range on a lower or unspecified deck level.
    """
    a_overhead = is_overhead(a)
    b_overhead = is_overhead(b)
    if a_overhead == b_overhead:
        return False
    return _frame_ranges_overlap(a, b)


def check_conflict(a: WorkPackageState, b: WorkPackageState) -> str | None:
    """
    Human-readable rationale for a conflict between `a` and `b`, or None.
    Thin wrapper over `_detect_conflict`, which also yields the named
    rule IDs (see `conflict_rule_ids`) -- one detection path, so the
    rationale and the rule IDs can never disagree.
    """
    found = _detect_conflict(a, b)
    return found[1] if found else None


def conflict_rule_ids(a: WorkPackageState, b: WorkPackageState) -> list[str]:
    """Sorted named-rule IDs (case_data/named_rules_v1.json) for this pair; [] if no conflict."""
    found = _detect_conflict(a, b)
    return found[0] if found else []


def _detect_conflict(
    a: WorkPackageState, b: WorkPackageState
) -> tuple[list[str], str] | None:
    """
    Returns `(rule_ids, rationale)` if `a` and `b` should not run
    concurrently, or None if no conflict is detected.

    Two packages are only ever flagged if they're both spatially *and*
    temporally linked -- see `_schedules_overlap`. Packages scheduled
    weeks apart in the same compartment are not a conflict even though
    they're spatially linked; packages with no schedule data on one or
    both sides default to "temporally linked" (unknown treated as
    overlapping), the same over-flagging-is-safe posture the rest of
    this module takes.
    """
    if a.work_package_id == b.work_package_id:
        if a is b:
            return None  # a true self-comparison
        # Re-check R06: two distinct records sharing an ID are corrupt input,
        # never "no conflict".
        raise ValueError(
            f"two distinct records share work_package_id {a.work_package_id!r}; "
            "IDs must be unique"
        )

    if not _schedules_overlap(a, b):
        return None

    hazard_overlap = {
        pair
        for pair in INCOMPATIBLE_HAZARD_PAIRS
        if pair <= set(a.hazard_categories) | set(b.hazard_categories)
        and pair & set(a.hazard_categories)
        and pair & set(b.hazard_categories)
    }

    spatially_linked = _same_compartment(a, b) or _frame_ranges_overlap(a, b)

    # review-01 R10: the rationale stays first-match (unchanged text), but the
    # rule-ID list names every rule that applies, so every contact is reached.
    rule_ids: set[str] = set()
    if hazard_overlap and spatially_linked:
        rule_ids |= {named_rules.rule_for_hazard_pair(p).rule_id for p in hazard_overlap}
    stacked = _vertically_stacked(a, b)
    if stacked:
        rule_ids.add(named_rules.rule_for_overhead_work().rule_id)

    if hazard_overlap and spatially_linked:
        pair_desc = ", ".join(sorted(h.value for p in hazard_overlap for h in p))
        return sorted(rule_ids), (
            f"Incompatible hazard categories ({pair_desc}) detected in overlapping "
            f"spatial envelope between {a.work_package_id} and {b.work_package_id}."
        )

    if stacked:
        # _vertically_stacked only confirms a and b differ on overhead status,
        # not which one is actually overhead -- an independent code review
        # found this rationale unconditionally named `a` as "Overhead work"
        # regardless of which package actually carries is_aloft/is_over_side,
        # which is wrong whenever the non-overhead package happens to be `a`
        # (e.g. because of iteration order in find_all_conflicts). Determine
        # the actual overhead party explicitly instead of assuming positionally.
        overhead, underlying = (a, b) if is_overhead(a) else (b, a)
        return sorted(rule_ids), (
            f"Overhead work ({overhead.work_package_id}) and underlying work "
            f"({underlying.work_package_id}) share an overlapping frame range with "
            f"no vertical deconfliction confirmed."
        )

    return None


def _fire_watch_peak_concurrency(
    group: list[WorkPackageState],
) -> tuple[int, list[WorkPackageState]]:
    """
    AUD-01 (AOSE Round 5, Grok): the previous implementation compared
    `len(group)` -- raw package count -- against the limit. That's wrong
    on two independent axes: (1) unit -- two packages with three hot
    workers each read as "2", under the limit of 4, while the fire watch
    was actually covering 6 concurrent hot workers; (2) shape -- even
    once weighted by `hot_worker_count`, summing every package in the
    group overcounts packages that are never actually concurrent (see
    `test_fire_watch_capacity_not_flagged_when_schedules_dont_overlap`'s
    own docstring, which named this exact gap before it was fixed here),
    and undercounts nothing, but a naive "total workers across the whole
    group" figure still isn't what NAVSEA8010-4.4.3 is regulating -- it's
    peak *simultaneous* coverage, not total assigned load.

    This is a weighted sweep-line over closed intervals
    `[scheduled_start, scheduled_end]`, matching the closed-interval
    convention `_schedule_is_ordered` (state.py, AUD-04) already
    enforces at construction time: touching endpoints count as
    overlapping. At a tied timestamp, start events are processed before
    end events specifically so a package ending at T and one starting at
    T are both counted as active at T -- processing ends first would
    silently undercount the one instant they actually overlap.

    Packages missing `scheduled_start` or `scheduled_end` can't be
    placed on the sweep-line at all, and the rest of this module treats
    missing schedule data as unknown, not as "no overlap"
    (`_schedules_overlap` returns True) -- the same over-flagging-is-
    -safe posture applies here: an unscheduled package's
    `hot_worker_count` is added as a constant baseline present at every
    point on the line, rather than being silently dropped from the
    tally, which would be the unsafe direction.

    Returns `(peak_worker_count, packages_active_at_that_peak)`. All
    sort/comparison keys here are `datetime` only (`scheduled_start`/
    `scheduled_end` are always `datetime` once WorkPackageState
    construction succeeds) -- Grok's own AUD-01 patch mixed `float` and
    `datetime` sort keys and crashed; there's nothing to mix here.
    """
    scheduled = [
        wp for wp in group if wp.scheduled_start is not None and wp.scheduled_end is not None
    ]
    unscheduled = [
        wp for wp in group if wp.scheduled_start is None or wp.scheduled_end is None
    ]

    active: dict[str, WorkPackageState] = {wp.work_package_id: wp for wp in unscheduled}
    running = sum(wp.hot_worker_count for wp in unscheduled)
    peak = running
    peak_active = dict(active)

    # is_end=0 (start) sorts before is_end=1 (end) at a tied timestamp --
    # see docstring above for why that ordering is the correct one for
    # closed, touching-counts-as-overlapping intervals.
    sweep_events = sorted(
        (
            *((instant(wp.scheduled_start), 0, wp) for wp in scheduled),
            *((instant(wp.scheduled_end), 1, wp) for wp in scheduled),
        ),
        key=lambda event: (event[0], event[1]),
    )

    for _, is_end, wp in sweep_events:
        if is_end == 0:
            active[wp.work_package_id] = wp
            running += wp.hot_worker_count
        else:
            active.pop(wp.work_package_id, None)
            running -= wp.hot_worker_count
        if running > peak:
            peak = running
            peak_active = dict(active)

    return peak, list(peak_active.values())


def _fire_watch_capacity_conflicts(
    packages: list[WorkPackageState],
) -> list[tuple[WorkPackageState, WorkPackageState, str]]:
    """
    Fire-watch capacity (NAVSEA8010-4.4.3) is an N-way constraint -- how
    many concurrent hot *workers* one fire watch covers -- not a
    pairwise geometry/hazard check like everything else in this module,
    so it can't live inside `check_conflict()`, which only ever sees two
    packages at a time. Packages are grouped by `fire_watch_id`; a
    group's peak concurrent `hot_worker_count` is computed with a
    weighted sweep-line (`_fire_watch_peak_concurrency`, AUD-01 fix --
    replaces the old raw-package-count comparison), and if that peak
    exceeds `MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH`, every
    temporally-overlapping pair in the group is flagged -- temporal, not
    spatial, because fire watch capacity is about how many hot-work
    evolutions one watchstander is actively covering *right now*,
    regardless of where aboard the ship each one is. Flagging is still
    done pairwise (unchanged from before) once a group is known to be
    over capacity; only the over-capacity *decision* changed.

    Packages with no `fire_watch_id` set are never included -- silently
    grouping unassigned packages together would fabricate a capacity
    conflict between two packages that were never actually claimed to
    share a fire watch in the first place.
    """
    by_watch: dict[str, list[WorkPackageState]] = defaultdict(list)
    for wp in packages:
        key = watch_key(wp)
        if key and HazardCategory.HOT_WORK in wp.hazard_categories:
            by_watch[key].append(wp)

    violations: list[tuple[WorkPackageState, WorkPackageState, str]] = []
    for watch_id, group in by_watch.items():
        peak, _peak_active = _fire_watch_peak_concurrency(group)
        if peak <= MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH:
            continue
        for a, b in combinations(group, 2):
            if not _schedules_overlap(a, b):
                continue
            covered = ", ".join(sorted(wp.work_package_id for wp in group))
            rationale = (
                f"Fire watch '{watch_id}' peaks at {peak} concurrent hot workers "
                f"among ({covered}), exceeding the limit of "
                f"{MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH} (NAVSEA8010-4.4.3 -- "
                f"'No more than four hot workers shall be attended by a single fire "
                f"watch,' verified against primary source, see "
                f"case_data/navsea_8010_psns_v2014.json)."
            )
            violations.append((a, b, rationale))
    return violations


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

    Fire-watch capacity is checked separately from the pairwise
    `check_conflict()` loop, not as an alternative to it -- see
    `_fire_watch_capacity_conflicts` for why it's inherently N-way.
    """
    ids = [wp.work_package_id for wp in packages]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        # review-01 R06: check_conflict() skips equal IDs as a self-comparison,
        # so two different records sharing an ID were never compared.
        raise ValueError(f"duplicate work_package_id in batch: {dupes}")

    for a, b in combinations(packages, 2):
        rationale = check_conflict(a, b)
        if rationale:
            _record_conflict(a, b.work_package_id, rationale)
            _record_conflict(b, a.work_package_id, rationale)
    for a, b, rationale in _fire_watch_capacity_conflicts(packages):
        _record_conflict(a, b.work_package_id, rationale)
        _record_conflict(b, a.work_package_id, rationale)
    # review-05 R05-06: more hot workers than one watch may cover, and no watch named, is
    # missing data that would otherwise read as safe. It routes to a person.
    for wp in unnamed_watch_overloads(packages):
        _record_rationale(wp, (
            f"{wp.work_package_id} has {wp.hot_worker_count} hot workers and no fire watch named; one "
            f"watch covers at most {MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH} "
            f"({named_rules.rule_for_fire_watch_capacity().rule_id}, NAVSEA8010-4.4.3)."
        ))
    for watch_id, peak, overloaded in fire_watch_overloads(packages):
        for wp in overloaded:
            if not wp.conflict_rationale or f"Fire watch '{watch_id}'" not in wp.conflict_rationale:
                _record_rationale(wp, (
                    f"Fire watch '{watch_id}' reaches {_package_loads([*_watch_group(packages, watch_id)])[id(wp)]} "
                    f"concurrent hot workers while {wp.work_package_id} is active, exceeding the limit "
                    f"of {MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH} "
                    f"({named_rules.rule_for_fire_watch_capacity().rule_id}, NAVSEA8010-4.4.3)."
                ))
    return packages


def unnamed_watch_overloads(packages: list[WorkPackageState]) -> list[WorkPackageState]:
    """review-05 R05-06: hot work with more workers than one watch covers and no watch named.
    One function, used by detection and by the shift suggester, so they can't disagree."""
    return [wp for wp in packages
            if HazardCategory.HOT_WORK in wp.hazard_categories and watch_key(wp) is None
            and wp.hot_worker_count > MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH]


def watch_key(wp: WorkPackageState) -> str | None:
    """review-05 R05-06: 'FW-N-1' and 'fw-n-1 ' are the same watch."""
    k = (wp.fire_watch_id or "").strip().casefold()
    return k or None


def _watch_group(packages: list[WorkPackageState], watch_id: str) -> list[WorkPackageState]:
    key = (watch_id or "").strip().casefold()
    return [wp for wp in packages
            if watch_key(wp) == key and HazardCategory.HOT_WORK in wp.hazard_categories]


def _package_loads(group: list[WorkPackageState]) -> dict[int, int]:
    """
    Re-check R09: for each package (keyed by id()), the highest number of
    concurrent hot workers on its fire watch at any instant while that
    package is active. Closed intervals, matching `_schedules_overlap`.
    Unscheduled packages count as active everywhere (the same over-flagging
    posture as `_fire_watch_peak_concurrency`), so an unscheduled package's
    load is the watch's overall peak.
    """
    scheduled = [w for w in group if w.scheduled_start is not None and w.scheduled_end is not None]
    sched_ids = {id(w) for w in scheduled}
    baseline = sum(w.hot_worker_count for w in group if id(w) not in sched_ids)

    def load_at(t) -> int:
        return baseline + sum(w.hot_worker_count for w in scheduled
                              if instant(w.scheduled_start) <= t <= instant(w.scheduled_end))

    loads: dict[int, int] = {}
    for w in scheduled:
        s, e = instant(w.scheduled_start), instant(w.scheduled_end)
        # The load only rises at a start, so the max inside [s, e] is at s or at
        # some other package's start that falls inside [s, e].
        points = [s] + [instant(o.scheduled_start) for o in scheduled
                        if s <= instant(o.scheduled_start) <= e]
        loads[id(w)] = max(load_at(t) for t in points)
    overall = max(loads.values(), default=baseline)
    for w in group:
        if id(w) not in sched_ids:
            loads[id(w)] = max(overall, baseline)
    return loads

def fire_watch_overloads(
    packages: list[WorkPackageState],
) -> list[tuple[str, int, list[WorkPackageState]]]:
    """
    review-01 R09 and re-check: every fire watch that ever exceeds the limit,
    with *every* package whose own active interval sees the excess (not only
    the packages at the single global peak, which missed a second overload
    on another day). Unlike `_fire_watch_capacity_conflicts()`, which
    reports pairs, this also reports a single package that overloads its
    own fire watch. Sorted by watch ID, then package ID.
    """
    # Matched by watch_key; reported with the ID as entered (first spelling, sorted).
    spellings: dict[str, set[str]] = defaultdict(set)
    for wp in packages:
        if watch_key(wp) and HazardCategory.HOT_WORK in wp.hazard_categories:
            spellings[watch_key(wp)].add(wp.fire_watch_id.strip())
    watch_ids = sorted(min(v) for v in spellings.values())
    out = []
    for watch_id in watch_ids:
        group = _watch_group(packages, watch_id)
        loads = _package_loads(group)
        over = sorted((w for w in group if loads[id(w)] > MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH),
                      key=lambda w: w.work_package_id)
        if over:
            out.append((watch_id, max(loads.values()), over))
    return out


def _record_rationale(wp: WorkPackageState, rationale: str) -> None:
    """Append a rationale with no partner package (e.g. a self-overload)."""
    if not wp.conflict_rationale:
        wp.conflict_rationale = rationale
    elif rationale not in wp.conflict_rationale:
        wp.conflict_rationale = f"{wp.conflict_rationale} | {rationale}"


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

    # review-01 R09: a package can be flagged with no partner (it overloads its
    # own fire watch), so a rationale alone is enough to route it to review.
    def _flagged(wp: WorkPackageState) -> bool:
        return bool(wp.conflicts or wp.conflict_rationale)

    any_conflicts = any(_flagged(wp) for wp in packages)
    for wp in packages:
        if _flagged(wp):
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
            if _flagged(wp)  # re-check N01: a partner-less overload must not read "all clear"
        ],
    )

    return {
        "work_packages": packages,
        "requires_hitl_review": any_conflicts,
    }
