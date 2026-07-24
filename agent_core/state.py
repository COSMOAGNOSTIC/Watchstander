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

from pydantic import BaseModel, ConfigDict, Field


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


class SafetyPermitsRequired(BaseModel):
    hot_work_permit: bool = False
    confined_space_entry_permit: bool = False
    fall_protection_plan: bool = False
    marine_chemist_certificate: bool = False
    competent_person_inspection: bool = False


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

    risk_level: RiskLevel = RiskLevel.LOW
    requires_hitl_review: bool = False

    # populated by the deconfliction agent, not set by the submitter
    conflicts: list[str] = Field(
        default_factory=list, description="work_package_ids this package conflicts with"
    )
    conflict_rationale: Optional[str] = Field(
        default=None, description="Agent-generated explanation of why a conflict was flagged"
    )

    model_config = ConfigDict(use_enum_values=True)
