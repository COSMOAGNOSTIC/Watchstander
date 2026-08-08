"""
Shared demo work-package data, real ship-sourced (not synthetic), used by
more than one consumer: `visualizer/demo_broadcaster.py` (fakes the event
sequence for the 2D/3D visualizers, no real graph run) and `reviewer/`
(runs this data through the REAL graph -- real deconfliction, real
reasoning, a real interrupt() a human actually resolves). Living in one
place means both stay honest about using the identical real compartment
data rather than two copies drifting apart.

Compartment names, deck levels, and frame ranges are read directly off
USCG Cutter ACUSHNET / ex-USS SHACKLE (ARS-9)'s HAER (Historic American
Engineering Record) drawing, Sheet 5 of 10 ("Deck Plans") -- Library of
Congress HABS/AK-49, public domain (HABS/HAER/HALS documentation is
"available to the public without restriction" per NPS). Not from
case_data/ -- this is illustrative demo staging, not a sourced incident
or a real work order. Full sourcing detail, including the frame-range
estimation caveat (+/-2-3 frames, read from tick-mark proximity, not
digitized coordinates) and the standard-frame-spacing assumption used to
interpret them, is in docs/uscg-acushnet-ars9-source.md.

Spatial linkage for the flagged pair below comes from the shared
compartment_id ("Electric & Machine Shop (B-2)"), which
deconfliction._same_compartment() supports independently of frame
ranges -- the frame numbers additionally place both packages in a
genuinely overlapping span this time, not just the same named space.
ACUSHNET is an active Coast Guard cutter, not a Navy shipyard work site
-- governing_installation is deliberately left unset here, since tagging
her "PSNS" would misrepresent where she actually is.
"""

from agent_core.state import HazardCategory, RiskLevel, SpatialCoordinates, WorkPackageState


def acushnet_demo_work_packages() -> list[WorkPackageState]:
    """Real `WorkPackageState` objects for the graph -- not the raw dicts
    `visualizer/demo_broadcaster.py`'s scripted event sequence uses, since
    this data is meant to actually be run through `build_graph()`, not
    just broadcast as pre-baked event payloads."""
    return [
        WorkPackageState(
            work_package_id="HW-2201",
            description=(
                "Welding repair on shop equipment inside the Electric & Machine Shop (B-2), "
                "Second Deck, frames 70-84."
            ),
            hazard_categories=[HazardCategory.HOT_WORK],
            spatial=SpatialCoordinates(
                compartment_id="Electric & Machine Shop (B-2)",
                deck_level="Second Deck",
                frame_start=70,
                frame_end=84,
            ),
        ),
        WorkPackageState(
            work_package_id="CS-2202",
            description=(
                "Confined-space entry (bilge/void inspection reachable from the shop) inside "
                "the Electric & Machine Shop (B-2), Second Deck, frames 74-80, during the same "
                "work period as HW-2201."
            ),
            hazard_categories=[HazardCategory.CONFINED_SPACE],
            spatial=SpatialCoordinates(
                compartment_id="Electric & Machine Shop (B-2)",
                deck_level="Second Deck",
                frame_start=74,
                frame_end=80,
            ),
        ),
        WorkPackageState(
            work_package_id="ALOFT-2203",
            description="Working aloft, amidships, way of the mast, Main Deck, frames 60-70.",
            hazard_categories=[HazardCategory.WORKING_ALOFT],
            spatial=SpatialCoordinates(
                compartment_id="Main Deck, amidships (way of mast)",
                deck_level="Main Deck",
                frame_start=60,
                frame_end=70,
                is_aloft=True,
            ),
        ),
        WorkPackageState(
            work_package_id="FALL-2204",
            description=(
                "Anchor detail / forward deck work near the Anchor Windlass Room (A-102-E), "
                "Main Deck, frames 2-12."
            ),
            hazard_categories=[HazardCategory.FALL_PROTECTION],
            spatial=SpatialCoordinates(
                compartment_id="Anchor Windlass Room (A-102-E)",
                deck_level="Main Deck",
                frame_start=2,
                frame_end=12,
            ),
        ),
    ]
