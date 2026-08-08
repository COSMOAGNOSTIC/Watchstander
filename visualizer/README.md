# Live 2D Spatial Visualizer — real HAER drawings, switchable views

A small Godot 4 project that renders the Watchstander graph's activity
directly on top of real USCG Cutter ACUSHNET / ex-USS SHACKLE (ARS-9) HAER
drawings (Library of Congress HAER AK-49, public domain — see
`docs/uscg-acushnet-ars9-source.md`) — not a generated schematic. Work
packages are positioned by their real frame range and deck level on the
actual print, conflicts drawn as red links between the packages involved,
and a dedicated Safety Review station lights up while a flagged package
waits on a human HITL decision. Two real sheets are available and
switchable at runtime with the **V key** — Inboard Profile (default, a
real side cross-section) and Deck Plan (a top-down floor plan) — so a
flagged conflict can be cross-referenced against more than one angle of
the actual ship. See ARCHITECTURE.md ADR-025 and ADR-027.

## Why this looks different from cosmoai-adept's visualizer

cosmoai-adept's agent has no inherent spatial data, so its visualizer
invents a spatial metaphor (an agent walking to a "tool station").
Watchstander's `WorkPackageState` already carries real spatial fields —
`compartment_id`, `frame_start`/`frame_end`, `deck_level`, `is_aloft`,
`is_over_side` — so this scene renders that data directly instead of
layering an unrelated metaphor on top of it. See ARCHITECTURE.md Section
8 for the full design rationale, including why the deck plan is a
generated schematic rather than an imported real ship drawing.

## Running it

1. Install [Godot 4.3+](https://godotengine.org/download).
2. Open this folder (`visualizer/`) as a project in the Godot editor, or run headless:
   ```
   godot --path visualizer/
   ```
3. Start anything that calls `agent_core.events.emit(...)` — either a real
   graph invocation or the scripted stand-in that needs no API key:
   ```
   python visualizer/demo_broadcaster.py
   ```
4. The visualizer connects to `ws://127.0.0.1:8081` automatically (with
   reconnect-on-drop) — a different port than cosmoai-adept's `8080` so
   both visualizers can run side by side on the same machine. Uses the
   literal loopback address, not the hostname `localhost` — on a
   dual-stack machine (Windows in particular) that hostname can resolve
   to a different address family on each side, so both sockets open
   without error but no data ever crosses. See ARCHITECTURE.md ADR-026.
   The status line at the bottom of the scene shows live connection
   state (orange "not connected -- retrying", green "connected") so a
   silent mismatch like that is visible instead of looking identical to
   "nothing is happening yet."

## How it works

`agent_core/events.py` starts a WebSocket server lazily, the first time
anything calls `emit()`. It's a pure broadcaster — no listener, no
effect, and it never broadcasts a work package's `description`, only
operational metadata (ids, frame range, deck level, hazard categories,
provenance tags). `Main.gd` connects as a client using Godot 4's built-in
`WebSocketPeer`, parses each JSON event, and:

| Event | Visual |
|---|---|
| `deconfliction_start` | scene resets; every work package in the roster is placed on the active view by frame range + deck level |
| `deconfliction_result` | flagged packages' markers turn red and a red link line is drawn between each conflicting pair |
| `reasoning_start` / `reasoning_result` | status bubble shows brief synthesis progress and each brief's provenance tag |
| `hitl_awaiting` | the flagged package's marker links to the Safety Review station, which pulses orange, until a decision resumes |
| `hitl_decided` | Safety Review station stops pulsing; bubble shows the disposition (approved/rejected/invalid) |

Pressing **V** at any point re-lays-out the same replayed data (whatever
was last received) against the other view's calibration — switching mid-
scene doesn't lose or reset what's on screen, it just shows the same
flagged packages from a different angle.

The event schema is deliberately close to cosmoai-adept's (same
lazy-broadcaster design, same "operational metadata only" rule) so the
same front-end conventions — and the same eventual consumers, if a real
dashboard is ever built on top of either — transfer across both repos.

## Backgrounds: two real prints, not a schematic (ADR-025, ADR-027)

Two HAER sheets ship as background assets, both real captures from the
Library of Congress's own copy, cropped/resized once, not regenerated at
runtime:

- `assets/bg_acushnet_inboard_profile.png` — Sheet 3/10, "Inboard
  Profile." A genuine side cross-section, compartments stacked by real
  deck height with the sheet's own printed frame scale. **This is the
  default view.** It's the correct drawing type for this scene's
  ALOFT/MAIN DECK/2ND DECK/HOLD/WATERLINE band scheme — every band has an
  actual corresponding row on this sheet.
- `assets/bg_acushnet_deckplan.png` — Sheet 5/10, "Deck Plans." A
  top-down floor plan of Main Deck and Second Deck. Useful for seeing a
  compartment's footprint and neighbors rather than its height. Only two
  of the five bands (Main Deck, 2nd Deck) have a real row on this sheet —
  ALOFT/3RD DECK/OVER THE SIDE sit in the margin above/below the image on
  this view, same as before.

ADR-006 (2026-07-25) originally chose a *generated* schematic over a real
drawing because no real drawing was readily importable at the time; once
the ACUSHNET HAER sheet was sourced for the 3D blockout (ADR-019) the
same constraint no longer applied to the 2D view, and Donnie asked
directly for the real print once he'd watched the schematic version run
live (ADR-025). The Deck Plan sheet shipped first and worked visually,
but its band labels didn't correspond to anything drawn on that
particular sheet type — a top-down plan doesn't have "bands" the way a
side cross-section does. Sourcing the Inboard Profile sheet and making it
the default fixed that mismatch, and keeping the Deck Plan sheet as a
second, switchable view (ADR-027) turned what was a wrong-sheet mistake
into a genuine cross-reference feature, directly requested: seeing a
flagged conflict from more than one real angle of the ship.

Each view has its **own independently-measured pixel calibration** — see
`Main.gd`'s `VIEWS` constant and top-of-file comment for the exact
measurements. Both sheets have the bow on the right and the stern on the
left (the low frame numbers/"FP" sit at the right edge of both prints),
the opposite of the old schematic's left-to-right convention, kept as-is
on both rather than mirroring either image and making its printed text
unreadable.

The old procedural schematic (`assets/bg_blueprint.png`,
`assets/gen_assets.py`) is left in the repo, unused by `Main.gd` now, in
case a future non-ACUSHNET demo vessel needs a placeholder background
before its own real print is sourced.

Status bubbles hold for `clamp(text.length() / 12, 3.0, 7.0)` seconds —
the same rule used in both COSMO visualizers, established after direct
feedback that a flat, fast timer made earlier mockups unreadable. If you
retime `demo_broadcaster.py`'s step interval, keep it at or above that
floor.

## Overlapping work packages

When two flagged work packages share a deck level and an overlapping
frame range — exactly the condition that produces a conflict — their
markers would otherwise render on top of each other. `Main.gd` detects
this (`band_placements`) and stacks the second marker slightly below the
first so both labels stay legible, rather than letting them collide.

## 3D blockout companion view (Main3D.tscn)

A separate, static, non-networked scene — `Main3D.tscn` / `Main3D.gd` / `OrbitCamera.gd` — that
renders the demo data's vessel (USCG Cutter ACUSHNET / ex-USS SHACKLE, ARS-9) as a simplified 3D
hull with compartment boxes at their real frame positions, colored by hazard category, the flagged
pair highlighted in the same red as the 2D view. It does **not** connect to `agent_core.events` or
show live state — it's a "pretty picture" for demos and screenshots, built once from a curated
subset of `docs/uscg-acushnet-ars9-source.md`'s real compartments. The 2D `Main.tscn` remains the
one true live view.

Deliberately simplified: straight bow and stern (no traced hull curvature), every compartment box
spans the full beam (no port/starboard subdivision). Frame positions and compartment identity are
real; hull shape is not — see the source doc's "3D blockout simplification" section for why that
was a scope call, not an oversight.

To view it: open this folder in the Godot editor, open `Main3D.tscn` in the scene dock, and run the
current scene (F6). Left-drag to orbit, scroll to zoom.

To render a screenshot without opening the editor (useful for CI or a quick check after editing the
compartment list), run headless under Xvfb with software GL:

```
Xvfb :99 -screen 0 1280x720x24 &
DISPLAY=:99 godot --path visualizer/ --display-driver x11 --rendering-driver opengl3 -s capture.gd
```

where `capture.gd` is a small throwaway `SceneTree` script that instantiates `Main3D.tscn`, waits a
few frames, and calls `get_viewport().get_texture().get_image().save_png(...)` before quitting —
not checked into this repo since it's a one-off dev tool, not part of the shipped project.

## Recording a demo GIF

```
Xvfb :99 -screen 0 960x540x24 &
export DISPLAY=:99
godot --path visualizer/ &
python visualizer/demo_broadcaster.py &
ffmpeg -f x11grab -video_size 960x540 -framerate 15 -i :99 -t 33 capture.mp4
ffmpeg -i capture.mp4 -vf "fps=10,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" -loop 0 demo.gif
```
