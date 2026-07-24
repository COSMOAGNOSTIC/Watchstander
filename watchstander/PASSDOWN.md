# PROJECT PASSDOWN: Watchstander
## Civilian Shipyard OSHA Spatial & Temporal Deconfliction Agent Graph

**Last updated:** 2026-07-23
**Status:** Scaffolding phase — local build, pending GitHub push (connector issue, see Blockers)

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

- **GitHub connector failing (2026-07-23):** All GitHub MCP tool calls (create_repository, search_repositories) returning generic execution failures — not a naming collision, confirmed via unrelated test search. Donnie checking reauth on his end. Repo is being scaffolded locally in the interim; will push in one shot once resolved.

---

## 7. Explicitly Out of Scope (v1)

- Navy mishap data (classification/aggregation risk — deliberately excluded)
- WebGL/Three.js front-end (digital twin visualization is a future phase)
- Any yard-specific proprietary data
