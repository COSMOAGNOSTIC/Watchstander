# Live 2D Spatial Visualizer — notional carrier schematic

A small Godot 4 project that renders the Watchstander graph's activity on a
schematic of the **notional carrier** (`case_data/carrier_notional_v1.json`,
invented end to end per AGENTS.md rule 6). Work packages are positioned by
frame range and deck level, conflicts are drawn as red links between the
packages involved, and a Safety Review station lights up while a flagged
package waits on a human decision. The background is the procedural blueprint
in `assets/bg_blueprint.png` (made by `assets/gen_assets.py`), not a drawing of
any real ship. Positions are illustrative, not to scale.

**Session 10 (ADR-049):** the visualizer used to draw on public-domain
drawings of a real Coast Guard cutter, with a second switchable sheet and a 3D
hull blockout of the same ship. Those, and the real-ship demo data, were deleted
so that every demo is notional. **The Godot scene changes were not run in Godot**
(not available in the build environment): `Main.gd`'s view data now points at
the schematic, and the 3D scene files are removed. Run it once and report
anything off.

## Why this looks different from cosmoai-adept's visualizer

cosmoai-adept's agent has no inherent spatial data, so its visualizer
invents a spatial metaphor (an agent walking to a "tool station").
Watchstander's `WorkPackageState` already carries real spatial fields —
`compartment_id`, `frame_start`/`frame_end`, `deck_level`, `is_aloft`,
`is_over_side` — so this scene renders that data directly instead of
layering an unrelated metaphor on top of it. See ARCHITECTURE.md Section
8 for the full design rationale, 

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

There is one view today. **V** still cycles `Main.gd`'s `VIEWS` list, so a
second notional view can be added there without touching the drawing code.

The event schema is deliberately close to cosmoai-adept's (same
lazy-broadcaster design, same "operational metadata only" rule) so the
same front-end conventions — and the same eventual consumers, if a real
dashboard is ever built on top of either — transfer across both repos.

## Background

`assets/bg_blueprint.png` is a 960×540 generated schematic with deck lines at
y = 60/160/260/360/460. `Main.gd`'s `VIEWS` entry maps the notional carrier's
frames 0–260 left to right across it and puts markers mid-band. Deck labels
containing "2nd" go to the 2ND DECK band; "3rd", "4th", "5th" or "hold" go to
3RD DECK / HOLD; aloft and over-the-side flags win over the deck label;
anything else goes to MAIN DECK.

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

## Recording a demo GIF

```
Xvfb :99 -screen 0 960x540x24 &
export DISPLAY=:99
godot --path visualizer/ &
python visualizer/demo_broadcaster.py &
ffmpeg -f x11grab -video_size 960x540 -framerate 15 -i :99 -t 33 capture.mp4
ffmpeg -i capture.mp4 -vf "fps=10,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" -loop 0 demo.gif
```
