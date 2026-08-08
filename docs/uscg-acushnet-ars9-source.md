# USCG Cutter ACUSHNET / ex-USS SHACKLE (ARS-9) — Source Reference for 3D Blockout

Captured 2026-07-28, superseding the Turner Joy source (`uss-turner-joy-dd951-source.md`) as the
primary source for spatial demo data, because this drawing has something Turner Joy's didn't:
real frame station numbers printed directly on the sheet.

## Source

- Vessel: USCG Cutter ACUSHNET (WMEC-167), ex-USS SHACKLE (ARS-9), Diver-class salvage vessel,
  built 1944 for the U.S. Navy, transferred to the Coast Guard 1946. 213 ft length, 40 ft beam.
- Documentation: Historic American Engineering Record (HAER), Library of Congress collection
  reference AK-49, Ketchikan, Alaska. Drawings generated from original USCG records by Todd A.
  Croteau, HAER Maritime Recording Program, National Park Service, 2007.
- Rights: Same public-domain footing as the Turner Joy HAER set — HABS/HAER/HALS documentation is
  "available to the public without restriction" per NPS. Printed directly on the sheet border:
  "Delineated by: Scanned from USCG drawings and reformatted by Todd A. Croteau, 2007 ... National
  Park Service, United States Department of the Interior."
- Sheet used: Sheet 5 of 10, "Deck Plans" — shows Main Deck and Second Deck in full, each with
  labeled compartments, real space designators (Navy/Coast Guard deck-frame-position-usage
  format, e.g. `B-102-6E`, `A-101-A`), and a printed frame-number scale (AP at frame 110 down to
  FP at the bow) plus a 0-220 ft / 0-50 m distance bar. Sheet 9 of 10, "Shell Expansion," shows the
  actual hull curvature and frame lines if ever needed for a curve-accurate model later.
- Sheet 3 of 10, "Inboard Profile" — added 2026-08-08 (ARCHITECTURE.md ADR-027) as the 2D
  visualizer's default background. A genuine side cross-section (not a top-down plan like Sheet
  5): compartments stacked by real deck height, with the same AP=110/FP=0 frame-scale convention
  and the same right-side-is-bow orientation as Sheet 5. Used for `visualizer/Main.gd`'s
  `VIEWS[0]` ("Inboard Profile") pixel calibration — see that file's top-of-file comment for the
  exact constants. This sheet's native capture resolution makes the smallest printed frame-tick
  numbers illegible to read directly, so the calibration was cross-checked against this doc's
  already-known compartment identities instead (Lazarette landing aft-most, Forepeak Tank landing
  forward-most, matching their real names) rather than relying on tick-mark reading alone.
- **Unlike Turner Joy, real frame station numbers ARE printed on this sheet** — no synthetic
  placement values needed for the frame axis.

## Frame axis

AP (stern) = frame 110. FP (bow) = frame 0 (labeled "FP" at the right end of the printed scale,
after frame 2). Standard Navy/Coast Guard frame spacing convention for a vessel this size is
approximately 2 ft/frame, consistent with the sheet's own 213 ft overall length over ~110 frames
(213 / 110 ≈ 1.94 ft/frame) — **this per-frame foot value is inferred from the overall-length
dimension, not printed as a stated constant on the sheet**, flagged the same way every other
inferred-not-verbatim detail in this repo is flagged.

## Compartments used in the 3D blockout, with frame ranges

Frame ranges below are read from tick-mark proximity in the printed scale, not exact digitized
coordinates — treat each as accurate to roughly ±2-3 frames, not a survey measurement.

### Main Deck
- Resistor Room (B-102-6E) — approx. frame 96-104
- DC Shop (B-102-2Q) — approx. frame 90-96
- Ship's Office (B-102-1Q) — approx. frame 86-92
- Galley & Mess Deck (B-101-1L) — approx. frame 70-86
- Chief's Mess (A-104-1L) — approx. frame 62-70
- Jr. Officers Passage (A-103-6L) — approx. frame 40-62
- Laundry (A-102-Q) — approx. frame 24-40
- MAA Stores (A-101-A) — approx. frame 12-24
- Anchor Windlass Room (A-102-E) — approx. frame 2-12

### Second Deck
- Lazarette (C-205-V) — approx. frame 100-110 (aft-most)
- Aft Steering (C-204-E) — approx. frame 92-100
- Reefer Room (C-203-E) — approx. frame 84-92
- Electric & Machine Shop (B-2) — approx. frame 70-84
- Generator Room (B-1) — approx. frame 58-70
- Crew berthing (multiple compartments, unlabeled individually) — approx. frame 24-58
- Forepeak Tank (A-1W) — approx. frame 2-16

## What this was used for

`visualizer/demo_broadcaster.py`'s `WORK_PACKAGES` and the new 3D blockout scene
(`visualizer/Main3D.gd`) both use a subset of the above: Electric & Machine Shop (B-2) on the
Second Deck for the flagged hot_work/confined_space pair (same-compartment linkage, same pattern
as the Turner Joy demo used), Main Deck amidships (no single labeled compartment corresponds to
"aloft" work by definition, since aloft work happens above/outside interior spaces — placed near
frame 60-70, approximate, not tied to a printed label) for working_aloft, and Anchor Windlass Room
/ forward weather deck (frame 2-14) for fall_protection.

## 3D blockout simplification (deliberate, not an oversight)

The 3D scene renders a **rectangular hull, straight bow and stern, flat deck edges** — the actual
hull curvature visible on Sheet 9 (Shell Expansion) is NOT traced or modeled. This was a scope
decision, not a corner cut by accident: getting hull curvature right requires tracing dozens of
points off the shell expansion sheet, which doesn't change anything about the compartment
deconfliction logic the demo exists to show, and the project's existing 2D visualizer already
established the precedent (ADR-006) that a generated/simplified schematic is preferable to
something that looks precise and isn't. Frame positions and compartment identity/order are real;
hull shape is not.

## Not yet done

- Sheet 9 (Shell Expansion / real hull curvature) not traced — would be needed for any future
  curve-accurate hull.
- Only Main Deck and Second Deck compartments are used; sheets covering other decks (if any exist
  in the full 10-sheet set) were not reviewed.
- Frame ranges are tick-proximity estimates, not digitized coordinates — see caveat above.
- No hazard-category judgment here has been reviewed by anyone with DC-A/damage-control
  background, same caveat as the Turner Joy source.
