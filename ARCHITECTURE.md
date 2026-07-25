# Watchstander — Architecture

> **Status:** Living document. Update when a decision changes, a component is added/removed, or a migration phase completes.
> **Last updated:** 2026-07-25

## 1. Purpose and Scope

Watchstander is a LangGraph-based multi-agent system that evaluates concurrent shipyard work packages for hazardous spatial/temporal overlap under **OSHA 1915 (Shipyard Employment)**, and gates anything flagged behind a genuine human-in-the-loop safety review. It exists to demonstrate deterministic, auditable safety reasoning grounded in real incident history — not a chatbot that talks about safety, a state machine that enforces it.

Out of scope for v1: Navy mishap data (classification/aggregation risk — deliberately excluded), any yard-specific proprietary data, and a full 3D digital twin (the spatial visualizer described in Section 8 is a 2D schematic, not a CAD-accurate model).

## 2. Design Principles

1. **Detection is deterministic, explanation is not.** `deconfliction.py`'s geometry/hazard-pair overlap check never touches an LLM — conflicts must be auditable and repeatable. The reasoning layer sits *after* that decision and only explains it; it cannot create or dismiss a conflict.
2. **Every generated brief carries its provenance.** A `SafetyBrief` is tagged `[SOURCE: LLM SYNTHESIS]` or `[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]`, both in its own text and as a top-level field — a reviewer must never have to guess whether a model actually reasoned about a conflict.
3. **The HITL gate blocks for real.** `hitl.py` uses LangGraph's `interrupt()` — execution genuinely pauses and waits for a decision, it does not simulate review with a stub.
4. **Grounded, never invented.** The reasoning node's system prompt and its deterministic fallback both work only from an explicit `_grounding_context()` dict assembled from already-verified state; case IDs, shipyards, dates, and outcomes are never invented.
5. **Edge-resilient by requirement.** Case retrieval (`retrieval.py`) uses a hand-rolled TF-IDF index instead of a vector DB specifically so deconfliction and citation keep working with zero network access and zero model-weight downloads — chosen over ChromaDB/FAISS + sentence-transformers for exactly that reason (see Decision Log).
6. **Public-domain case grounding only.** Every cited case in `case_data/` traces to a public OSHA/DOL record — no Navy mishap data, no proprietary yard data.

## 3. Components

| Module | Responsibility |
|---|---|
| `state.py` | `WorkPackageState`, `SpatialCoordinates`, `HazardCategory`, `RiskLevel`, `SafetyBrief` — the schema everything else operates on |
| `deconfliction.py` | Deterministic spatial/temporal overlap detection between work packages — no LLM call |
| `case_lookup.py` | Phase 1 flat lookup: case citation by hazard category, first match in `case_data/cases_v1.json` |
| `retrieval.py` | Phase 3 TF-IDF ranked lookup: case citation ranked by similarity to the flagged conflict's own text, within the matching hazard category |
| `reasoning.py` | Synthesizes a flagged conflict + its grounded case citation into a `SafetyBrief` for the human reviewer; live LLM call with a deterministic, zero-network fallback |
| `hitl.py` | `interrupt()`-based human review gate — the only place execution actually pauses |
| `graph.py` | Assembles `entry -> deconfliction -> reasoning -> hitl_gate -> END` |
| `case_data/cases_v1.json` | Sourced OSHA/DOL case histories, tagged by hazard category |
| `visualizer/` | Godot 4 2D spatial scene rendering work packages, conflicts, and HITL state on a schematic shipyard deck layout (Section 8) |

## 4. Reasoning and Grounding Model

Threat: an LLM inventing plausible-sounding but false case details (a fabricated shipyard, a fabricated fatality) in front of a Safety Officer making a real decision.

| Surface | Control |
|---|---|
| What the model sees | Only `_grounding_context()` — work package id, description, hazard categories, conflict rationale, and the single best-matching sourced case citation (or an explicit "no case on file" note) |
| What the model must return | Strict JSON with exactly three keys; any malformed or missing-key response is treated as a failure and falls through to the deterministic fallback, never partially trusted |
| No API key / no network | `_call_llm()` returns `None` immediately — this is the expected, always-true path in CI, not an error state |
| Provenance | Every brief is tagged at generation time (`provenance_tag()`), visible both in the brief's prose and as a standalone field in the HITL interrupt payload |

## 5. HITL Model

`hitl_gate_node` reviews every work package flagged by `deconfliction.py` (`requires_hitl_review`) or independently marked `RiskLevel.CRITICAL`, and calls `interrupt()` with a payload built entirely from already-verified state: the work package id, description, hazard categories, conflict rationale, the safety brief (if one was generated) and its provenance tag, and risk level. The graph does not proceed past this node for a flagged package until a human decision is resumed into it. This is the single mandatory checkpoint in the whole system — nothing downstream of a flag can execute without it.

## 6. Case Data Model

`case_data/cases_v1.json` is the only source of precedent the reasoning layer is allowed to cite. Each case is tagged by `hazard_category`, `shipyard`, `summary`, `root_cause`, and `osha_subpart`. Two lookup strategies exist side by side: `case_lookup.cite_case()` (Phase 1, flat first-match) is kept for its narrower test coverage and simplicity; `retrieval.cite_best_matching_case()` (Phase 3, TF-IDF ranked) is what `reasoning.py` actually calls in production once a hazard category has more than one candidate case. See MIGRATION.md Phase 4 for current case-count status per domain — this dataset is explicitly incomplete and tracked as open work, not finished coverage represented as if it were complete.

## 7. Test Strategy

Deterministic logic (`deconfliction.py`, `case_lookup.py`, `retrieval.py`) is tested directly with no mocking required — same inputs, same outputs, every time. `reasoning.py` is tested exclusively through its deterministic fallback path (no `ANTHROPIC_API_KEY` in CI), which is the actual guarantee this project makes: the system produces a real, case-grounded, provenance-tagged brief with zero API keys and zero network calls, not just when the LLM path happens to work.

## 8. Digital Twin / Spatial Visualizer (Phase 5)

**Status: design recorded here, implementation in progress — see MIGRATION.md Phase 5.**

Unlike cosmoai-adept's visualizer — an agent walking between abstract tool stations — Watchstander's natural visualization is literally spatial: work packages already carry `compartment_id`, `frame_start`/`frame_end`, and `deck_level`. The visualizer renders these as an actual schematic cross-section rather than an abstraction layered on top of unrelated data.

**Telemetry layer.** `agent_core/events.py` (new) mirrors cosmoai-adept's design exactly: a lazy-started, no-op-by-default WebSocket broadcaster. `graph.py`'s nodes emit `deconfliction_start`/`deconfliction_result`, `reasoning_start`/`reasoning_result`, and `hitl_awaiting`/`hitl_decided` at the same points execution actually reaches them — never full work-package descriptions or case text, only ids, hazard categories, conflict flags, and the safety-brief provenance tag, consistent with the "operational metadata, not raw content" rule already used in the COSMO projects.

**Scene layout.** A top-down shipyard cross-section: frame numbers run left-to-right as a labeled grid axis, deck levels stack top-to-bottom as horizontal bands, compartments render as labeled rectangles positioned by their `frame_start`/`frame_end` and `deck_level`. Work packages appear as markers inside their compartment's cell — aloft/over-side work floats above the deck band it's staged from, matching `deconfliction.py`'s own `_vertically_stacked()` check. When `deconfliction_result` flags a conflict, both work packages' markers and the connecting overlap region render in a hazard color; when `hitl_awaiting` fires, the flagged package's marker pulses and a HUD panel shows the safety brief text and its provenance tag until `hitl_decided` resolves it.

**Asset sourcing decision.** Real ship general-arrangement drawings (DWG/DXF) exist but are commercial CAD marketplace content with unclear reuse licensing, and Godot 4 has no native 2D CAD import path (only STL, which is 3D-print geometry). Rather than import real ship blueprints, the deck plan is generated procedurally with the same `gen_assets.py` + PIL pattern already used for both COSMO visualizers — grid lines, deck bands, and compartment rectangles, stylistically consistent with the Circuit/Pixel-Office asset pipeline. This keeps the repo dependency-free and license-clean, and is arguably more honest: the case data is real, the deck geometry is explicitly illustrative, and nothing here claims to be an accurate rendering of any specific vessel.

**Consistency with the established house rule:** speech-bubble-equivalent text (the safety brief panel) must hold long enough to read — same `clamp(text.length() / CHARS_PER_SECOND, MIN, MAX)` timing rule as both existing visualizers, not a fixed duration.

## 9. Known Debt

| Item | Notes |
|---|---|
| Case data incomplete | MIGRATION.md Phase 4 — not yet at 5-10 cases per core hazard domain; `confined_space` and `fall_protection` specifically need more sourcing passes |
| No spatial visualizer yet | Phase 5, in progress as of this document — see Section 8 |
| No event schema versioning | Same debt class as cosmoai-adept; fine at zero-to-one consumers, worth a `schema_version` field before a second one exists |
| Single reasoning provider | `_call_llm()` only supports Anthropic; no local-backend option yet (cosmoai-adept has one — worth porting here once the visualizer work lands, not decided yet) |

## 10. Decision Log

| ID | Date | Decision | Rationale |
|---|---|---|---|
| ADR-001 | 2026-07-23 | Deterministic geometry/hazard-pair check, LLM layered on top only for explanation | Conflict detection must be auditable and repeatable; an LLM deciding whether a hazard exists is unacceptable in a safety-critical gate |
| ADR-002 | 2026-07-23 | Real LangGraph `interrupt()` for HITL, not a simulated review step | The whole point of the gate is that it actually blocks; a fake gate is worse than no gate because it looks safe |
| ADR-003 | 2026-07-24 | Explicit provenance tagging on every `SafetyBrief` | A reviewer must always be able to tell model-generated from templated output — silent equivalence between the two paths was flagged as unacceptable in architecture review |
| ADR-004 | 2026-07-24 | Pure-Python TF-IDF retrieval instead of a vector DB | Edge-resilience requirement rules out runtime model-weight downloads; corpus size (low tens of docs) doesn't justify the dependency anyway |
| ADR-005 | 2026-07-24 | `over_the_side` dropped as a standalone case-citation category, kept as a spatial flag | Civilian OSHA (29 CFR 1915) captures over-water fall hazards under Fall Protection (Subpart I); standalone tracking is a Naval/NSTM convention, not a civilian OSHA case pattern |
| ADR-006 | 2026-07-25 | Procedural schematic deck plan instead of real ship CAD drawings for the visualizer | Real ship general-arrangement drawings are commercial CAD content with unclear reuse licensing, and Godot 4 has no native 2D CAD import path; a generated schematic is license-clean and consistent with the existing asset pipeline |

## 11. Maintenance Rules

Update this document when: a migration phase completes, a component is added, a decision changes, or debt is paid. If the doc and the code disagree, the doc is the bug. See [MIGRATION.md](MIGRATION.md) for how we got here and [PASSDOWN.md](PASSDOWN.md) for team roles and session continuity.
