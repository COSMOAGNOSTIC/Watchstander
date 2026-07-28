# USS Turner Joy (DD-951) — Source Reference for Visualizer Demo Data

Captured 2026-07-27. This is a transcription reference, not generated/authoritative data — it records what was actually read off two real drawing sheets, for anyone extending `visualizer/demo_broadcaster.py` or sourcing more real compartments later.

## Source

- Vessel: USS Turner Joy (DD-951), Forrest Sherman-class destroyer, 1959. Museum ship, Bremerton Marina, Kitsap County, WA.
- Documentation: Historic American Engineering Record (HAER), Library of Congress collection reference WA-210, recorded 2011 (delineated by Ryan Pierce and Todd Croteau, HAER Maritime Recording Program, National Maritime Heritage Program).
- Rights: HABS/HAER/HALS documentation is "available to the public without restriction" (National Park Service FAQ) — federal government work product, public domain, same footing as the NAVSEA 8010 Manual sourcing.
- Sheets used: Sheet 2 of 4 ("Inboard Profile and Upper Deck Plans"), Sheet 3 of 4 ("Lower Deck Plans"). Sheets 1 (title/specifications) and 4 (midship/typical sections) not transcribed here.
- **Printed directly on the drawing, carried forward as-is:** "This drawing was traced from scans of original U.S. Navy drawings located on the ship. The layout and dimensions were not verified in the field."
- **No frame station numbers appear on either sheet** — only an overall length (407'-5") and a 0–440 ft distance/scale bar. Any frame numbers used in `demo_broadcaster.py` are therefore synthetic placement coordinates for the visualizer's rendering axis only, not derived from this source.

## Deck levels (top to bottom as drawn)

Top of House, 04 Level, 03 Level, 02 Level Aft, 02 Level, 01 Level, Main Deck, First Platform (Second Deck), Second Platform (Third Deck), Third Platform, Hold.

## Compartments transcribed, by sheet

### Sheet 2 — Inboard Profile (side view, aft to forward as drawn)
Steering Gear, Emergency Generator, Air Conditioning Machinery, No. 53 Gun Mount Carrier Room, 5"/54-cal. Projectile Stowage, 5"/54-cal. Powder Magazine (aft), Ballast, Fuel Oil Ballast, No. 2 Engine Room, No. 2 Fire Room, Crew Space (×2), Uptake Space and Passage, Crew Mess Hall, No. 1 Engine Room, No. 1 Fire Room, Radio (Aux) / Radio Center, Combat Information Center (CIC), Passage, Unit Commander's Stateroom, Wardroom Lounge, Stateroom, Crew Space (×2), No. 51 Gun Mount Carrier Room, Sonar Equipment Room, Pure Water Storage, 5"/54-cal. Powder Magazine (forward), 5"/54-cal. Storage, Sonar Dome (below hull, bow).

### Sheet 2 — Upper works, top-down (Top of House / 04 / 03 / 02 Aft / 02 Level)
Antenna Group, ECM Room No. 2, IC Room, Pilot House, Target Designation Equipment Room, Fan Room No. 1, MK 68 Director No. 51.

### Sheet 2 — 01 Level plan
5"/54-cal. Loading Machinery (beneath), Torpedo Tubes (port and starboard), Expansion Joints, Radio Center, 40mm Hedgehogs port and stbd (removed), 5"/54-cal. Gun Mount (forward), Gun Mount (aft), Captain's Stateroom, Unit Commander's Stateroom (extended forward over gun mount), Fueling-at-Sea Station, Depth Charge Rack (removed).

### Sheet 2 — Main Deck plan
Forward anchor windlass, Depth Charge Rack (removed), 5"/54-cal. Gun Mounts (forward and aft, single mounts), 5"/54-cal. Loading Machinery (beneath), Torpedo Tubes port/starboard (triple), Expansion Joints (×3), Galley, Radio Center, 40mm Hedgehogs port/stbd (removed), Crew Mess and Lounge, Wardroom and Lounge.

### Sheet 3 — First Platform (Second Deck)
Crew's Living Space (×3 forward, ×2 aft), No. 2 Engine Room, No. 2 Fire Room, No. 1 Engine Room, No. 1 Fire Room, No. 55 Gun Mount Carrier (forward), No. 51 Gun Mount Carrier (aft), Crew's Head, Anchor Windlass Room.

### Sheet 3 — Second Platform (Third Deck)
Steering Gear (aft-most), 5"/54-cal. Ammo Hoist (×2), No. 2 Engine Room, No. 2 Fire Room, No. 1 Engine Room, No. 1 Fire Room, Fuel Tanks, Engineering Office, Refrigeration Machinery, Crew's Living Space, Refer/Freezer Spaces, Sonar Equipment Room No. 1, Fan Room, Sonar Equipment Room No. 2.

### Sheet 3 — Third Platform
Small unlabeled compartment at the bow only (not transcribed further — no legible label).

### Sheet 3 — Hold
No. 2 Engine Room, No. 2 Fire Room, No. 1 Engine Room, No. 1 Fire Room (lower extents of the same spaces listed above — engineering spaces span multiple deck levels vertically, as expected).

## What this was used for

`visualizer/demo_broadcaster.py`'s `WORK_PACKAGES` uses four of these (No. 1 Fire Room ×2 for the flagged hot_work/confined_space pair, MK 68 Director No. 51 for working_aloft, 01 Level/gun mount area for fall_protection) — see that file's module docstring for the full sourcing note and the synthetic-frame-number caveat.

## Not yet done

- Sheets 1 and 4 not transcribed.
- No frame station data exists in this source at all — if real frame numbers are ever needed (e.g. for a non-demo use), they'd have to come from the ship's actual frame table / inclining experiment booklet, not this HAER survey.
- No hazard-category judgment here has been reviewed by anyone with actual damage-control/DC-A school background — treat the hot_work/confined_space pairing choice as illustrative staging, not a vetted safety determination.
