# PROJECT PASSDOWN: Watchstander
## Civilian Shipyard OSHA Spatial & Temporal Deconfliction Agent Graph

**Last updated:** 2026-07-25 (later same day)
**Status:** Live on GitHub, CI now genuinely green — the graph import was broken and untested until this session's external-review response (see Section 9). ARCHITECTURE.md added; live spatial visualizer (Phase 5) built and demo-recorded. Phase 4 case-data expansion still open.

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

---

## 9. Session Notes — 2026-07-25 (later same day): External review response — broken graph import + unenforced HITL decision

**Where things stood coming in:** both public repos (this one and `cosmoai-adept`) went through an independent Fable-model code/architecture/security review, plus two external recruiter-perspective AI assessments (ChatGPT, Grok) that Donnie ran separately and brought back for comparison. Both recruiter assessments praised this repo's HITL gate as one of the two strongest architectural signals in the whole portfolio ("the workflow cannot proceed without human authorization") — true in the narrow sense that execution genuinely pauses, but Fable's actual code trace found the pause and the answer weren't the same guarantee.

**What got found and verified before fixing:**
- **`graph.py` didn't import on a clean install.** `from langgraph.checkpoint.sqlite import SqliteSaver` needs the separate `langgraph-checkpoint-sqlite` package, never declared in `pyproject.toml`. Reproduced directly in a fresh virtualenv containing only `langgraph`/`pydantic`/`websockets`: `ModuleNotFoundError` on `import agent_core.graph`. Compounding factor: no test in the repo ever imported `graph.py` or `hitl.py` — the green CI badge was masking a broken build of the flagship assembled graph, the exact thing "clone it and run it" would hit first.
- **The HITL decision wasn't structurally enforced.** `hitl_gate_node` genuinely blocked on `interrupt()` (real, not simulated — that part was never in question), but the human's answer was recorded only as a string appended to `conflict_rationale`. "Approve" and "reject" produced byte-identical `WorkPackageState` output on every other field. ARCHITECTURE.md's old §5 claimed "nothing downstream of a flag can execute without it" — true only because nothing downstream existed yet to check anything.

**What got built:**
- `pyproject.toml` — added `langgraph-checkpoint-sqlite>=2.0` as an explicit dependency.
- `state.py` — new `HitlDisposition` enum (`APPROVED`/`REJECTED`/`INVALID`); `WorkPackageState` gained `hitl_disposition` (the parsed verdict, `None` until a review happens) and `cleared_for_execution` (the field a real downstream consumer must check — defaults `True` for packages that never needed review, `False` only on rejection or an unparseable answer).
- `hitl.py` — new `_parse_decision()` (case-insensitive prefix match on "approve"/"reject", anything else fails closed to `INVALID`); `hitl_gate_node` now sets both new fields and includes the parsed disposition in the `hitl_decided` event payload, not just the raw string.
- `tests/test_graph.py` (new) — builds the real graph via `build_graph()` and drives a full `entry -> deconfliction -> reasoning -> hitl_gate -> END` invocation through a genuine `interrupt()`/`Command(resume=...)` cycle with `MemorySaver`. This is the literal regression test for the import bug — it would have caught it on day one.
- `tests/test_hitl.py` (new) — 7 tests covering the disposition parser directly plus the full approve/reject/ambiguous/no-review-needed/critical-risk cases through the real compiled graph.
- 34/34 tests passing (up from 24). Verified the import fix in an isolated clean virtualenv both ways: fails without the dependency (reproducing the bug), succeeds with it (confirming the fix).
- ARCHITECTURE.md §5 and §7 rewritten to explain why these fixes exist; ADR-007/008 added. Known Debt gained the non-idempotent multi-package `interrupt()` loop (a real, more involved issue Fable also found — deliberately *not* fixed in this pass, disclosed instead of silently deferred) plus two domain-correctness gaps from the same review: "temporal deconfliction" is claimed in the README/docstrings but `scheduled_start`/`scheduled_end` are never read by `check_conflict()`, and there's no adjacency tolerance on frame ranges, so the "adjacent uncleared space" scenario `INCOMPATIBLE_HAZARD_PAIRS`'s own comment cites as motivating isn't actually caught.

**Decided but not built:**
- The non-idempotent HITL loop under multiple simultaneously-flagged packages — real issue, larger fix (restructuring to interrupt once per invocation rather than once per package), out of scope for this pass and tracked honestly in Known Debt.
- Temporal deconfliction and frame-range adjacency tolerance — both real domain-correctness gaps, both left for a future session since they're feature work, not defects in what's already shipped.
- cosmoai-adept received its own review-response fixes this session (sandbox trust boundary, quick-start crash) — see that repo's PASSDOWN.md; not duplicated here since the two repos' gaps were unrelated.

**Open questions for next session:** should the HITL loop restructure happen before or after Phase 4's case-data expansion? Given three independent reviewers now flagged an eval harness as the highest-leverage next investment across both repos, is that still the right next priority over closing Known Debt items surfaced this session?

---

## 10. Session Notes — 2026-07-25 (later still): Evaluation harness

**Why this session happened:** the 5.5 session above closed two acute defects (broken graph import, unenforced HITL decision) but left the domain-correctness gaps the same review surfaced — no adjacency tolerance, `deck_level` never used, `is_over_side` mislabeled in rationale text, the debatable `{WORKING_ALOFT, FALL_PROTECTION}` hazard pair — as prose in ARCHITECTURE.md's Known Debt table, not as anything CI actually measured. Donnie's framing going into this, verbatim, is worth keeping here rather than paraphrasing: *"I WANT failures to be seen in the repo because it shows that we don't have perfect code or agents, and I welcome, in fact I love those problems because they make me smarter, and the AI smarter, and we can demonstrate actually, in real time how we deal with design and security issues... The difference is I can eat that, then move forward and make it better than it was."* That's the design brief for this harness: quantify the gaps honestly, check the number into git, and let a future session's diff on that number be the story of improvement — not a repo that quietly stops mentioning problems once they're found.

**What got built:**
- `eval/scenarios.py` — 14 hand-authored conflict-detection scenarios (true positives across the hazard-pair and vertical-stacking paths, true negatives, a frame-boundary-touching edge case, a multi-conflict-per-package case) plus 7 case-retrieval scenarios run against the real `case_data/cases_v1.json` (not synthetic data) — including all three `fall_protection` cases individually distinguished by query text, which is the exact "real choice to make" scenario `retrieval.py`'s own docstring cites as its reason to exist.
- Four scenarios are known gaps *by design*, not oversights: `gap-adjacent-frames-not-touching`, `gap-two-aloft-packages-stacked`, `gap-simultaneous-confined-space-entries` (all false negatives already named in Known Debt), and `debatable-aloft-fall-protection-compliant-config` (the questionable hazard pair). A fifth, `rationale-over-side-labeled-overhead`, measures the `is_over_side` mislabeling as a literal substring check on the generated rationale text rather than leaving it as something a human has to notice by reading.
- `eval/run_eval.py` — runs the real pipeline (no mocks) and produces a metrics dict; `--write-baseline` regenerates `eval/baseline.json`, `--json` prints raw metrics, default prints a human report. Asserts `ANTHROPIC_API_KEY` is unset so the reasoning check always exercises the deterministic-fallback path.
- `eval/baseline.json` — checked in from a reviewed run: 14/14 conflict scenarios and 7/7 retrieval scenarios match their documented expected behavior; 10/14 conflict scenarios are domain-correct (the other 4 are the known gaps above).
- `tests/test_eval_harness.py` — 6 tests: baseline file exists and parses, live run matches baseline exactly, every scenario's own `expected_conflict`/`expected_case_id` claim still holds against live code, the set of known-gap IDs is exactly the documented four (so a silent fix or a silent new regression both fail loudly instead of passing quietly), and the reasoning deterministic-fallback path is grounded and provenance-tagged.
- 40/40 tests passing (up from 34).
- ARCHITECTURE.md — new `eval/` row in Components, a full paragraph in §7 Test Strategy explaining the harness and why it's distinct from unit tests, Known Debt rows cross-referenced to the specific scenario IDs that quantify them, ADR-009. MIGRATION.md — new Phase 5.75, Phase 6 checklist gained two items (deck_level unused, is_over_side rationale wording) and checked off the harness item.

**Decided but not built:**
- Did not build a corresponding eval harness for cosmoai-adept (tool-selection accuracy, approval-compliance rate) — ChatGPT's reassessment named it as valuable there too, but this session's explicit scope was "start the evaluation harness" for the repo with the most safety-critical surface area; cosmoai-adept's harness is a separate, not-yet-scheduled piece of work.
- Did not implement temporal deconfliction or fix the non-idempotent multi-package HITL loop this session — both were on the table (per the AskUserQuestion decision that chose the eval harness instead) and remain open, tracked in MIGRATION.md Phase 6 and ARCHITECTURE.md Known Debt.
- Did not add adjacency tolerance, deck_level-aware stacking, or fix the is_over_side rationale wording — the harness's entire point this session was to measure these gaps precisely, not close them yet. Closing any one of them is now a one-line change plus a `--write-baseline` regen plus a reviewed diff, which is the intended workflow going forward.

**Open questions for next session:** of the now-quantified gaps (adjacency tolerance, deck_level/z-axis stacking, is_over_side rationale wording, the debatable hazard pair, temporal deconfliction, the non-idempotent HITL loop), which is highest-leverage to close next? Should cosmoai-adept get its own eval harness before or after any of Watchstander's remaining gaps are closed?

---

## 11. Session Notes — 2026-07-25 (still later): Second-pass review response — fail-open gaps in this session's own fixes

**Why this session happened:** Donnie shared a Gemini "recruiter lens" assessment of both repos, which — Gemini admitted when pressed to actually trace code instead of pattern-match on repo/file names — was written without ever fetching the GitHub URLs; it hallucinated a description of this repo's purpose (guessed "duty-cycle"/"scheduled task loop" behavior from the name "Watchstander" rather than reading what the code does) and missed that cosmoai-adept's README already had the Mermaid diagram it recommended adding. Rather than relay files back and forth with Gemini manually, a second independent Fable-model pass was run directly against the three files Gemini itself had asked to see (`state.py`, `deconfliction.py`, `hitl.py`) — cold, no prior context, specifically told to line-trace logic paths and trust boundaries rather than accept anything at face value. It found real gaps in the disposition-enforcement fix from the Section 9 session above, plus two pre-existing bugs in `deconfliction.py` nobody had caught yet.

**What got found and verified before fixing:**
- **`cleared_for_execution` still defaulted open in a real window.** Section 9's fix added the field, but its `True` default applied not just to packages that never needed review — it also covered a `RiskLevel.CRITICAL` package from the moment it's constructed (before deconfliction even runs) and a flagged package in the gap between `deconfliction_node` setting `requires_hitl_review = True` and `hitl_gate_node` actually running. Any consumer checking only `cleared_for_execution` — exactly what its docstring says to do — would read an unreviewed conflict as cleared in that window.
- **The disposition parser was fail-open on hedged text.** `_parse_decision("approve only if the marine chemist re-certifies")` and `_parse_decision("approve?? absolutely not")` both returned `APPROVED`, because both start with the literal substring "approve" and the parser was a pure prefix match.
- **`conflict_rationale` silently dropped information.** A package conflicting with two others kept only the last pair's rationale text (overwrite, not accumulate) even though `.conflicts` itself stayed complete — and re-running `find_all_conflicts` on the same objects (retry, checkpoint replay) had no idempotency guard, so it would append duplicates.
- **The overhead/underlying rationale label was positionally wrong.** `check_conflict()` unconditionally named its first argument "Overhead work," regardless of which package actually carried `is_aloft`/`is_over_side` — wrong whenever the non-overhead package happened to be first.
- **`hitl_decided` broadcast the reviewer's raw text**, violating `events.py`'s own "ids/flags/provenance tags only, never raw content" policy.

**What got built:**
- `state.py` — new `model_validator` forces `cleared_for_execution = False` at construction time for an unreviewed `CRITICAL` package.
- `deconfliction.py` — `deconfliction_node` now also sets `cleared_for_execution = False` the instant it flags a conflict, closing the post-flagging half of the same gap. New `_record_conflict()` helper replaces the direct-overwrite append logic: accumulates rationale text instead of overwriting, and is idempotent on repeated invocation. `check_conflict()` now computes the actual overhead party instead of assuming argument position.
- `hitl.py` — `_parse_decision()` gained a negation/conditional-cue check (`" not "`, `"n't"`, `" unless "`, `" only if "`, etc.) scanned against the *leading words* of the answer, ahead of the prefix match. Bounding it to leading words was itself a mid-session fix: an initial version scanning the whole string wrongly flagged legitimate trailing rationale like "reject - the permit hasn't been signed off" as `INVALID`, caught by the new test suite before being shipped. `hitl_decided`'s event payload dropped `decision=str(decision)`, keeping only the parsed `disposition`.
- `visualizer/demo_broadcaster.py` and `Main.gd` updated to match the new `hitl_decided` payload shape (disposition instead of raw decision text); `visualizer/README.md`'s event table updated.
- 10 new tests: `tests/test_state.py` (new file, 3 tests), `tests/test_deconfliction.py` (+4: label-order, rationale accumulation, idempotency, deconfliction_node-level fail-closed), `tests/test_hitl.py` (+3: negation-cue rejection, trailing-rationale-still-works, no-raw-text-in-event). 50/50 passing, up from 40.
- Re-ran `eval/run_eval.py` after all fixes: baseline unchanged (the harness only captures booleans/counts, not raw rationale text or event payloads, so none of these fixes moved the numbers — confirmed rather than assumed).
- ARCHITECTURE.md §5 gained five explanatory paragraphs; Known Debt's HITL-loop and `is_over_side` rows updated to reflect what's now partially mitigated vs. still fully open; ADR-010 through ADR-013 added. MIGRATION.md gained Phase 5.85.

**Decided but not built:**
- The deeper semantic question of whether `is_over_side` should count as "overhead" at all (per the original Fable finding: over-the-side hangs *below* the deck edge, so treating it identically to `is_aloft` is domain-backwards) remains open — this session only fixed *which* package a correct-or-not label points at, not the underlying model.
- The non-idempotent multi-package HITL loop is now partially mitigated (`conflict_rationale`'s append is guarded) but not fully closed — the `events.emit()` calls in the replayed interrupt path still aren't idempotent. Still needs the interrupt-once-per-invocation restructure noted since Section 9.
- cosmoai-adept received its own second-pass fixes this session (memory checkpointer moved outside the sandbox, the `_assert_no_model_controlled_sandbox()` guard hardened against two fail-open gaps, two `config.py` hardening fixes) — see that repo's PASSDOWN.md.

**Open questions for next session:** is it worth formalizing "ask an independent reviewer to trace N specific files cold" as a repeatable pattern, given it's now found real issues twice in a row — once against the original code (Section 9), once against this session's own fixes to that code? What's the actual next highest-leverage item: the interrupt-loop restructure, the `is_over_side` semantic fix, or one of the eval-harness-quantified gaps from Section 10?
