# PROJECT PASSDOWN: Watchstander
## Civilian Shipyard OSHA Spatial & Temporal Deconfliction Agent Graph

**Last updated:** 2026-07-25
**Status:** Live on GitHub, CI green. ARCHITECTURE.md added; live spatial visualizer (Phase 5) built and demo-recorded. Phase 4 case-data expansion still open.

---

## 1. Executive Summary & Strategic Pivot

- **Core pivot:** Away from cloud database/BigQuery ML labs (Google PMLE cert track), toward pure **Agentic Systems Architecture** — state machines, multi-agent graph flow, structured safety reasoning, local tool execution.
- **Target project:** Open-source civilian shipyard maintenance & safety agent network built around **OSHA 1915 (Shipyard Employment)** standards.
- **Repo name:** `watchstander` — deliberately not COSMO-branded. This project needs to read instantly to an outside recruiter/engineer (shipyard, safety, spatial reasoning) without requiring COSMO-universe context. Naming philosophy: no forced acronyms or cute cleverness — if a nickname emerges organically from use, let it; don't manufacture one.
- **Goal:** Public GitHub repository demonstrating enterprise-grade, high-risk multi-agent flow, spatial deconfliction, and Human-in-the-Loop (HITL) safety governance — doubling as a recruitment/portfolio asset for defense-tech transition (Anduril, Palantir, Rebellion Defense targets).
- **Scope discipline:** Public-domain, civilian OSHA data ONLY for v1. Navy mishap data explicitly excluded to avoid classification/aggregation risk — this was a deliberate scope-narrowing decision, not an oversight.

---

## 2. Team & Division of Labor

- **Donnie (Human Architect):** Operational SME — specifically, knows *when* something crosses into OSHA jurisdiction and how to read the underlying intent of a regulation, not just the letter of it. Systems director, prompt engineer, final gatekeeper. 26-year Navy FCCM; physical operational exposure to Colonna's Shipyard (Norfolk), Marinette Marine (WI), BAE Systems Drydock (San Diego), NASSCO/NAVSTA San Diego graving dock, Mayport, PSNS, and Changi (Singapore) — this grounds spatial/hazard reasoning validation against real yard layouts.
- **Claude (Claude Code / primary developer):** Lead coding partner — LangGraph implementation, rapid prototyping, script execution, repository commits.
- **Gemini (architecture critic & documenter):** Architecture reviewer, OSHA/safety compliance auditor, edge-case reviewer, and maintainer of this passdown doc going forward.

**Sync protocol:** This file (`PASSDOWN.md`) is the single source of truth for cross-session/cross-model continuity — chosen over Google Docs for version history, readable diffs, and zero permission friction. Update after each meaningful sprint milestone. Gemini reads this before starting any review pass.

---

## 3. Technical Stack & Target Architecture

- **Orchestration:** LangGraph (Python) state machine, cyclic loops, structured routing.
- **Data models:** Python `TypedDict` / Pydantic models for `WorkPackageState`, including `SpatialCoordinates` (X, Y, Z / frame / compartment tags) and `SafetyPermitsRequired`.
- **Reused infrastructure:** Where it fits, borrow from the `cosmoai-adept` framework (COSMOAGNOSTIC org) — spec-driven agent pattern, sandboxed file access, SQLite-backed persistence, pluggable tool library. Not a hard dependency; use only what genuinely applies.

### Target capabilities
1. **OSHA 1915 grounding (RAG):** Confined Space Entry, Hot Work, Working Aloft, Over-the-Side, Fall Protection — grounded not just in regulation text but in real case histories/mishap reports, so the agent reasons from *why* the rule exists, not just the rule itself.
2. **Spatial & temporal deconfliction:** Detect physical overlap (e.g., Hot Work directly below Aloft staging, RF hazards active near mast work).
3. **Digital twin readiness:** Expose JSON spatial payloads (compartment/frame IDs) ready for future WebGL/Three.js front-end — not built in v1.
4. **HITL safety gate:** Mandatory manual override/approval checkpoint for high-risk work packages before they're cleared.

---

## 4. Case Data Sourced (v1 — public domain only)

Initial research pass complete via OSHA.gov and DOL.gov public releases. Real, citable, non-aggregate, civilian-only.

**Confined Space Entry:**
- St. John's Ship Building, Palatka FL (Aug 2023) — welder fatality, oxygen-deficient atmosphere, space not tested before entry.
- First Marine LLC, Calvert City KY — towboat explosion during hot work in flammable-gas atmosphere, 3 fatalities, 2 critical. Five contractors cited (prime + insulation sub + 2 staffing agencies).

**Hot Work:**
- OSHA eTool baseline stat: up to 25% of shipyard fatalities result from fires/explosions caused by hot work.
- First Marine case (above) doubles as hot work + confined space overlap example — good candidate for a spatial deconfliction training case since the explosion involved hot work in a space adjacent to one not cleared for it.

**Working Aloft / Over-the-Side / Fall Protection:**
- **Detyens Shipyards Inc., North Charleston SC — longitudinal case, strongest "why the rule exists" material found so far:**
  - 2024: worker fell ~20 ft from unguarded platform edge inside a gas tank; cited for willfully exposing workers to fall hazards (no guardrails), inadequate lighting, no hard hats for workers below overhead work.
  - 2020: shackle fatally struck employee during a lift; cited for fall protection failure + caught-between hazard (employee positioned between guardrail and a rudder shaft being lifted).
  - 2015: 1 repeated + 13 serious + 1 other-than-serious citations, same yard.
  - Pattern: 4 fatalities in 5 years, 33 serious violations across 18 inspections since 2014. This is a repeat-failure case study, not a one-off — high value for teaching pattern recognition rather than single-incident compliance checking.

**Next data pass needed:** Round out to 5-10 cases per category (currently light on pure Over-the-Side/drowning and need more Confined Space breadth). Continue pulling from OSHA public accident search + DOL news releases only.

---

## 5. Immediate Next Steps

1. ~~Scaffold core LangGraph project structure~~ — in progress, this session.
2. Implement `WorkPackageState` schema including spatial tags (`frame_start`, `frame_end`, `deck_level`, `is_aloft`, `is_over_side`).
3. Build the **Spatial Deconfliction Agent** node to evaluate overlapping work windows and hazard zones.
4. Establish the **HITL interruption checkpoint** for flagged permits.
5. Continue case data collection to round out 5-10 per hazard category.
6. Push to GitHub once connector is reauthorized (see Blockers).

---

## 6. Blockers

- **GitHub connector failing (2026-07-23):** Resolved — repo is live at `github.com/COSMOAGNOSTIC/Watchstander`, CI green. No open blockers as of 2026-07-25.

---

## 7. Explicitly Out of Scope (v1)

- Navy mishap data (classification/aggregation risk — deliberately excluded)
- Any yard-specific proprietary data
- Real ship CAD/general-arrangement drawings in the visualizer (see Section 8 below — deliberate, not a resource gap)

---

## 8. Session Notes — 2026-07-25: ARCHITECTURE.md + Live Spatial Visualizer

**Where things stood coming in:** Watchstander already had MIGRATION.md and PASSDOWN.md (this file), both current, but no ARCHITECTURE.md — inconsistent with the three-doc standard now codified across all projects (see cosmoai-adept's PASSDOWN.md for the origin of that rule). No visualizer existed at all; MIGRATION.md Phase 5 ("Digital twin readiness") was explicitly deferred. The prompt for this work: add ARCHITECTURE.md first (with the visualizer's design recorded in it before building), then build the visualizer.

**What got built:**
- `ARCHITECTURE.md` — new. Purpose/scope, design principles (deterministic detection / non-deterministic explanation split, provenance tagging, real `interrupt()`, edge-resilient TF-IDF retrieval), component table, a dedicated Section 8 for the digital-twin/visualizer design (written before implementation), Known Debt, and a Decision Log carrying forward the existing ADRs from git history (deterministic-detection split, real HITL interrupt, provenance tagging, TF-IDF over vector DB, `over_the_side` scope narrowing) plus a new ADR-006 for the asset-sourcing decision below.
- **Asset-sourcing research, before building anything:** checked whether real open-source ship general-arrangement drawings (DWG/DXF) could be imported into Godot. Two findings closed that path: Godot 4 has no native 2D CAD import (only STL, which is 3D-print geometry, not deck plans), and the "open" ship CAD drawings that do exist online (cadbull, dwgdownload, etc.) are commercial CAD marketplace content with unclear reuse licensing — wrong fit for a public MIT repo. Decision: generate a stylized schematic deck plan procedurally instead, same `gen_assets.py` + PIL pattern as both COSMO visualizers. Recorded as ADR-006.
- `agent_core/events.py` — new, ported from cosmoai-adept's broadcaster design (lazy-started, no-op-by-default WebSocket server), on port 8081 instead of 8080 so both COSMO visualizers and this one can run concurrently on one machine.
- `deconfliction.py`, `reasoning.py`, `hitl.py` — each now emits events at the point execution actually reaches them. Deliberately narrow payloads: work package ids, hazard categories, frame range, deck level, conflict pairs, and safety-brief provenance tags — never `description` or case-citation prose, consistent with the "operational metadata only" rule from cosmoai-adept.
- `visualizer/` — Godot 4 project, "Blueprint" skin: a schematic top-down deck plan (frame-grid lines, deck-level bands, a hatched waterline region), work packages placed by their real `frame_start`/`frame_end`/`deck_level`/`is_aloft`/`is_over_side`, conflicts rendered as red links between markers, a dedicated Safety Review station that pulses orange during `hitl_awaiting` and stops on `hitl_decided`.
- Overlap de-stacking (`band_placements` in `Main.gd`): two work packages sharing a deck level and overlapping frame range — which is exactly what a flagged conflict looks like — would otherwise render labels on top of each other. Fixed by shifting the second marker down within its band.
- `visualizer/demo_broadcaster.py` — scripted run through the full pipeline (4 work packages placed, a hot-work/confined-space conflict flagged, a deterministic-fallback safety brief synthesized, HITL review requested and decided) with no API key required.
- Recorded and screenshot-verified the demo GIF at three points: initial placement, conflict flagged, HITL decision resolved. Embedded in README.md.
- `tests/test_events.py` — 2 new tests. Full suite: 24/24 passing, zero network calls.
- README.md, `visualizer/README.md`, MIGRATION.md (Phase 5 flipped from deferred to substantially complete) all updated to match.

**Decided but not built:**
- Standalone JSON spatial-payload export (a snapshot artifact distinct from the live WebSocket stream) — MIGRATION.md Phase 5's one remaining unchecked item. The live event stream already carries this data; a static export format for a hypothetical non-live consumer just hasn't been built yet.
- Whether Watchstander should get a HITL-approval-hook-swap or local-LLM-backend feature parity with cosmoai-adept was not raised this session — Watchstander's HITL gate is already a real `interrupt()`, a different (and arguably stronger) pattern than cosmoai-adept's `approval_hook` callback, so parity isn't obviously the right goal here without more thought.

**Open questions for next session:**
- Phase 4 (case data expansion) is still the most-overdue item in MIGRATION.md — `confined_space` and `fall_protection` both need another OSHA sourcing pass. Worth prioritizing before further visualizer polish.
- Is a non-CLI resume mechanism worth building for the HITL gate (something that actually calls back into a paused LangGraph thread from, say, a Slack button), or is a local/demo-only reviewer flow sufficient for portfolio purposes?
