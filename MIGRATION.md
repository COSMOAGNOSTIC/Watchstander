# Watchstander — Migration Plan

> **Goal:** From a deterministic rules-engine scaffold to a fully case-grounded, HITL-reviewed multi-agent safety system — building each phase on a verified previous phase, never freelancing ahead of the plan.
> **Companion doc:** PASSDOWN.md covers team roles and session continuity; this file is the build road.
> **Rule of the road:** one phase per sitting where practical, each phase ends with tests passing. Never start a phase with the previous one's Definition of Done unmet.
> **Last updated:** 2026-07-25 (Phase 4 in progress, Phase 5.5 complete)

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

## Phase 5.5 — External review response: broken graph import + unenforced HITL decision

This phase exists because an independent Fable-model code review (run against the public repo, no shared context with prior sessions) found two critical defects — both confirmed by direct reproduction in a clean virtualenv before fixing:

- [x] **`graph.py` didn't import on a clean install.** `from langgraph.checkpoint.sqlite import SqliteSaver` requires the separate `langgraph-checkpoint-sqlite` package, which was never declared in `pyproject.toml`. Reproduced: a fresh venv with only `langgraph`/`pydantic`/`websockets` installed raised `ModuleNotFoundError` on `import agent_core.graph`. Worse than a missing dependency alone — **no test in this repo ever imported `graph.py` or `hitl.py`**, so CI was green while the flagship assembled graph was unrunnable. Fixed: dependency added; `tests/test_graph.py` now builds the real graph and drives a full invocation through it, so this class of gap can't recur silently.
- [x] **The HITL gate's decision wasn't structurally enforced.** `hitl_gate_node` genuinely paused on `interrupt()` (that part was always real), but recorded the human's answer only as a string appended to `conflict_rationale` — "approve" and "reject" produced identical `WorkPackageState` output. Fixed: `state.py` gained a `HitlDisposition` enum (`APPROVED`/`REJECTED`/`INVALID`) and two new `WorkPackageState` fields, `hitl_disposition` and `cleared_for_execution`; `hitl.py`'s new `_parse_decision()` maps the raw answer to a disposition (case-insensitive prefix match on "approve"/"reject", anything else fails closed to `INVALID`); `cleared_for_execution` is the field any future consumer must actually check, not prose-grepping.
- [x] 10 new tests (`tests/test_graph.py`, `tests/test_hitl.py`) drive the real compiled graph through genuine `interrupt()`/`Command(resume=...)` cycles — approve, reject, ambiguous input, no-review-needed, and independently-critical-risk cases. 34/34 tests passing, up from 24.
- [x] ARCHITECTURE.md §5 rewritten to describe why the fix exists, not just the current state; ADR-007/008 added; a known-but-not-fixed limitation (the HITL loop's non-idempotent `interrupt()` replay under multiple flagged packages) disclosed honestly in Known Debt rather than silently omitted, along with two domain-correctness gaps the same review surfaced (temporal deconfliction claimed but not implemented; no adjacency tolerance on frame ranges).

**Definition of done:** ✅ Complete — both defects reproduced in a clean environment, fixed, and covered by tests that exercise the real graph rather than a mock; `pytest -v` green (34 tests).

---

## Phase 5.75 — Evaluation harness

This phase exists because the external review response above closed two acute defects, but left the system's actual domain-correctness rate an unmeasured, qualitative claim — Fable's review had found real gaps (no adjacency tolerance, `deck_level` never used, `is_over_side` mislabeled in rationale text, a domain-questionable hazard pair) but nothing in the repo turned those findings into a number that CI re-checks. Unit tests answer whether one function is correct on one input; they don't answer "out of a representative set of real scenarios, how many does the whole pipeline get right today, and which specific ones does it still get wrong."

- [x] `eval/scenarios.py` — 14 hand-authored conflict-detection scenarios (true positives, true negatives, a frame-boundary edge case, a multi-conflict case) plus 7 case-retrieval scenarios run against the real `case_data/cases_v1.json`. Four scenarios are known gaps *on purpose*: `gap-adjacent-frames-not-touching`, `gap-two-aloft-packages-stacked`, and `gap-simultaneous-confined-space-entries` each reproduce a specific false negative from ARCHITECTURE.md's Known Debt table; `debatable-aloft-fall-protection-compliant-config` reproduces the domain-questionable `{WORKING_ALOFT, FALL_PROTECTION}` pair Fable flagged. A fifth scenario, `rationale-over-side-labeled-overhead`, pins down the `is_over_side` mislabeling as a measured string check instead of prose.
- [x] `eval/run_eval.py` — runs the real, non-mocked pipeline (`deconfliction.find_all_conflicts`, `retrieval.cite_best_matching_case`, `reasoning.generate_safety_brief`'s deterministic-fallback path) against every scenario and produces a metrics dict. Zero API keys, zero network calls, same constraint as the rest of the suite.
- [x] `eval/baseline.json` — the metrics dict from this reviewed run, checked into git.
- [x] `tests/test_eval_harness.py` — asserts a fresh run matches the baseline exactly, and separately asserts the set of known-gap scenario IDs is exactly the documented four — so either a silent new regression or a silently-unclaimed gap-fix fails the suite instead of passing quietly.
- [x] ARCHITECTURE.md §3/§7/§9/§10 updated (component row, harness description, Known Debt rows cross-referenced to specific scenario IDs, ADR-009).

**Definition of done:** ✅ Complete — 14/14 conflict scenarios and 7/7 retrieval scenarios match their documented expected behavior (10/14 conflict scenarios are domain-correct; the other 4 are documented, intentional known gaps); `pytest -v` green (40 tests, up from 34).

---

## Phase 6 — Lock it in

- [x] Test coverage expanded beyond deconfliction logic (state validation, HITL gate behavior) — see Phase 5.5
- [x] Fixed-scenario evaluation harness with a checked-in regression baseline — see Phase 5.75
- [ ] README reflects actual current capabilities, not aspirational ones — still stale: its architecture diagram omits `reasoning.py`/`retrieval.py`/`case_lookup.py`, and it claims "temporal" deconfliction that isn't implemented (see Known Debt in ARCHITECTURE.md)
- [ ] PASSDOWN.md and MIGRATION.md both current
- [ ] One full end-to-end smoke run documented
- [ ] Temporal deconfliction actually implemented, or the claim removed
- [ ] Adjacency tolerance added to `_frame_ranges_overlap()` (or the "adjacent uncleared space" claim in `deconfliction.py`'s own comment softened to match what the code does)
- [ ] `deck_level` actually used in conflict detection, or the "(x, y) grid coordinates" claim in `SpatialCoordinates`'s docstring softened
- [ ] `is_over_side` rationale text fixed to describe the geometry correctly (currently labeled "Overhead work" — see `eval/scenarios.py`'s `rationale-over-side-labeled-overhead`)

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
| 5.5 — External review response (graph import + HITL disposition) | ✅ | 2026-07-25 |
| 5.75 — Evaluation harness | ✅ | 2026-07-25 |
| 6 — Lock it in | ⬜ | |