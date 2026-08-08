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

## Phase 5.85 — Second-pass review response: fail-open gaps in this session's own fixes

This phase exists because closing Phase 5.5's two acute defects didn't fully close them — a second, more targeted independent Fable-model review pass (asked to line-trace `state.py`, `deconfliction.py`, and `hitl.py` cold, not read this document) found real fail-open gaps in the disposition-enforcement and graph-import fixes from Phase 5.5 itself, plus two pre-existing correctness bugs in `deconfliction.py`.

- [x] **`cleared_for_execution` no longer defaults open while review is pending.** It defaulted `True` not just for packages that never needed review, but also for a `CRITICAL`-risk package before it's ever reviewed, and for a flagged package in the window between `deconfliction_node` and `hitl_gate_node`. Fixed with a `model_validator` on `WorkPackageState` (closes the construction-time gap) plus an explicit set in `deconfliction_node` (closes the post-flagging gap).
- [x] **`_parse_decision()` fails closed on hedged/conditional text, not just unrecognized text.** "approve only if X re-certifies" and "approve?? absolutely not" both used to parse as `APPROVED` since both start with the substring "approve". Fixed with a leading-words negation-cue check ahead of the prefix match — bounded to the leading words specifically after an early version of the fix wrongly flagged legitimate trailing rationale ("reject - the permit hasn't been signed off") as `INVALID` too.
- [x] **`conflict_rationale` accumulates instead of being overwritten, and `find_all_conflicts` is idempotent.** A package conflicting with two others used to keep only the last pair's rationale; re-running the function on the same objects used to append duplicate `.conflicts` entries. Fixed via a `_record_conflict()` helper with both guards.
- [x] **The overhead/underlying rationale label tracks the actual overhead party, not argument position.** The rationale text used to unconditionally name the first argument to `check_conflict()` as "Overhead work" regardless of which package actually carried `is_aloft`/`is_over_side`. Fixed — this closes the *labeling* bug; the deeper semantic question of whether `is_over_side` should count as "overhead" at all remains open (Known Debt).
- [x] **`hitl_decided` no longer broadcasts the reviewer's raw free-text answer**, closing a violation of `events.py`'s own ids/flags/provenance-only broadcast policy that Phase 5.5's disposition fix itself introduced.
- [x] 10 new tests (`tests/test_state.py` new; `tests/test_deconfliction.py` gained 4; `tests/test_hitl.py` gained 3) — each named for the specific bug it regresses, not just the passing case. 50/50 passing, up from 40. `eval/baseline.json` re-verified unchanged (the harness only captures booleans/counts, not raw rationale text, so none of these fixes moved the eval metrics).
- [x] ARCHITECTURE.md §5 gained five new explanatory paragraphs (one per fix); Known Debt's HITL-loop and `is_over_side` rows updated to reflect what's now partially mitigated vs. still fully open; ADR-010 through ADR-013 added.

**Definition of done:** ✅ Complete — all five issues reproduced via the review's own examples, fixed, and covered by regression tests; `pytest -v` green (50 tests); eval harness baseline re-verified unaffected.

---

## Phase 5.9 — Two items closed off the NEED list: temporal deconfliction, event schema versioning

- [x] **`check_conflict()` now reads `scheduled_start`/`scheduled_end`.** README and `deconfliction.py`'s own docstring had claimed spatial *and* temporal overlap detection since Phase 1; the code never checked it. Fixed via a new `_schedules_overlap()` helper, gated as an early return in `check_conflict()` before either the hazard-pair or vertically-stacked branch runs. Missing schedule data on either side defaults to overlapping (not non-overlapping) — the opposite default from `_frame_ranges_overlap()` — since an unscheduled package can't be assumed safe to run concurrently the way an unlocated one's spatial link can be assumed absent. 3 new tests in `tests/test_deconfliction.py`.
- [x] **`events.py` broadcast payloads now carry `schema_version`.** Every event previously went out with no version marker at all. Added a module-level `SCHEMA_VERSION` constant and a pure `build_message()` function (split out of `EventBroadcaster.emit` for unit-testability without a live WebSocket client), stamped on every payload after `**payload` so a caller can't override it. cosmoai-adept's broadcaster doesn't have this field yet — worth porting there too, not done in this pass. 2 new tests in `tests/test_events.py`.
- [x] 5 new tests total. 55/55 passing, up from 50. `eval/baseline.json` re-verified unchanged — none of `eval/scenarios.py`'s existing scenarios set `scheduled_start`/`scheduled_end`, so all default to the "missing data = overlapping" path and none of their outcomes moved.
- [x] ARCHITECTURE.md §5 gained two new explanatory paragraphs; Known Debt's "temporal deconfliction advertised, not implemented" row removed (closed) and "no event schema versioning" row removed (closed); ADR-014 and ADR-015 added.

**Definition of done:** ✅ Complete — both items reproduced against ARCHITECTURE.md's own Known Debt description, fixed, covered by regression tests; `pytest -v` green (55 tests); eval harness baseline re-verified unaffected. `is_over_side`'s semantic model deliberately deprioritized rather than fixed, 2026-07-27 (ADR-016 — never causes an under-flag, only an imprecise rationale). Still genuinely open from the original NEED list: the non-idempotent multi-package HITL loop, see Known Debt.

---

## Phase 5.95 — NAVSEA 8010 Manual integration: site-scoped procedural grounding + fire-watch capacity

Prompted by a real signal, not a hypothetical one: a Carrier-team GS-14 told Donnie directly that work in this specific lane is award-relevant. Scoped deliberately narrow rather than building a universal Navy-wide rules engine in one pass — see the design discussion this phase is based on for why (different installations/type commands run different governing instructions; nothing forces fleet-wide adoption of this software yet, so there's no second real deployment to generalize against).

- [x] **New site-scoped governing-procedure source: `case_data/navsea_8010_psns_v2014.json`.** Confirmed genuinely public domain — NAVSEA S0570-AC-CCM-010/8010, Distribution Statement A, dated 06 Feb 2014 / smoothed 26 Aug 2014, hosted at NAVSEA's own FOIA reading room. A separate "ACN 3/A" amendment found on a third-party (non-.mil) host, marked FOR OFFICIAL USE ONLY, was identified and explicitly excluded — not the authoritative copy, not used anywhere in this repo. Covers `hot_work` only; the manual doesn't address confined_space/working_aloft/fall_protection/over_the_side, and no entries exist for those categories under this source.
- [x] **New `agent_core/procedural_lookup.py`**, mirroring `case_lookup.py`'s pattern: `cite_governing_procedure(installation, hazards)` returns a citation or `None`. Site-scoped by design — `WorkPackageState.governing_installation` selects the ruleset; unset means no citation, not a silently-assumed default site. Adding a second installation means adding a sourced JSON file and a `_RULESET_FILES` entry, not new logic.
- [x] **Every ruleset entry marked `verified: false`** — extracted via automated document fetch, not confirmed verbatim against primary-source text for exact numeric/procedural specifics. `cite_governing_procedure()` surfaces an explicit `[UNVERIFIED: ...]` caveat in the citation text itself.
- [x] **`reasoning.py` wired to cite both sources** — case precedent and governing procedure are additive, kept distinguishable in the system prompt and in `_deterministic_fallback()`'s `precedent_context` text, never blended into one unlabeled claim.
- [x] **New deconfliction concept: fire-watch capacity (NAVSEA8010-4.4.3).** `WorkPackageState` gained `fire_watch_id`. `deconfliction._fire_watch_capacity_conflicts()` — a new N-way function, not a pairwise `check_conflict()` branch, since capacity is a group constraint — flags temporally-overlapping HOT_WORK packages sharing a fire watch once the group exceeds `MAX_CONCURRENT_HOT_WORKERS_PER_FIRE_WATCH` (set to `1`, a conservative default since the exact regulatory number is unverified, not a confirmed limit). Called from `find_all_conflicts()` alongside the pairwise loop, with the same idempotency guard via `_record_conflict()`.
- [x] 11 new tests (`tests/test_procedural_lookup.py` new — 5; `tests/test_deconfliction.py` gained 4; `tests/test_reasoning.py` gained 2). 66/66 passing, up from 55. `eval/baseline.json` re-verified unchanged — no existing eval scenario sets `governing_installation` or `fire_watch_id`, so none of their outcomes moved.
- [x] ARCHITECTURE.md §3/§6/§9/§10 updated (component rows, two new grounding-model explanatory paragraphs, three new Known Debt rows for the unverified-specifics gap, ADR-017/ADR-018 added); README.md updated with the second grounding source and component list.

**Definition of done:** ✅ Complete for this scope — site-scoped ruleset architecture built and sourced correctly (public domain confirmed, FOUO copy excluded), dual citation grounding wired, fire-watch capacity implemented as its own correctly-scoped N-way check, `pytest -v` green (66 tests), eval harness baseline re-verified unaffected. Explicitly NOT done, on purpose: verbatim confirmation of NAVSEA8010-4.4.3's actual numeric fire-watch limit and other unverified specifics (needs a primary-source read, not automated extraction); a second installation's ruleset (no second site deployment exists yet to generalize against); Chapter 11 (fire/smoke boundaries) integration into the spatial model — flagged as a real structural echo worth a future look, not built this pass.

---

## Phase 5.97 — Real ship data for the visualizer demo: Turner Joy → USCG ACUSHNET, plus a 3D blockout companion view

Two rounds of real-drawing sourcing. First pass used USS Turner Joy (DD-951)'s HAER drawings (real compartment names, but no printed frame numbers — `frame_start`/`frame_end` were synthetic placement values, flagged as such). Second pass found a strictly better source and replaced it.

- [x] **Source swap: Turner Joy → USCG Cutter ACUSHNET / ex-USS SHACKLE (ARS-9), HAER AK-49, Sheet 5 ("Deck Plans").** Same public-domain footing (HABS/HAER/HALS, NPS-confirmed), but this sheet has real frame station numbers printed on it (AP at frame 110 to FP at the bow) — closes the exact "not read off the drawing" caveat the Turner Joy data carried. See `docs/uscg-acushnet-ars9-source.md` for the full sourcing chain, including the ±2-3 frame tick-proximity estimation caveat and the inferred (not printed) ~1.94 ft/frame spacing. Turner Joy source doc kept for history, no longer the active demo source.
- [x] **`visualizer/demo_broadcaster.py` `WORK_PACKAGES` updated** — real ACUSHNET compartments (`Electric & Machine Shop (B-2)` for the flagged hot_work/confined_space pair, now genuinely frame-overlapping and not just compartment-ID-matched; `Anchor Windlass Room (A-102-E)` for fall_protection; an approximate, honestly-labeled "amidships, way of mast" placement for working_aloft since aloft work by definition isn't a labeled interior compartment). 2D visualizer (`Main.gd`) required no changes — its `deck_level` string matching already handled "Main Deck"/"Second Deck".
- [x] **New: `visualizer/Main3D.gd` + `Main3D.tscn` + `OrbitCamera.gd`** — a static, non-networked 3D blockout companion view, explicitly NOT a replacement for the live 2D visualizer (which still owns the WebSocket-driven real-time deconfliction/HITL display). Renders ACUSHNET as a simplified rectangular hull (straight bow/stern — real curvature exists on the source's Sheet 9 but wasn't traced, a deliberate scope call in the same spirit as ADR-006's 2D schematic decision, not an oversight) with compartments extruded as boxes at their real frame positions, colored by hazard category, flagged pair highlighted in the same red used elsewhere. Mouse-drag-to-orbit, scroll-to-zoom camera, no dependencies.
- [x] **Actually rendered, not just written.** Downloaded a real Godot 4.3 Linux binary into the build sandbox, ran it headless under Xvfb + software GL (llvmpipe) with a throwaway capture script, and confirmed the scene renders correctly — real ship silhouette, correct hazard colors, flagged pair in red — before handing off. Camera defaults tuned from that actual render (initial framing was too close/low; fixed).
- [x] `pytest -v` still green, 66/66 — no Python-side logic touched, only demo data and new Godot-only files.

**Definition of done:** ✅ Complete for this scope — real frame numbers now drive both the 2D and 3D views, the 3D blockout exists, renders correctly (verified via an actual headless render, not just code review), and is honestly documented as a simplified companion view rather than a claimed-accurate hull model. Explicitly NOT done, on purpose: hull curvature (Sheet 9 not traced), port/starboard subdivision within compartments (every box spans full beam), and only a curated subset of ACUSHNET's real compartments are placed in the 3D scene (the rest exist in the source doc but weren't worth the time to add for a demo view).

---

## Phase 6 — Lock it in

- [x] Test coverage expanded beyond deconfliction logic (state validation, HITL gate behavior) — see Phase 5.5
- [x] Fixed-scenario evaluation harness with a checked-in regression baseline — see Phase 5.75
- [x] Fail-open gaps in the Phase 5.5 fixes themselves closed — see Phase 5.85
- [x] ARCHITECTURE.md §8's visualizer status line corrected from "implementation in progress" to "built and substantially complete," matching Phase 5's own status above — caught by an independent Fable/Grok review pass finding the two docs disagreed with each other, rather than caught proactively
- [x] CI was red on every push since the eval harness was added (Phase 5.75) — `eval/` was never registered as an installable package, so `tests/test_eval_harness.py`'s `from eval.run_eval import ...` only resolved locally because every local check happened to use `python -m pytest` (which prepends cwd to `sys.path`); CI runs the `pytest` console script directly, which doesn't. Fixed by adding `eval*` to `pyproject.toml`'s `packages.find`, same as `agent_core`. Caught by Donnie noticing the GitHub Actions badge, not by any local or AI-assisted review — see PASSDOWN.md.
- [ ] README reflects actual current capabilities, not aspirational ones — still stale: its architecture diagram omits `reasoning.py`/`retrieval.py`/`case_lookup.py` (the "temporal" deconfliction claim is no longer stale as of Phase 5.9 — it's now true)
- [ ] PASSDOWN.md and MIGRATION.md both current
- [ ] One full end-to-end smoke run documented
- [x] Temporal deconfliction actually implemented — see Phase 5.9
- [ ] Adjacency tolerance added to `_frame_ranges_overlap()` (or the "adjacent uncleared space" claim in `deconfliction.py`'s own comment softened to match what the code does)
- [ ] `deck_level` actually used in conflict detection, or the "(x, y) grid coordinates" claim in `SpatialCoordinates`'s docstring softened
- [x] `is_over_side`'s underlying semantic model — deliberately deprioritized (not fixed), 2026-07-27: it never causes an under-flag, only an occasionally domain-imprecise rationale on an already-correctly-flagged conflict; see ARCHITECTURE.md Known Debt / ADR-016
- [x] Non-idempotent multi-package HITL loop fully closed (2026-07-28, commit `ff91b3b`, ADR-022) — restructured `hitl_gate_node`'s interrupt-per-package loop into `hitl_prepare_node` / `hitl_route` / `hitl_gate_single_node`, fanned out via LangGraph's `Send()`, one checkpointed `interrupt()` per package instead of a shared loop that replayed `events.emit()` calls on resume. Verified 67/67 three times (sandbox, Donnie's machine, post-rebase); see ARCHITECTURE.md §5

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
| 5.85 — Second-pass review response (fail-open gaps in 5.5's own fixes) | ✅ | 2026-07-25 |
| 6 — Lock it in | ⬜ | |