# Watchstander — Migration Plan

> **Goal:** From a deterministic rules-engine scaffold to a fully case-grounded, HITL-reviewed multi-agent safety system — building each phase on a verified previous phase, never freelancing ahead of the plan.
> **Companion doc:** PASSDOWN.md covers team roles and session continuity; this file is the build road.
> **Rule of the road:** one phase per sitting where practical, each phase ends with tests passing. Never start a phase with the previous one's Definition of Done unmet.
> **Last updated:** 2026-07-25 (Phase 4 in progress, Phase 5 substantially complete)

Phase ordering logic: **prove the deterministic core → wire it to real case data → add reasoning on top → expand coverage → make it presentable/lockable.**

---

## Phase 0 — Structural scaffold

- [x] `WorkPackageState` schema — spatial coordinates, hazard categories, permits required
- [x] Deterministic spatial/temporal deconfliction logic (`deconfliction.py`)
- [x] HITL gate using real LangGraph `interrupt()` — not simulated
- [x] Graph assembly: entry → deconfliction → HITL → END
- [x] Initial case data sourced (5 cases, public OSHA/DOL only, civilian shipyards)
- [x] Tests passing: 4/4, modeled on real case patterns (First Marine, Detyens)
- [x] CI green on Python 3.11 and 3.12
- [x] Repo public, MIT licensed

**Definition of done:** ✅ Complete — 2026-07-23

---

## Phase 1 — Case-data grounding

- [x] Wire `case_data/cases_v1.json` into the deconfliction node
- [x] When a conflict is flagged, retrieve the matching case(s) by hazard category
- [x] Include case citation (case_id, root_cause, source_url) in `conflict_rationale`
- [x] No LLM call yet — pure lookup, keeps this phase deterministic and testable
- [x] Tests: conflict rationale includes a real case_id from the JSON, not just template text

**Definition of done:** ✅ Complete — 2026-07-23.

---

## Phase 2 — Reasoning layer (first LLM node)

- [x] New graph node (`agent_core/reasoning.py`): takes flagged conflict + retrieved case, produces a `SafetyBrief` (executive summary, precedent context, recommended action) for the HITL reviewer
- [x] Node sits between deconfliction and HITL gate, does not replace either — graph is now `deconfliction -> reasoning -> hitl_gate`
- [x] Explicit prompt grounding — no hallucinated case details; the model (or the deterministic fallback) works only from an explicit `_grounding_context()` built from already-verified state
- [x] Deterministic fallback when no `ANTHROPIC_API_KEY` is configured (always true in CI) — zero network calls in the test suite, brief is assembled directly from real fields instead of generated
- [x] Tests (`tests/test_reasoning.py`): verify brief cites the real sourced case_id (e.g. `HW-FIRSTMARINE`) when one exists, states plainly when none exists rather than inventing one, and is only attached to flagged packages
- [x] **Refinement per architecture review:** explicit `[SOURCE: LLM SYNTHESIS]` / `[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]` provenance tag, visible both in the brief's own text and as a top-level `safety_brief_provenance` field in the HITL interrupt payload — a reviewer must always be able to tell which path produced a given brief, never let the two look identical downstream

**Definition of done:** ✅ Complete — 2026-07-24. HITL reviewer sees a natural-language explanation, not just a template string, that explanation is traceable to real case data every time, and its provenance (model-generated vs. templated) is never ambiguous.

---

## Phase 3 — Real retrieval (RAG proper)

- [x] Replace flat JSON lookup with similarity-ranked retrieval (`agent_core/retrieval.py`) once case count justified it — `fall_protection` already has 3 cases, so "always cite the first one in the file" (Phase 1 behavior) stopped being defensible
- [x] Evaluate vector store options (lightweight first) — **decision: pure-Python TF-IDF + cosine similarity, not a vector DB.** ChromaDB/FAISS + sentence-transformer embeddings would need to download model weights at runtime, which conflicts with the edge-resilience requirement from architecture review (deconfliction and case retrieval must keep working with zero network access). At the corpus size this project has (low tens of documents, even at Phase 4's 5-10/category target), a hand-rolled TF-IDF index needs no extra dependency, no model download, and is more than fast enough — revisit only if the corpus grows into the hundreds
- [x] Tests (`tests/test_retrieval.py`): verify ranking actually changes the cited case for a multi-case category (`fall_protection`) based on query relevance, not just "first in file"; verify deterministic fallback behavior with no query signal

**Definition of done:** ✅ Complete — 2026-07-24. Retrieval scales past simple category-matching (ranks by relevance within a category) without losing citation accuracy or adding a network dependency.

---

## Phase 4 — Case data expansion (in progress)

- [ ] Round out to 5-10 cases per **core civilian hazard domain** — **status as of 2026-07-24: confined_space=1, hot_work=2, working_aloft=1, fall_protection=3 (7 cases across the 4 core domains, plus over_the_side=0, now explicitly out of scope — see amendment below). Not yet at target for any domain.**
- [x] First expansion pass added 2 new verified cases: `HW-ASHTABULA-2024` (hot_work — South Marine Systems LLC, Port of Ashtabula OH, fire during welding/paint removal in a cargo hold) and `ALOFT-GUAMSHIPYARD-2022` (working_aloft — Guam Shipyard, rigger fatally struck when an overloaded crane's cable snapped). Both sourced directly from OSHA/DOL press releases, not press-summary sites.
- [x] Continue public OSHA/DOL sourcing only — no Navy data (see PASSDOWN.md Section 7)
- [x] **DoD amendment (architecture review, 2026-07-24):** `over_the_side` is dropped as a standalone case-citation target. Under civilian shipyard employment (29 CFR 1915), over-water fall hazards are legally captured under *Fall Protection* (Subpart I / 1915.73), not a separate OSHA case classification — standalone "over-the-side" program tracking is an underway Naval/NSTM operational convention (confirmed independently by Donnie as SME), not a civilian OSHA case pattern. Future over-water staging cases get sourced and tagged as `fall_protection`, same as any other elevated/edge-guarding case. The `OVER_THE_SIDE` flag stays in `SpatialCoordinates`/`HazardCategory` for deconfliction geometry (it's still a physically distinct condition worth flagging for spatial overlap purposes) — only the case-citation dataset's target category was dropped.
- [ ] `confined_space` needs cases beyond St. John's Ship Building — next pass should search OSHA's structured accident-search database rather than press-release prose (same note as Phase 1's original pass).
- [ ] `fall_protection` next case should ideally come from over-water/over-the-side staging work specifically, given the amendment above, to actually demonstrate that category covering what it now claims to cover.

**Definition of done:** Every one of the 4 core hazard domains (`hot_work`, `confined_space`, `working_aloft`, `fall_protection`) has 5+ sourced, cited cases. **Not yet met — this phase needs at least one more research pass before it can be checked off.**

---

## Phase 5 — Digital twin readiness / live spatial visualizer

- [x] `ARCHITECTURE.md` added — Watchstander now has all three standard docs (MIGRATION, PASSDOWN, ARCHITECTURE); Section 8 records the visualizer's design before it was built
- [x] `agent_core/events.py` — lazy WebSocket broadcaster ported from cosmoai-adept's design, on port 8081 so both visualizers can run side by side
- [x] `deconfliction.py`, `reasoning.py`, `hitl.py` emit `deconfliction_start`/`deconfliction_result`, `reasoning_start`/`reasoning_result`, `hitl_awaiting`/`hitl_decided` — operational metadata only, never `description` or case prose
- [x] `visualizer/` — Godot 4 project, "Blueprint" skin: schematic deck plan (frame grid + deck-level bands), work packages placed by real `frame_start`/`frame_end`/`deck_level`, conflicts drawn as red links, a dedicated Safety Review station that pulses during `hitl_awaiting`
- [x] Asset-sourcing decision made explicit (ARCHITECTURE.md ADR-006): procedural schematic instead of real ship CAD drawings — no license-clean open option exists, and Godot 4 has no native 2D CAD import path
- [x] `visualizer/demo_broadcaster.py` — scripted run through deconfliction → reasoning → HITL, no API key required
- [x] Overlap de-stacking so two work packages sharing a deck level and frame range (i.e. exactly the packages a conflict flags) don't render their labels on top of each other
- [x] Recorded demo GIF, embedded in README.md; screenshot-verified at three points in the sequence (initial placement, conflict flagged, HITL decision)
- [x] `tests/test_events.py` — 2 new tests; full suite still green with zero network calls in CI
- [ ] JSON spatial payload export as a standalone artifact (distinct from the live WebSocket stream) — not yet built; the event stream itself now carries this data, but there's no snapshot-export format yet for a hypothetical non-live consumer

**Definition of done:** ✅ Substantially complete — live visualizer built, screenshot-verified, demo GIF recorded and embedded, docs current. Standalone JSON export (the one remaining unchecked item) is minor and can be picked up opportunistically.

---

## Phase 6 — Lock it in

- [ ] Test coverage expanded beyond deconfliction logic (state validation, HITL gate behavior)
- [ ] README reflects actual current capabilities, not aspirational ones
- [ ] PASSDOWN.md and MIGRATION.md both current
- [ ] One full end-to-end smoke run documented

**Definition of done:** Tests green, docs match reality, repo is honestly representative of what it does.

---

## Phase status

| Phase | Status | Date done |
|---|---|---|
| 0 — Structural scaffold | ✅ | 2026-07-23 |
| 1 — Case-data grounding | ✅ | 2026-07-23 |
| 2 — Reasoning layer | ✅ | 2026-07-24 |
| 3 — Real retrieval (RAG) | ✅ | 2026-07-24 |
| 4 — Case data expansion | 🟡 in progress (7 cases across 4 core domains, target 5-10/domain; `over_the_side` out of scope) | |
| 5 — Digital twin readiness / live visualizer | ✅ (JSON export artifact still open) | 2026-07-25 |
| 6 — Lock it in | ⬜ | |