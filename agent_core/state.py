"""
Core state schema for Watchstander work packages.

A WorkPackageState represents a single unit of shipyard work (a job,
a permit, a task) tagged with enough spatial and hazard metadata for
the deconfliction agent to reason about overlap with other concurrent
work packages.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HazardCategory(str, Enum):
    CONFINED_SPACE = "confined_space"
    HOT_WORK = "hot_work"
    WORKING_ALOFT = "working_aloft"
    OVER_THE_SIDE = "over_the_side"
    FALL_PROTECTION = "fall_protection"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"  # always routes to HITL gate


class HitlDisposition(str, Enum):
    """
    The structured, machine-checkable record of a human reviewer's decision
    at the HITL gate. Before this existed, `hitl_gate_node` recorded the
    raw decision only as a string appended to `conflict_rationale` -- prose,
    not state -- so "approve" and "reject" produced identical downstream
    behavior.

    A resume value is read as an exact structural token (see
    `agent_core.hitl._extract_decision`), not parsed as free text --
    APPROVED/REJECTED come from an exact match; anything else is INVALID
    and is treated identically to REJECTED for `cleared_for_execution`,
    below -- the gate fails closed on an unparseable answer rather than
    defaulting to open.

    This is a deliberately binary decision model: there is no
    conditionally-approved state yet. A reviewer who means "approved,
    but only once X is confirmed" must REJECT today and have the
    package resubmitted once the condition is actually met -- any note
    attached to a decision is audit trail only, never enforced. The
    reserved name for the future third state is `CONDITIONALLY_APPROVED`
    -- do not introduce a different name or a separate bool flag for
    this concept later. When it's added, `cleared_for_execution`'s
    allowlist check (`disposition == HitlDisposition.APPROVED`) needs no
    change: a `CONDITIONALLY_APPROVED` value already defaults to
    `cleared_for_execution = False`, same as every other non-APPROVED
    value today, until whatever resolves the condition explicitly flips
    it. See ARCHITECTURE.md Known Debt for the resolution-workflow gap
    this leaves open.
    """

    APPROVED = "approved"
    REJECTED = "rejected"
    INVALID = "invalid"


class SpatialCoordinates(BaseModel):
    """
    Locates a work package within a vessel or shipyard structure.

    Frame numbers and deck levels are the shipboard equivalent of
    (x, y) grid coordinates — this is what lets the deconfliction
    agent detect "hot work directly below aloft staging" style
    overlaps without needing full 3D geometry.
    """

    compartment_id: Optional[str] = Field(
        default=None, description="Compartment or space designator, e.g. 'FR-88-2-A'"
    )
    frame_start: Optional[int] = Field(
        default=None, description="Forward-most frame number affected"
    )
    frame_end: Optional[int] = Field(
        default=None, description="Aft-most frame number affected"
    )
    deck_level: Optional[str] = Field(
        default=None, description="Deck designator, e.g. '2nd Deck', 'Main Deck'"
    )
    is_aloft: bool = Field(
        default=False, description="Work performed >5 ft above a solid surface (29 CFR 1915.77)"
    )
    is_over_side: bool = Field(
        default=False, description="Work performed over the side of the vessel, over water"
    )
    is_enclosed_or_confined: bool = Field(
        default=False, description="Work performed in a confined/enclosed space per 1915 Subpart B"
    )

    @model_validator(mode="after")
    def _frame_range_is_ordered(self) -> "SpatialCoordinates":
        """
        AOSE Round 5 (Grok AUD-04, reproduced and confirmed valid): with no
        constraint here, a transposed frame_start/frame_end (a data-entry
        typo) silently changes what `_frame_ranges_overlap()` in
        deconfliction.py reports, since that function assumes a closed
        interval `[frame_start, frame_end]` and never checks the order
        itself. This is the spatial half of the same defect shape as
        `_schedule_is_ordered` below; both intervals are closed
        (`start <= end`) and inclusive by convention, and that convention
        is enforced here at construction time rather than left implicit.
        """
        if (
            self.frame_start is not None
            and self.frame_end is not None
            and self.frame_start > self.frame_end
        ):
            raise ValueError(
                f"frame_start ({self.frame_start}) must be <= frame_end "
                f"({self.frame_end}) -- frame range is a closed interval "
                "[frame_start, frame_end]"
            )
        return self


class SafetyPermitsRequired(BaseModel):
    hot_work_permit: bool = False
    confined_space_entry_permit: bool = False
    fall_protection_plan: bool = False
    marine_chemist_certificate: bool = False
    competent_person_inspection: bool = False


class SafetyBrief(BaseModel):
    """
    Plain-language synthesis of a flagged conflict, produced by the
    Phase 2 reasoning node for the HITL reviewer. This is explanatory
    output layered on top of an already-deterministic conflict
    decision -- it never decides whether a conflict exists, only
    explains one that deconfliction.py already found.
    """

    executive_summary: str = Field(
        description="2-sentence plain-language breakdown of the hazard for the reviewer"
    )
    precedent_context: str = Field(
        description="Plain-language summary of the sourced case this brief is grounded in, "
        "or an explicit note that no case is on file yet"
    )
    recommended_action: str = Field(
        description="Concrete deconfliction step, e.g. reschedule, add a barrier, verify permit"
    )
    source: str = Field(
        description="How this brief was generated: 'llm' or 'deterministic-fallback'"
    )


class WorkPackageState(BaseModel):
    """
    The unit of work the agent graph reasons over. One instance per
    job/permit/task. Multiple concurrent WorkPackageStates in the same
    or adjacent spatial envelope are what the Spatial Deconfliction
    Agent evaluates for overlap.
    """

    work_package_id: str
    description: str
    hazard_categories: list[HazardCategory] = Field(default_factory=list)
    spatial: SpatialCoordinates = Field(default_factory=SpatialCoordinates)
    permits_required: SafetyPermitsRequired = Field(default_factory=SafetyPermitsRequired)

    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None

    governing_installation: Optional[str] = Field(
        default=None,
        description="Which installation's ruleset governs this package (e.g. 'PSNS'), "
        "used by agent_core/procedural_lookup.py to select a site-scoped governing-"
        "procedure citation. Different installations and type commands (NASNI, NAVSTA "
        "Everett, SURFPAC vs AIRPAC vs AIRLANT) operate under different instructions -- "
        "leaving this unset means no procedural citation is attempted, rather than "
        "silently assuming a default site's rules apply.",
    )
    fire_watch_id: Optional[str] = Field(
        default=None,
        description="Identifier for the fire watch covering this package's hot work, "
        "if any. Multiple concurrent HOT_WORK packages sharing the same fire_watch_id "
        "are checked against NAVSEA8010-4.4.3's single-fire-watch-with-multiple-hot-"
        "workers limitation in deconfliction.py.",
    )
    hot_worker_count: int = Field(
        default=1,
        ge=1,
        description="Number of hot workers this package contributes toward its fire "
        "watch's concurrent-worker tally (NAVSEA8010-4.4.3). AUD-01 (AOSE Round 5): "
        "`_fire_watch_capacity_conflicts` in deconfliction.py previously counted "
        "*packages* per fire watch, not workers -- two packages with three welders "
        "each read as '2', under the limit of 4, when the fire watch was actually "
        "covering 6 concurrent hot workers. Defaults to 1 so a package that never "
        "sets this explicitly is still counted, rather than silently contributing "
        "zero to the tally.",
    )

    risk_level: RiskLevel = RiskLevel.LOW
    requires_hitl_review: bool = False

    # populated by the deconfliction agent, not set by the submitter
    conflicts: list[str] = Field(
        default_factory=list, description="work_package_ids this package conflicts with"
    )
    conflict_rationale: Optional[str] = Field(
        default=None, description="Agent-generated explanation of why a conflict was flagged"
    )

    # populated by the Phase 2 reasoning node, not set by the submitter
    safety_brief: Optional[SafetyBrief] = Field(
        default=None, description="Plain-language HITL brief synthesized from the flagged conflict"
    )

    # populated by hitl_gate_node, not set by the submitter. `conflict_rationale`
    # still gets the decision appended as prose for human readability, but
    # these two fields are the actual machine-checkable record - a future
    # downstream consumer (a scheduler, a permit issuer) must check
    # `cleared_for_execution`, not grep `conflict_rationale` for the word
    # "approve".
    hitl_disposition: Optional[HitlDisposition] = Field(
        default=None,
        description="Structured record of the human reviewer's decision. "
        "None means no HITL review has happened yet for this package.",
    )
    cleared_for_execution: bool = Field(
        default=True,
        description="False only when a required HITL review resulted in a "
        "rejection or an unparseable decision (fail closed). True by default "
        "for packages that never required review. Any downstream consumer "
        "must check this field before acting on a work package.",
    )

    model_config = ConfigDict(use_enum_values=True)

    @model_validator(mode="after")
    def _fail_closed_pending_review(self) -> "WorkPackageState":
        """
        `cleared_for_execution` defaults to True, which is correct for a
        package that never needed review -- but an independent code review
        found it was *also* True for a package that needs review and hasn't
        been reviewed yet, from the moment the object exists (e.g. a
        RiskLevel.CRITICAL package, which always requires review even before
        deconfliction runs) until `hitl_gate_node` records an actual
        disposition. Any consumer trusting `cleared_for_execution` alone --
        exactly what this field's own docstring instructs -- would treat an
        unreviewed critical package as cleared.

        This closes the gap at construction time: a package that is
        independently CRITICAL risk, OR that has `requires_hitl_review=True`
        set directly (e.g. a submitter flagging a package for review for a
        reason outside the risk-level/conflict machinery), and hasn't been
        reviewed yet (`hitl_disposition is None`) is forced to
        `cleared_for_execution = False` here, regardless of what was passed
        in. The `requires_hitl_review` half of this check closes the AUD-09
        residual gap identified during the AOSE Round 4 cross-review
        (`aose-round4-crossreview-gemini-aud09.md` §3.1): CRITICAL-risk and
        conflict-flagged packages were already closed (this validator's
        original scope, and `deconfliction_node`'s inline flip,
        respectively), but a package that is neither CRITICAL nor
        conflict-flagged, yet still has `requires_hitl_review=True` set
        directly, was not -- it read `cleared_for_execution=True` from the
        moment it was constructed until an actual disposition landed.
        `deconfliction_node` closes the conflict-flagged half of the same
        gap for packages that only become review-required once a conflict
        is actually detected (see deconfliction.py). `hitl_gate_node`
        remains the sole authority once an actual disposition is recorded --
        this validator only tightens the *pending-review* default, it never
        runs again after that, since by then `hitl_disposition` is no
        longer `None`.
        """
        if self.hitl_disposition is None and (
            self.risk_level == RiskLevel.CRITICAL or self.requires_hitl_review
        ):
            self.cleared_for_execution = False
        return self

    @model_validator(mode="after")
    def _schedule_is_ordered(self) -> "WorkPackageState":
        """
        AOSE Round 5 (Grok AUD-04, reproduced and confirmed valid): with no
        constraint here, a transposed scheduled_start/scheduled_end silently
        disables every downstream conflict check for this package.
        `check_conflict()` in deconfliction.py gates on `_schedules_overlap()`
        first and returns early if it's False -- and `_schedules_overlap()`
        assumes a closed interval `[scheduled_start, scheduled_end]` without
        checking the order itself, so one bad data-entry typo (a real
        scenario, not a contrived one) can make a genuinely overlapping,
        incompatible-hazard-pair conflict report as "no conflict" with
        nothing else in the pipeline able to catch it. Enforced here at
        construction time, same as the frame-range half of this defect in
        SpatialCoordinates._frame_range_is_ordered.
        """
        if (
            self.scheduled_start is not None
            and self.scheduled_end is not None
            and self.scheduled_start > self.scheduled_end
        ):
            raise ValueError(
                f"scheduled_start ({self.scheduled_start}) must be <= "
                f"scheduled_end ({self.scheduled_end}) -- schedule is a "
                "closed interval [scheduled_start, scheduled_end]"
            )
        return self
