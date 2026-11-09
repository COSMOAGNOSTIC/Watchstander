# PROJECT PASSDOWN: Watchstander
## Civilian Shipyard OSHA Spatial & Temporal Deconfliction Agent Graph

**Last updated:** 2026-08-08
**Status:** Live on GitHub, CI genuinely green. Live spatial visualizer (Phase 5) built and demo-recorded, now on a real ACUSHNET Inboard Profile background with a switchable Deck Plan alternate view (Phase 9, see Section 16) after a WebSocket connectivity bug and a wrong-sheet-type mismatch were both caught by Donnie actually running it; a real HITL reviewer web app (Phase 7, `reviewer/`) now exists too — see Section 14, the visualizer's status-only view had no human-facing decision interface until that session. Phase 4 case-data expansion and Phase 6 ("Lock it in") still open. A real in-Godot render of the visualizer is still owed (Known Debt, carried since Phase 8).

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

---

## 12. Session Notes — 2026-07-25 (still later): Stale-doc fix caught by Grok review

**What happened:** an independent Grok review of both repos (run after the AOSE.md addition) correctly flagged that ARCHITECTURE.md §8 still said "design recorded here, implementation in progress" for the visualizer, even though Phase 5 in MIGRATION.md has been marked substantially complete since earlier today. Spot-checked several of Grok's other specific claims (the `pyproject.toml` dependency-pinning gap, the `is_over_side` semantic note, the TOCTOU item's actual location in cosmoai-adept) against the real files before trusting any of it — all checked out accurately, unlike the earlier Gemini assessment.

**What got fixed:** ARCHITECTURE.md §8's status line corrected to match reality, with a note explaining *why* it went stale (this project's own Maintenance Rules say "if the doc and the code disagree, the doc is the bug," and this is a live instance of exactly that). MIGRATION.md Phase 6 checklist updated to record the fix.

**Decided but not built:** the rest of Grok's list (temporal deconfliction claim vs. implementation, porting the eval harness pattern to cosmoai-adept, dependency pinning on both repos, closing the HITL loop's remaining non-idempotency) was deliberately left for a future session — Donnie chose the cheap, honest doc fix only this round rather than opening a larger scope.

**Open questions for next session:** same as Section 11's close — which of temporal deconfliction, the HITL loop restructure, or porting the eval harness to cosmoai-adept is the next highest-leverage move.

---

## 13. Session Notes — 2026-07-25 (still later): CI red since the eval harness landed — packaging bug, not a code bug

**What happened:** Donnie noticed GitHub Actions showing red for Watchstander and asked. The actual failure: `ModuleNotFoundError: No module named 'eval'` in `tests/test_eval_harness.py`, on every run since the eval harness was added (Phase 5.75) — several commits' worth of red CI that nobody, including this session's own "verify in a clean venv" checks, had caught.

**Root cause:** `eval/` was added as a plain directory with an `__init__.py` but never registered in `pyproject.toml`'s `[tool.setuptools.packages.find]` list — only `agent_core*` was. That made `eval` importable only by accident: `python -m pytest` prepends the current working directory to `sys.path`, so every local run this session (all invoked as `python -m pytest`) resolved the import fine. CI's workflow runs the `pytest` console-script entry point directly (`Run pytest -v` in the Actions log), which does not add the cwd to `sys.path`, so it failed every time. Confirmed by reproducing the exact failure locally with a plain `pytest -v` invocation in a fresh venv, then confirming the fix the same way — not with `python -m pytest`, which would have hidden the bug all over again.

**What got fixed:** `eval*` added to `pyproject.toml`'s `packages.find`, same treatment as `agent_core`. Verified in two freshly created virtualenvs (Python 3.11 and 3.12), fresh `pip install -e ".[dev]"`, invoked as plain `pytest -v` to match CI exactly — 50/50 passing both times.

**Why this matters beyond the one-line fix:** none of the AI review passes this session — two independent Fable passes, plus Gemini's and Grok's assessments — caught this, because none of them ran the actual CI command; they all read code, not execution behavior under the exact invocation CI uses. This session's own local verification also didn't catch it for the same reason: it always ran `python -m pytest`, which papered over the exact gap. AOSE.md gained a new section on this specifically, because it's a live instance of the document's own principle — re-running a check the same way you always have isn't verification — aimed at this session's own habits rather than at an external AI reviewer for once.

**Decided but not built:** did not add a CI-mirroring pytest invocation to the local dev workflow (e.g. a Makefile target or pre-commit hook that runs plain `pytest`, not `python -m pytest`) — worth considering for a future session so this class of gap can't recur silently.

**Follow-up, same session:** checked cosmoai-adept for the same class of bug before closing this out. It uses `setup.py`'s `find_packages()` with no include filter (unlike Watchstander's `pyproject.toml`, which explicitly lists `agent_core*`), so any future top-level package there gets auto-registered — no equivalent gap exists. Confirmed by a fresh-venv install and a plain `pytest -v` run (CI's exact invocation): 59/59 passing. No changes needed on that repo.

---

## 14. Session Notes — 2026-08-08: Real HITL reviewer web app (Phase 7)

**Status:** Phase 7 done. 133/133 tests passing (127 → 133, all new: `tests/test_reviewer.py`).

**Where this came from:** Donnie ran the visualizer live for the first time this session (previously he'd only seen the 3D blockout once, weeks ago, and had never watched the live 2D view or the graph do anything in real time). After watching it — packages placed, a conflict flagged red, the Safety Review station pulsing — he asked two direct questions: where's the data explaining *why* a package was flagged, and where's the actual human decision interface. Both answers were the same honest gap: `events.py`'s broadcast policy deliberately keeps that content off the visualizer's WebSocket (correct, by design — Section 8/ADR-013), but nothing in the repo had ever built the *other* half — a real place for a human to read the full brief and answer the real `interrupt()`. The only things that had ever resolved a real `interrupt()` before this session were `tests/test_graph.py`/`test_hitl.py` (hardcoding `"approve"`) and `demo_broadcaster.py` (which doesn't touch the real graph at all, just replays a scripted event sequence). His framing, verbatim in spirit: a status light with no lever to pull is pointless — a real reviewer needs to see the flagged problem, see the deterministic-vs-LLM reasoning, and have an actual interface to record their decision.

**What got built:** `reviewer/` — a local FastAPI app, real `build_graph()` behind it, a persistent `SqliteSaver` (not `MemorySaver`, which every existing test uses and which would lose all pending state on process restart) so a review queued in one HTTP request survives to be decided in a separate later one. Dashboard lists pending reviews and recently-decided packages; a detail page shows the full description, conflict rationale, synthesized safety brief, and its provenance tag (`[SOURCE: LLM SYNTHESIS]` vs. `[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]` — literally the "LLM online/offline" signal Donnie asked about); a real Approve/Reject form whose submit calls `graph.invoke(Command(resume={interrupt_id: decision_text}), config=...)`, genuinely resuming the paused graph, not simulating a decision. `agent_core/demo_fixtures.py` (new) holds the real ACUSHNET compartment/frame demo data as actual `WorkPackageState` objects; `visualizer/demo_broadcaster.py` now derives its scripted event-payload dicts from this same source instead of duplicating the data by hand, so the two demo paths can't drift.

One real bug found by testing the actual approve flow, not by code review: `state.tasks[i].interrupts` keeps listing a `Send()`-fanned-out task's original `Interrupt` object even after that task has been resumed and completed — `task.result` being non-`None` is what actually distinguishes "done" from "still genuinely paused." The first version of `list_pending_reviews()` didn't check this, so an approved package never left the dashboard's pending list even though the underlying graph state was correct. Caught by `test_approving_one_package_leaves_the_others_pending` actually running the flow end-to-end through FastAPI's `TestClient`. Fixed by skipping any task where `task.result is not None`. Full writeup: ARCHITECTURE.md §8.5, AOSE.md.

Also verified against a genuinely live running server (`uvicorn` + `curl`), not just the in-process `TestClient` — seeded a real demo run, confirmed all three expected packages (`HW-2201`, `CS-2202`, `ALOFT-2203` — a real, previously-undocumented third conflict from `_vertically_stacked()`'s frame-range overlap with `HW-2201`, not staged) showed up, and pulled a detail page's rendered HTML directly to confirm the brief and provenance tag actually appear.

**Not done, deliberately:** no auth (fine for one local reviewer on their own machine, the same trust boundary the visualizer's undefended WebSocket already assumes — disclosed as Known Debt, not hidden); no real work-package intake form yet (the only way to create a pending review is "seed the ACUSHNET demo" — a real intake form or API endpoint is a natural next step); no live-updating dashboard (refresh to see new state, unlike the visualizer's WebSocket push).

**Next up:** either build real intake for `reviewer/` (a form, or an API a scheduling system could POST to) so it's not demo-data-only, or return to Phase 6 ("Lock it in")'s remaining open items (README staleness, adjacency tolerance, `deck_level` actually used in conflict detection) — not decided this session.

---

## 15. Session Notes — 2026-08-08 (later same day): Real HAER print swapped in as the 2D visualizer background (Phase 8)

**Status:** Phase 8 done, pending one disclosed follow-up (a real Godot render — see below).

**Where this came from:** Immediately after Phase 7 (the reviewer app), Donnie's next ask was direct: the generic Godot visualizer is fine, but "in reality, we want to see the prints themselves, 2d or 3d... whichever is faster right now, probably 2d." He explicitly flagged not wanting bloat — the fastest real path, not a rebuild.

**What got built:** `visualizer/assets/bg_acushnet_deckplan.png` — a real capture of the Library of Congress's own copy of the ACUSHNET HAER Sheet 5/10 "Deck Plans" drawing (Main Deck + Second Deck, with the sheet's own printed frame scale), sourced by navigating to the LOC image URL in a live, user-connected Chrome browser (this sandbox's own network egress blocks `tile.loc.gov` directly — same class of restriction this project has hit before with Hugging Face and osha.gov) and screenshotting it, then cropping the browser chrome out in Python/PIL. `Main.gd` now loads this image as its background instead of the generated `bg_blueprint.png`, and its frame-to-x / deck-to-y calibration constants were recalibrated by measuring pixel positions directly off this specific image (the sheet's own 0-220 ft scale bar, the two deck rows' vertical centers) — to the same "approximately right, not survey-accurate" bar the rest of this project's frame-range readings already use.

One real, disclosed design consequence: the real print has the bow on the right and stern on the left — the opposite of the old procedural schematic's left-to-right-increasing-frame convention. Mirroring the image to preserve the old direction would have mirrored its own printed text into backwards, unreadable ship name/deck labels/frame numbers — so `X_MIN`/`X_MAX` were swapped instead (the existing linear interpolation in `_frame_to_x()` handles either direction with no formula change), keeping the real print's own orientation intact and readable.

**Verification, and its real limit:** no Godot is installed in this build sandbox, unlike the 3D blockout work (ADR-019), which had one available and got an actual headless-render screenshot. Instead, built a Python/PIL mockup that reproduces `Main.gd`'s exact new calibration constants against the real background image and the real ACUSHNET demo fixture data — confirmed the fall-protection package (frame 2-12, near the bow) lands near the right/bow end of the Main Deck row, matching its real Anchor Windlass Room compartment, before shipping. A real substitute check, not skipped — but a genuinely lower bar than an in-engine screenshot, and disclosed as Known Debt (ARCHITECTURE.md) rather than presented as fully verified.

**Not done, deliberately:** the 3D companion view (`Main3D.tscn`) still uses its own simplified geometry, not this real print — Donnie's own framing ("whichever is faster right now, probably 2D") scoped 3D texture-mapping out of this session.

**Next up:** open the scene in an actual Godot editor (on Donnie's machine) and confirm the mockup's calibration holds up on a real render — true up any offset that doesn't match. After that, either the `reviewer/` real-intake-form follow-up from Phase 7, or Phase 6's remaining open items.

**Open questions for next session:** worth considering whether Watchstander's explicit `include=[...]` list in `pyproject.toml` should switch to `find_packages()`-style auto-discovery (matching cosmoai-adept) specifically so this class of bug can't recur the next time a new top-level package is added and someone forgets to list it.

---

## 16. Session Notes — 2026-08-08 (later still): connectivity fix + Inboard Profile default view + switchable views (Phase 9)

**Status:** Phase 9 done, pending the same real-Godot-render follow-up carried over from Phase 8.

**Where this came from:** Donnie applied Phase 8's patch and actually ran it on his own Windows machine — the real print rendered correctly, but nothing else happened: no markers, no live update, even after re-running `demo_broadcaster.py` twice. Separately, once he saw the static print he pushed back hard on what it was actually showing: "you gave a top down drawing, the animation underneath is still the original we've been looking at for weeks. It visually has nothing to do with the drawing you put on top of it." Both turned out to be real, distinct bugs.

**Bug 1 — connectivity.** `agent_core/events.py`'s server and `Main.gd`'s client both connected to the hostname `"localhost"`. On a dual-stack machine (Windows in particular) that hostname can resolve to a different address family on each side — both sockets open without error, neither raises, and no data ever crosses. This bug predates today's work entirely; it's the same reason nothing happened the very first time Donnie ran the old schematic version, weeks ago. Fixed by pinning both sides to the literal loopback address `127.0.0.1`. The HUD status line was also just static text before this — it never actually reflected connection state, which is why the symptom was indistinguishable from "nothing is happening yet." It now tracks and shows live state (orange "not connected -- retrying" / green "connected"). Regression test added: `tests/test_events.py::test_default_host_is_the_literal_loopback_address_not_a_hostname`.

**Bug 2 — wrong sheet type.** Donnie's critique was correct: a HAER "Deck Plan" sheet (Sheet 5/10, used in Phase 8) is a top-down floor plan. `Main.gd`'s band scheme (ALOFT/MAIN DECK/2ND DECK/HOLD/WATERLINE, stacked vertically) is a side-cross-section metaphor. Only two of the five bands (Main Deck, 2nd Deck) had any real corresponding row on that sheet — the other three were floating in the margin, disconnected from anything actually drawn. Fix: sourced HAER Sheet 3/10, "Inboard Profile" — a genuine side cross-section with compartments stacked by real deck height and the sheet's own printed frame scale — and made it the new default. Every one of the five bands now corresponds to a real row on this sheet. Calibrated independently (different image, different pixel scale from Sheet 5 — not the same constants reused), and cross-checked against `docs/uscg-acushnet-ars9-source.md`'s already-known compartment identities (Lazarette lands aft-most, Forepeak Tank lands forward-most, matching their real names) since this image's native resolution makes the smallest printed frame-tick numbers illegible to read directly.

**The feature Donnie asked for on top of the fix:** rather than just discard the now-wrong-default Deck Plan sheet, Donnie asked directly for the ability to cross-reference a flagged conflict against more than one real angle of the ship. Both sheets now ship, switchable at runtime with the **V key** (`Main.gd`'s new `VIEWS` array and `_toggle_view()`), each with fully independent calibration (frame-to-pixel, deck-to-pixel, background position/size, label positions, Safety Review station position). Toggling re-lays-out whatever data was last received (`last_work_packages`/`last_conflicts`/`hitl_awaiting_id`, now tracked as scene state) against the newly active view, rather than resetting the scene — switching mid-review doesn't lose what's on screen.

**Verification, and its real limit (same caveat as Phase 8):** still no Godot in this build sandbox. Verified with a Python/PIL mockup reproducing `Main.gd`'s exact per-view constants against the real ACUSHNET demo fixture data for both views — all four demo packages (`HW-2201`, `CS-2202`, `ALOFT-2203`, `FALL-2204`) land in geographically plausible positions on both sheets, notably `FALL-2204` (frame 2-12, the real Anchor Windlass Room) landing right at the bow on both. A real check, not skipped — but still a lower bar than an actual in-engine render, disclosed as Known Debt exactly as Phase 8's was.

**Not done, deliberately:** the 3D companion view (`Main3D.tscn`) is unchanged, same scope call as Phase 8.

**Next up:** the real Godot render is now overdue across two phases — worth prioritizing next time Donnie has the editor open, specifically checking both views (not just the default) since the Deck Plan view's calibration wasn't re-verified this session, only re-confirmed unchanged from Phase 8. After that, either `reviewer/`'s real-intake-form follow-up, or Phase 6's remaining open items.

**Addendum, same day — confirmed live end-to-end, then two more direct fixes:** Donnie tested the Phase 9 patch on his own machine. The connectivity fix worked, but `demo_broadcaster.py`'s blind `time.sleep(3)` plus exit-immediately-after-replay meant its server (a daemon thread) could die before Godot even connected if there was any real-world delay switching windows — fixed by having it wait for an actual client and stay running afterward. Once connected, markers rendered for the first time ever against a real print, and the result was reported directly: "it looks like a colored smudge... the color palette is wrong and hard to see on a white background... make the pinpoints not look like an ink smudge." Both the pastel `HAZARD_COLOR` palette and `gen_assets.py`'s `glow_sprite()` (a soft Gaussian blur) were tuned for the old dark schematic background and never re-tuned for the real white print — fixed with the Okabe-Ito colorblind-safe palette and a new crisp `marker_pin()` asset (ADR-028), plus labels switched to fixed dark text with a white outline for legibility regardless of hazard color. Not yet re-confirmed live by Donnie as of this note.

---

## 17. Session Notes — 2026-08-21: Phases 10-11

**Status:** Phase 10 mostly done (reschedule suggestion, declarative rule config + audit primitive, perf benchmark, all with regression tests, 101/101 full suite passing). Phase 11 (visualizer manual-insert interaction) scoped and designed, not built.

**Note (2026-08-21):** a related prototype, built on Watchstander's own architecture, was demonstrated to outside stakeholders aligned with the project on 2026-08-20; the resulting minutes surfaced five concrete things worth pulling into Watchstander itself, ranked and built in priority order this session, in a cloned sandbox (this build environment has no Godot, so anything needing the visualizer stayed design-only -- see Phase 11).

**1. `agent_core/reschedule_suggestion.py` (ADR-030).** A flagged conflict previously came with only a rationale for why it was blocked, never a concrete alternative. `suggest_reschedule()` closes that gap with a bounded, deterministic nearest-offset search, re-using `deconfliction.py`'s own `check_conflict()` and `_fire_watch_capacity_conflicts()` rather than reimplementing them. Deliberately not built on OR-Tools CP-SAT (already flagged in Section 9's Extraction Candidates table for the *harder* temporal chit-expiration problem) -- this is a single-package bounded search, not a joint optimization, and Design Principle 7 (ADR-020/021) already commits this repo to evaluating before reaching for a dependency the problem doesn't need. Never mutates state, never auto-applies. Not yet wired into `reasoning_node`/`SafetyBrief` or the reviewer UI -- disclosed as Known Debt, two integration points identified.

**2. ADR-031 — hard constraint vs. soft preference, named explicitly.** Authorization windows (a chit's or tag-out's `valid_until`) constrain what's physically or legally permitted; schedule timing is a preference about when work happens within what's permitted. This distinction was already true of how the codebase behaves; it hadn't been stated as its own architectural principle before. Pure documentation, no code change -- the point is that future scheduling-adjacent code (a chit-expiration engine, a multi-package resequencer) inherits the rule at design time instead of re-discovering it.

**3. `agent_core/rules_config.py` + `case_data/hazard_rules_v1.json` + `agent_core/rules_audit.py` (ADR-032).** `deconfliction.py`'s hazard-pair rules and fire-watch capacity limit are now schema-validated declarative data, not hand-typed Python constants -- an unrecognized hazard category, a self-paired rule, or a non-positive limit fails loudly at load time. Both original constant names kept in `deconfliction.py` unchanged, so nothing else in the codebase needed to change. `rules_audit.py` is an append-only JSONL primitive (who/when/field/old/new/reason) for a future rule-editing tool to call -- nothing calls it automatically yet, since that tool doesn't exist, disclosed as Known Debt rather than left implicit.

**4. `eval/perf_benchmark.py` (ADR-033).** Watchstander had no benchmark on record for detection speed -- `eval/`'s existing harness scores correctness only, never speed. Deliberately kept separate from `eval/run_eval.py`'s output, which `tests/test_eval_harness.py` asserts for exact equality against a checked-in baseline -- mixing non-deterministic wall-clock timing into that dict would make the regression gate flaky by construction. First run: 200 synthetic packages, 19,900 pairwise checks, 57 flagged, **0.0113 seconds, zero LLM calls, zero network access**.

**5. Phase 11 — visualizer manual-insert interaction.** Scoped in MIGRATION.md, not built. This build sandbox has no Godot installed (same limitation ADR-019/ADR-025 already disclosed) -- writing untested `.gd` scene code here risks handing back something that looks plausible but silently doesn't run. Left as a ready-to-pick-up design instead.

**Verification this session:** 101/101 tests passing in a clean sandbox venv (`.venv/bin/python -m pytest -q -k "not retrieval"`, retrieval's heavier optional deps not installed this session -- unrelated to any change made). New test files: `test_reschedule_suggestion.py` (6), `test_rules_config.py` (7), `test_rules_audit.py` (4), `test_perf_benchmark.py` (2) -- 19 new regression tests total, all exercising real code paths, none mocked.

**Not done, deliberately:** the two Phase 10 integration points (suggestion -> `SafetyBrief`, suggestion -> reviewer UI) and the rule-editing tool itself (no GUI exists yet) -- all next steps, all disclosed as Known Debt rather than silently skipped. Phase 11 needs Donnie's own machine, where Godot is actually installed.

**Next up:** either of the two Phase 10 integration points (suggestion surfaced in the reviewer app is probably the highest-leverage next demo moment), or Phase 11's visualizer interaction once there's Godot access to verify against. Full technical feedback on the demo minutes themselves is logged separately outside this repo, not duplicated here.

---

## 18. Session Notes — 2026-08-21 (same day, continued): AOSE Round 6 -- independent Fable + Opus cross-review of Session 17's work

**Status:** Both reviews complete. AUD-10 fixed and regression-tested. ADR-031's false claim corrected in place. Remaining findings logged as Known Debt, not fixed this pass -- deliberately, not silently.

**Why this round happened:** Donnie asked directly whether it was time for an independent Opus or Fable run on Session 17's work. Per this repo's own hard rule from Round 5 ("the model that finds a bug never writes its fix") and the RE-TRACE routing rule (`claude/aose-model-routing-registry.md`: "the fix gets traced cold by a different session or model that did not write it"), the answer was yes by the repo's own standard -- nothing built in Session 17 had been independently traced yet. Two reviewers ran in parallel, each scoped to a different question:

- **Fable** — cold line-trace of the full diff (`reschedule_suggestion.py`, `rules_config.py`, `rules_audit.py`, `deconfliction.py`'s refactor, `eval/perf_benchmark.py`, and all new tests). Matches its established strength in this repo's registry: highest precision on record, zero fabrications across three prior rounds.
- **Opus** — independent architectural judgment on ADR-030's one debatable call (hand-rolled search vs. OR-Tools CP-SAT), not a line-level bug hunt.

### Fable verdict table

| ID | Claim | Verdict |
|---|---|---|
| AUD-10 | Pre-existing, unrelated fire-watch violation makes `suggest_reschedule` reject every offset | CONFIRMED (ran it) -- fixed this session, see ADR-034 |
| AUD-11 | `_shifted_copy` shares mutable `conflicts`/`spatial` objects with the original package (shallow `model_copy`) | CONFIRMED (ran it) -- latent, not firing today, no test guards it |
| AUD-12 | Docstring says missing `target_id` returns `None`; code raises `ValueError` | CONFIRMED (traced) -- code/test is the intended behavior, docstring is the bug, not yet corrected |
| AUD-13 | `schema_version` never validated against 1; unknown JSON keys silently ignored | CONFIRMED (ran it: version 999 + junk key loads clean) |
| AUD-14 | One truncated audit-log line makes every prior entry unreadable | CONFIRMED (ran it: `JSONDecodeError`) |
| AUD-15 | "Append-only" is convention, not enforcement | CONFIRMED by inspection |
| AUD-16 | Perf-benchmark docstring's conflict-count claim false at n=10 | CONFIRMED (ran it: 0 flagged at n=10) |
| AUD-17 | `_candidate_offsets` hangs on non-positive `step` | Traced, not run -- real, only reachable via caller misuse |
| AUD-18 | Duplicate `work_package_id`s silently drop from the validation set | Traced, unverified edge case |
| AUD-19 | Fire-watch branch of `suggest_reschedule` had zero test coverage | **CONFIRMED -- direct cause of AUD-10 shipping undetected; 2 regression tests added this session** |
| AUD-20 | One new test's ID-list assertion is trivially true | CONFIRMED by inspection |
| AUD-21 | Backward compatibility of the rules-config extraction (old hardcoded values vs. new JSON) | **VERIFIED CLEAN -- no drift** |
| AUD-22 | "Nearest offset wins" ordering at default args | **VERIFIED CLEAN** |

### Opus verdict (architectural, not itemized as AUD findings)

**Sound decision, wrong supporting arguments, incomplete in three ways.** Full detail:

1. Not using OR-Tools is the right call, but ADR-030's own justification ("materially smaller problem") is the weak argument -- the strong one is that `suggest_reschedule()` has exactly one decision variable (a scalar offset on one package), which makes it a 1-D linear scan, not a constraint-satisfaction problem at all. A solver would add zero search power here. Opus measured the actual scaling: 500 packages, 8-week window, 15-min steps -- 151ms for the pairwise-check path. No objection there.
2. **Measured performance cliff**, separate from the scaling question above: `_fire_watch_capacity_conflicts()` was built for one-time reporting (builds a full formatted string per violating pair) and gets called once per candidate offset inside the search loop, discarding the string every time. Measured directly: 74 seconds at 50 packages on one fire watch, ~72 minutes at 200 -- a 1,438x gap at n=200 that's pure discarded string formatting, not fundamental to the search. Logged as Known Debt, not fixed this session.
3. **"Nearest offset wins" is a plausible-sounding heuristic, not a validated objective** -- minimizing `|shift|` has no concept of shift boundaries, weekends, or the fact that moving earlier is usually harder than moving later operationally. Opus's own test runs got the search to recommend starting hot work nearly two days earlier than planned. `state.py` has no shift/calendar/movability model at all, so this isn't a quick fix.
4. **ADR-031 contained a false claim**, corrected in place this session (see ARCHITECTURE.md ADR-031's correction note): it said `reschedule_suggestion.py` already respects the hard-constraint/soft-preference distinction implicitly. Not relaxing a rule `deconfliction.py` enforces is not the same as respecting a constraint `deconfliction.py` doesn't model -- a chit's `valid_until` isn't represented anywhere in the schema today, so the search can suggest a shift landing outside a real authorization window without anything noticing.
5. **The travel-window comparison in ADR-030/031 is a single worked example, not a validated general case** -- it demonstrates asymmetric multi-party reasoning (which packages are movable, which aren't) that `suggest_reschedule()` doesn't actually have.
6. **Most important finding, not previously stated anywhere:** this module converts every existing `deconfliction.py` false negative (documented in §9 Known Debt -- adjacency tolerance, `deck_level` unused, same-category pairs that can't trigger `INCOMPATIBLE_HAZARD_PAIRS`) from a missed flag into an **active recommendation**. Worked example: `_vertically_stacked()`'s known gap means two aloft packages on the same frame range never conflict -- the search will therefore suggest a slot putting one aloft crew into exact simultaneity with another. A recommendation carries more implied authority than a silence. Logged as Known Debt this session; not previously disclosed in ADR-030.

Both reviewers independently confirmed the same reassuring floor: **nothing found is unsafe in the HITL sense** -- no path returns a suggestion that still actually conflicts by `deconfliction.py`'s own rules. Every real finding is either "the feature quietly stops working" (AUD-10, fixed) or "the suggestion could be operationally worse than it should be" (the objective-function gaps, disclosed, not yet fixed), not "a hazard gets missed and nobody's told."

**What got fixed this session:** AUD-10 only (`reschedule_suggestion.py`'s fire-watch check now scoped to violations naming the candidate), with two new regression tests (`test_unrelated_preexisting_fire_watch_violation_does_not_block_a_suggestion`, `test_fire_watch_violation_actually_involving_the_target_still_blocks_it`) -- 10/10 in `test_reschedule_suggestion.py`, full suite unaffected elsewhere. ADR-031's false claim corrected in place, struck visibly rather than silently edited, per this repo's own convention for handling a documentation error found after the fact.

**Deliberately not fixed this session:** the `O(M^3)` performance cliff, the objective-function/calendar-awareness gap, the docstring/code contradiction (AUD-12), the rules-config schema gaps (AUD-13), the audit-log truncation fragility (AUD-14/15), and the benchmark docstring's inaccurate claim (AUD-16) -- all logged as Known Debt rows in ARCHITECTURE.md rather than silently skipped. Donnie's own call, made explicitly: fix the one functional defect and the one factual documentation error now, log the rest, don't rabbit-hole the whole list in one sitting.

**Next up:** the performance cliff (Opus's finding) is probably the next highest-priority item if this module gets demoed against any hot-work-heavy scenario -- it's the one most likely to actually embarrass a live demo. After that, either of the two Session 17 integration points (suggestion -> `SafetyBrief`, suggestion -> reviewer UI), or Phase 11's visualizer interaction.


## 19. Session Notes — 2026-11-05: Upgrade Session 1 of 16 -- docs cleanup

**Branch:** `session-01-cleanup` (from `main` @ `aa3a4b5`). Not merged to `main`.
**Status:** Done. 169/169 tests passing (`pip install -e ".[dev,retrieval,reviewer]"` then `pytest -v`, same as CI; run locally on Python 3.13, CI matrix is 3.11/3.12).

**What changed** (commit `7607f26`, docs only -- `git diff --stat` confirmed only README.md, ARCHITECTURE.md, AOSE.md):
- README: license line corrected to Apache 2.0 (matches `LICENSE`); visualizer described as rendering over real HAER drawings, with a note that the demo GIF predates that; module list adds `reschedule_suggestion.py`, `rules_config.py`, `rules_audit.py`.
- ARCHITECTURE: header "Last updated" moved to 2026-08-21; the fire-watch raw-count Known Debt row marked CLOSED (the AUD-01 sweep-line, `_fire_watch_peak_concurrency()`, already fixed it), original text kept as history.
- AOSE: same fire-watch entry marked CLOSED; ADR range corrected to 001-034; numbering note explaining the two different "Round 6"s; new **Paused** banner -- the full adversarial loop is deferred for upgrade sessions 1-16. Interim practice: green CI before merge, the session that finds a bug never writes its fix, cross-model review at Session 11 (engine) and Session 16 (final), red-team pass after the web UI (Sessions 12-15).

**Verified before committing:** every factual claim in the patch checked against the code (`LICENSE` is Apache 2.0; `_fire_watch_peak_concurrency()` exists in `agent_core/deconfliction.py`; ADR-034 is the highest ADR; the three new modules and `case_data/hazard_rules_v1.json` exist).

**`phase7_hitl_reviewer.patch`:** left in place as instructed. Its contents are already in the repo -- every file it touches exists, and the only differing lines are later improvements (`submit_decision` now takes the note as a separate argument instead of string-concatenating it; the PASSDOWN status line was updated after Phases 8-9). It no longer applies in either direction. Safe to delete whenever you choose.

**Found, not fixed (out of this session's three-file scope):** `pyproject.toml` still declares `license = { text = "MIT" }` while `LICENSE` and now README say Apache 2.0. One-line fix; good candidate to fold into Session 2 or 16.

**Next up:** Session 2 -- projects, priority, due dates, status rollup. Per the session rules: first search the repo for existing project/priority/status/due-date symbols and report what exists, then failing tests, then implementation.

## 20. Session Notes — 2026-11-05: Upgrade Session 2 of 16 -- projects, priority, due dates, status rollup

**Branch:** `session-02-projects` (from `main` @ `aa3a4b5`, not from `session-01-cleanup`). Not merged. Session 1's PASSDOWN entry (section 19) lives on `session-01-cleanup`; merging both will need a trivial end-of-file conflict resolution in this file -- merge Session 1 first.
**Status:** Done. 194/194 tests passing (169 -> 194, all 25 new in `tests/test_projects.py`), installed and run as CI does.

**Pre-build search:** no project, priority, due-date, status or rollup symbols existed anywhere. Building blocks reused from `state.py`: `scheduled_start`/`scheduled_end`, `requires_hitl_review`, `risk_level`, `hitl_disposition`, `cleared_for_execution`. No completion/DONE field exists on a package, and none was invented.

**What was built** (`agent_core/projects.py`, commit `b44729e`):
- `Priority` (urgent/high/routine/low); `Project` (ID, name, priority default routine, optional `due_date`, `work_package_ids`; duplicates rejected).
- `package_status()` -- derived, never stored. Worst-first: BLOCKED (reviewed and not approved, or not cleared for an unknown reason) > PENDING_REVIEW > UNSCHEDULED > CLEARED. Fails closed: a package with `cleared_for_execution=False` never reads CLEARED.
- `rollup_project(project, packages, as_of)` -- overall = worst package status; counts and IDs per status; `late_package_ids` (scheduled_end after due date; ending exactly on it is not late); `past_due` judged against `as_of`, never the clock. Unknown or duplicated package IDs raise `ValueError` (same convention as `suggest_reschedule()`). Empty project rolls up UNSCHEDULED, never green.
- `sort_projects()` -- priority, then due date (none last), then ID. Does not mutate input.
- Also fixed: `pyproject.toml` license metadata MIT -> Apache-2.0 (found in Session 1).

**Known gaps, not fixed (candidates for the Session 11 review):**
- Mixing timezone-aware and naive datetimes (due date vs. package schedule) raises `TypeError` from the comparison; the repo doesn't standardize on one yet.
- A package listed in two projects isn't detected; each project rolls it up independently.
- Not wired into anything yet -- no graph node, brief, or reviewer reads it.
- Unscheduled packages can't be judged late; they surface under UNSCHEDULED instead.

**Next up:** Session 3 -- certificates with valid-from/valid-until, checked against the whole work window (not just the start). Relevant prior art: ADR-031 already states authorization windows are a hard constraint and records that nothing in `state.py` models a chit's `valid_until` today.

## 21. Session Notes — 2026-11-05: Upgrade Session 3 of 16 -- certificates checked against the whole work window

**Branch:** `session-03-certificates` (from `main` @ `aa3a4b5`). Not merged. Sections 19 and 20 (Sessions 1 and 2) live on their own branches; merge in session order and expect trivial end-of-file conflicts in this file.
**Status:** Done. 192/192 tests passing on this branch (169 -> 192, all 23 new in `tests/test_certificates.py`), installed and run as CI does.

**Pre-build search:** no certificate, validity, or expiry code existed. `SafetyPermitsRequired` (five booleans in `state.py`) recorded only that a permit is *required*, with no dates, and nothing read it. ADR-031 already states authorization windows are a hard constraint and that `valid_until` was unmodeled; `reschedule_suggestion.py`'s docstring names the unbuilt "chit-expiration engine". This session supplies the data model and the coverage check, not that engine.

**What was built** (`agent_core/certificates.py`, commit `c4237e7`):
- `Certificate` -- ID, work package ID, `CertificateKind`, closed window [`valid_from`, `valid_until`]; an unordered window is rejected.
- `CertificateKind` mirrors `SafetyPermitsRequired` field-for-field (same names, same order). A test fails if a permit flag is ever added without a kind, so a new permit can't go silently unchecked.
- `check_certificates(pkg, certificates)` -- for each required permit, the union of that package's certificates of that kind must cover the whole scheduled window. Findings: MISSING (none on file), NOT_COVERED (exact uncovered intervals listed, e.g. expires 1500 on a job to 1900), UNSCHEDULED (fails closed: needs a permit but has no complete schedule). Back-to-back renewals ending/starting at the same instant count as continuous. Duplicate certificate IDs raise. Never mutates the package.

**Known gaps, not fixed (candidates for Session 11):**
- Not wired in: no graph node, brief, or reviewer calls it yet, and `suggest_reschedule()` still can't see certificate windows (ADR-031's open point stands until Session 7 re-checks suggestions against every rule).
- No revocation or issuer/authority field; a certificate is trusted if it exists. Session 4 (named rules, who-to-call) is the natural place for issuing authority.
- Timezone-aware vs naive datetimes are not normalized (same gap as Session 2).
- Certificates are per package; one certificate covering several packages in the same space would need one record each.

**Next up:** Session 4 -- named rules with IDs, CFR cites, and who-to-call.

## 22. Session Notes — 2026-11-05: Upgrade Session 4 of 16 -- named rules with IDs, citations, and who-to-call

**Branch:** `session-04-rules` (from `main` @ `e0522a9`, which now includes Sessions 1-3). Not merged. From here sessions stack: Session 5 branches from this one.
**Status:** Done. 243/243 tests passing (217 -> 243, all 26 new in `tests/test_named_rules.py`), installed and run as CI does. `python -m eval.run_eval` unchanged against `eval/baseline.json`.

**Pre-build search:** `hazard_rules_v1.json` / `rules_config.py` held the three hazard pairs and the fire-watch limit under one shared `source_citation` string; no rule IDs, per-rule cites, or contacts anywhere. `check_conflict()` returned free text from two branches (hazard pair, overhead); `_fire_watch_capacity_conflicts()` cited NAVSEA8010-4.4.3 inline. Session 3's certificate findings had no rule.

**What was built** (commit `33af925`):
- `case_data/named_rules_v1.json` -- 10 rules: WS-HZ-001 hot work + confined space, WS-HZ-002 hot work + aloft, WS-HZ-003 aloft + fall protection, WS-OH-001 overhead work, WS-FW-001 fire-watch capacity, WS-CT-001..005 one per certificate kind. Each: title, citations (`source`, `verified`), `contact_role`, `escalation_role`, note. Contact roles used: Gas Free Engineer, Fire Safety Coordinator, Safety Officer, Competent Person.
- `agent_core/named_rules.py` -- validated loader (fails loudly on duplicate/malformed IDs, unknown hazard or certificate kind, blank contact, uncited rule without a note, wrong `schema_version`) and lookups: `get_rule`, `rule_for_hazard_pair`, `rule_for_overhead_work`, `rule_for_fire_watch_capacity`, `rule_for_certificate_kind`. Explains only; decides nothing.
- `deconfliction.py` -- `check_conflict()` is now a thin wrapper over `_detect_conflict()`, which returns `(rule_ids, rationale)`; new `conflict_rule_ids()`. Rationale strings are byte-identical to before.
- `certificates.py` -- `CertificateFinding.rule_id`.
- Completeness is test-enforced against the live detection constants: every incompatible pair and every certificate kind has exactly one rule, no rule exists for a pair detection doesn't check, and rule IDs always agree with `check_conflict()`.

**Citation honesty -- needs a human:** only NAVSEA8010-4.2, -4.4.3, -4.4.4 are `verified: true` (primary source read 2026-08-08, ADR-023); a test enforces that nothing else claims verification. Every 29 CFR section (1915.7, .12, .14, .77, .159, .503, .504) was added from general knowledge of Part 1915 and is `verified: false`. Before Session 16's recruiter README, someone should read each against eCFR and flip the flag or correct it. WS-OH-001 is deliberately uncited (note says why) rather than guessed.

**Known gaps, not fixed (candidates for Session 11):**
- Fire-watch findings still return `(a, b, rationale)` tuples without a rule ID; the rule exists (`rule_for_fire_watch_capacity()`), but the tuple shape is consumed by `suggest_reschedule()`, so it was left alone. Session 7/8 should attach it.
- `WorkPackageState.conflicts`/`conflict_rationale` don't store rule IDs; callers must ask `conflict_rule_ids()`. Wiring into state/brief is Session 8.
- `hazard_rules_v1.json` and `named_rules_v1.json` are two files describing the same pairs; tests keep them in lockstep, but a future merge into one file would be cleaner.

**Next up:** Session 5 -- judgment flags routed to a named Gas Free Engineer. The `contact_role` field here is the hook; Session 5 needs a notional roster mapping roles to notional people.

## 23. Session Notes — 2026-11-05: Upgrade Session 5 of 16 -- judgment flags routed to a named Gas Free Engineer

**Branch:** `session-05-judgment`, stacked on `session-04-rules`. Not merged.
**Status:** Done. 268/268 tests passing (243 -> 268, all 25 new in `tests/test_judgment.py`), installed and run as CI does. `eval.run_eval` unchanged.

**Pre-build search:** no judgment, roster, or person concept anywhere; "Gas Free Engineer" existed only as a Session 4 `contact_role` string. The eval already recorded the engine's blind spots as known gaps (`gap-adjacent-frames-not-touching`, `gap-simultaneous-confined-space-entries`), and an unlocated hot-work/confined-space package was silently treated as "no spatial link".

**What was built** (commit `e1dbfad`):
- New `RuleCategory.JUDGMENT` and rules WS-JF-001 (hot work within `JUDGMENT_ADJACENCY_FRAMES`=3 frames of a concurrent confined space, not overlapping, not already a conflict), WS-JF-002 (simultaneous confined-space entries in the same compartment or overlapping frames), WS-JF-003 (hot work or confined space with no compartment and no complete frame range). All route to the Gas Free Engineer, escalation Safety Officer. A judgment flag is "a person must decide", never a violation.
- `agent_core/judgment.py` -- `judgment_flags(packages, roster)`: deterministic, sorted by `flag_id` (e.g. `WS-JF-002:B+C`), order-independent, pure. Reuses `deconfliction`'s own overlap helpers so "concurrent" means the same thing in both places (unknown schedule = concurrent).
- `case_data/roster_notional_v1.json` -- 5 invented people (GFE primary Riley Example, backup Jordan Placeholder; Safety Officer, Fire Safety Coordinator, Competent Person). Loader rejects any entry not marked `notional: true`, duplicate IDs, or two primaries per role; `judgment_flags()` raises before producing anything if a judgment rule's role has no primary.
- Session 4 citation test tightened: a NAVSEA cite's `verified` must equal the site ruleset's flag (WS-JF-001 cites NAVSEA8010-4.3, verified there); every CFR cite must be `verified: false`.

**Known gaps, not fixed (candidates for Session 11):**
- The 3-frame threshold is a notional review prompt, not a sourced distance; should be site-configurable.
- `judgment.py` imports private helpers (`_frame_ranges_overlap`, `_same_compartment`, `_schedules_overlap`) from `deconfliction.py`; intentional to keep one definition, but they should become public if more modules need them.
- Routing ignores shifts: always the role's primary. Backup GFE is listed but unused until Session 6's shift calendar.
- `gap-two-aloft-packages-stacked` (deck_level unused) is not a GFE matter and has no judgment rule.
- Not wired into the graph, brief, or reviewer yet (Session 8).

**Next up:** Session 6 -- crews, a shift calendar, locked packages, contractor windows. Shift-aware routing of judgment flags (on-shift GFE) is a natural fit there.

## 24. Session Notes — 2026-11-05: Upgrade Session 6 of 16 -- crews, shift calendar, locked packages, contractor windows

**Branch:** `session-06-crews`, stacked on `session-05-judgment`. Not merged. **Hold merging until the Codex review of Sessions 2-5 (`review-01`) is triaged**, per Donnie.
**Status:** Done. 304/304 tests passing (268 -> 304: 35 in `tests/test_crews.py`, 1 in `tests/test_reschedule_suggestion.py`), installed and run as CI does. `eval.run_eval` unchanged.

**Pre-build search:** no crew, shift, lock, contractor, or calendar concept anywhere; `WorkPackageState` had no crew or lock field, and `suggest_reschedule()` would shift any package. Session 3's certificate check already contained the closed-interval coverage logic needed for contractor windows.

**What was built** (commit `6461002`):
- `agent_core/crews.py` -- `Shift`, `ShiftCalendar` (sorted, unique IDs, no overlaps; half-open `shift_at`; `next_shift(after)` for Session 7; `from_daily_pattern` with midnight-crossing shifts), `Window`, `Crew` (organic, or contractor with `contractor_windows`; a contractor with no windows may work nowhere), `is_movable()`.
- `check_schedule_constraints(packages, crews, calendar)` -- report-only, sorted, order-independent. New named rules, category `schedule`, contact Production Planner: WS-SC-001 unknown crew; WS-SC-002 contractor work outside windows (whole window; unscheduled contractor package reported, fails closed); WS-SC-003 work outside the shift calendar (gaps reported); WS-SC-004 crew double-booked (strict overlap, so back-to-back is fine). Uncited on purpose: planning constraints, not regulations.
- `state.py` -- `crew_id`, `locked`, `lock_reason` on `WorkPackageState`; locked requires a reason. All default off.
- `agent_core/intervals.py` -- `uncovered()` moved out of `certificates.py`; certificate tests unchanged and green.
- `reschedule_suggestion.py` -- returns `None` for a locked target (test proves the same pair gets a suggestion when unlocked).

**Known gaps, not fixed (candidates for review):**
- Shift-aware routing of judgment flags (on-shift GFE) not done; roster has no shift assignment yet. Fits Session 7 or 8.
- `suggest_reschedule()` still knows nothing about shifts, crews, contractor windows, or certificates -- it only respects the lock. That is Session 7's job.
- Unscheduled packages are skipped by the calendar and double-booking checks (projects rollup already reports them as UNSCHEDULED); only contractor packages fail closed.
- Calendar is concrete shifts; no holidays, recurring exceptions, or per-crew calendars.
- Locks are absolute; no "lock expires" or partial lock (start fixed, end flexible).

**Next up:** triage Codex's `review-01` findings (in a session that didn't write the code), then Session 7 -- the shift-aware fix suggester.

## 25. Session Notes — 2026-11-05: review-01 triage and a written review loop

**Branch:** `fix-review-01`, stacked on `session-06-crews` (includes the merged `review-01` report). Not merged.

**Why this happened:** Codex's review-01 of Sessions 2–5 reported 17 reproduced findings (9 high). The builder first accepted all 17 from reading the report alone. AOSE's rule "criticism is input, not authority" already existed, but only as narrative in AOSE.md, which no session loads, and the Session 1 pause note had dropped it. Donnie caught the gap.

**What changed:**
- `AGENTS.md` (read by Codex) and `CLAUDE.md` (imports it, read by Claude Code): the 8 session rules, the review loop, and the merge rules, loaded automatically every session. Review loop: the reviewer reports reproduced vs traced with a SHA; the builder gives every finding a verdict (CONFIRMED / AGREE-TRACED / DISPUTED with evidence) before fixing; Donnie settles disputes; the reviewer re-checks fixes.
- `reviews/TEMPLATE.md`: response format with a required verdict per finding.
- AOSE.md: pause note replaced by a five-line operating checklist plus the review cadence.
- review-01 verdicts: all 17 independently reproduced at `12d3873` and on this branch (`reviews/review-01-repro.py`). No disputes. Decisions D1 (how status accounts for findings) and D2 (R09 changes inherited detection) await Donnie.

**Housekeeping:** `integrate-01-03` is still on GitHub. This session's proxy refuses branch deletion, so Donnie needs to delete it in the GitHub UI.

**Next up:** Donnie answers D1/D2 → fix all 17 on this branch, test-first → Codex re-checks the fixes → merge chain Sessions 4–6 plus fixes → Session 7.

## 26. Session Notes — 2026-11-05: review-01 fixes (R01–R17)

**Branch:** `fix-review-01`. Not merged; waiting on Codex's re-check.
**Status:** All 17 fixed in `08fe4a5`. Full suite 341 passed, installed and run as CI does. `eval/baseline.json` unchanged (D2 needed no approval).

**Decisions:** D1 is the four-input AND gate. `package_status` and `rollup_project` require certificate, judgment, and schedule findings as arguments, refuse `None`, and add `HAS_FINDINGS`. D2: no baseline movement.

**What changed:** new `agent_core/validation.py` (`NonBlankStr`; `instant()` for real-time comparison; `require_comparable()` refusing mixed naive/aware times; `fmt_time()` with seconds). It is applied across state, certificates, intervals, crews, deconfliction, and projects. Unknown permit and spatial keys are refused. Duplicate IDs are refused in conflict and judgment batches. New judgment rules: WS-JF-004 (no common coordinate) and WS-JF-005 (gas-free work missing from the hazard list). Gas-free signals now read the hazard list, the spatial flag, and permits. `fire_watch_overloads()` catches single-package overloads, and `deconfliction_node` routes them to review. All applicable rule IDs are returned. Flag IDs are collision-proof. Judgment catalogue and triggers must match exactly. The R15/R16 tests were rewritten and mutation-checked. Per-finding fix and test table is in `reviews/review-01-sessions-02-05.md`.

**Known gaps opened by the fixes (for the re-check):** aware-time gap bounds now come back in UTC; the `deconfliction_result` event omits partner-less self-overloads; `extra="forbid"` affects every caller's intake.

**Next up:** Codex re-checks `fix-review-01` → Donnie's go → merge Sessions 4–6 plus fixes to `main` (CI on each branch and on the merged result) → Session 7.

## Review 01 re-check

Re-checked `fix-review-01` at `c234f3bd07f0d2a4f740bbf21fd8e1ba2357c1dd` on `review-01-recheck`. The per-ID verdicts, downstream findings and verification are under **Reviewer re-check** in `reviews/review-01-sessions-02-05.md`. Twelve confirmed fixed. R02, R06, R09, R13 and R14 reopened with reproductions. Hold for triage, particularly the second self-overloaded package clearing, the visualizer's all-clear, and invalid reschedule suggestions. All 341 tests passed and the eval matched the checked-in baseline.

## 27. Session Notes — 2026-11-05: review-01 re-check triage and fixes

**Branch:** `fix-review-01`. Not merged; waiting on Codex's second re-check.
**Re-check result (Codex at `c234f3b`):** 12 confirmed fixed; R02, R06, R09, R13, R14 reopened; new N01–N05, including a second fire-watch overload left cleared, a visualizer "all clear" during a required review, a reschedule suggestion that preserved an overload, and a suggestion ending before it started across the daylight-saving repeated hour.
**Builder response:** every item independently reproduced at `c234f3b` (`reviews/review-01-recheck-repro.py`, 10/10), with verdicts committed before any fix (`99e7a72`). No disputes. The builder's earlier "0/17 after fix" claim was corrected: the old script had crashed on the new API and that crash was miscounted as a fix.
**Fixes:** `7c82768`. 355 tests passed; eval 14/14 with the baseline unchanged. Per-item table in the review file.
**Lesson recorded:** a verification script that can crash must report the crash as an error, never as a pass. The new script is written that way.
**Next up:** Codex re-check 2 → Donnie's go → merge Sessions 4–6 plus fixes (CI on each branch and on the merged result) → Session 7.

## Review 01 re-check 2

Reviewed `fix-review-01` at `e80640934e8ac9bc93a563721890d3acb9c0b48f` on `review-01-recheck2`. Results are under **Reviewer re-check 2** in `reviews/review-01-sessions-02-05.md`. Nine of the ten requested findings are confirmed fixed. R02 remains open through iterator reuse across project rollups. New N06 covers misleading self-overload briefs and N07 covers irrelevant certificate kinds aborting coverage checks. All 355 tests passed and eval matched the baseline. Independent watch-load, daylight-saving movement and coverage checks also passed. Hold for triage of the reproduced false clearance.

## 28. Session Notes — 2026-11-05: review-01 re-check 2 triage and fixes

**Branch:** `fix-review-01`. Not merged; waiting on Codex re-check 3.
**Re-check 2 (Codex at `e806409`):** 9 confirmed fixed; R02 reopened via the rollup path; new N06 (self-overload brief invented a partner and suggested pair remedies) and N07 (an unrequired certificate kind aborted coverage).
**Builder:** 3/3 independently reproduced (`reviews/review-01-recheck2-repro.py`); verdicts committed before fixing (`5ee5bd2`); fixed in `e5076c4`; 364 tests passed; eval baseline unchanged.
**Lesson:** R02 reopened twice because each fix guarded only the call site the reviewer named. The guard is now shared, and a parametrized test runs every findings-taking entry point.
**Found by the builder during verification:** the first N06 fix mislabelled its brief "LLM OFFLINE"; it now uses the new source `deterministic-template`.
**Raised for Session 8 (rule 7):** with the LLM on, `recommended_action` comes from the model. Proposal: always deterministic; the LLM may only rephrase the summary.
**Next up:** Codex re-check 3 → Donnie's go → merge → Session 7.

## Review 01 re-check 3

Reviewed `fix-review-01` at `38e0616b6df88b8de36cd11b146171a2d4673855` on `review-01-recheck3`. R02, N06 and N07 are confirmed fixed, with no new regression identified in these changes. The new deterministic-template provenance survived the real graph, events, SQLite reload, HTTP queue/detail pages and a rejection. All 364 tests passed and eval matched the baseline. Details and limits are under **Reviewer re-check 3** in `reviews/review-01-sessions-02-05.md`. The review-01 findings are closed across the completed re-checks. Donnie's merge approval and required CI still apply.

## 29. Session Notes — 2026-11-05: Upgrade Session 7 of 16 -- shift-aware fix suggester

**Branch:** `session-07-shift-suggester`, from `main` @ `c3a41ff` (Sessions 1–6 and review-01 merged; CI green on main). Not merged.
**Status:** Done. 387/387 tests passing (364 → 387, all new in `tests/test_shift_suggester.py`), installed and run as CI does. Eval 14/14, baseline unchanged.

**Pre-build search:** `suggest_reschedule()` moved one package by a whole step either way and knew nothing of shifts, crews, contractor windows, or certificates, though it respected locks and fire-watch overloads. `crews.py` already provided `shift_at`, `next_shift`, and `is_movable`. Nothing moved a crew as a unit or recorded why a candidate was rejected. Nothing called either suggester.

**What was built** (commit `486e099`): `agent_core/shift_suggester.py`, `suggest_crew_shift(packages, target_id, *, crews, calendar, certificates, max_shifts=6)`.
- The block is every package the target's crew starts in the target's shift. It moves forward as a unit by (later shift start − current shift start), keeping its internal spacing.
- Each candidate shift is re-checked against conflicts, fire-watch overloads, certificates, schedule rules, and judgment flags, counting only findings that name a moved package.
- Returns `CrewShiftOutcome`: the suggestion (`applied=False`, `source="deterministic_shift_search"`, and the checks run), every rejected shift with its rule IDs, or a reason. The reasons are: locked package, no crew, unknown crew, no schedule, outside the calendar, no later shift, or nothing passed.
- Pure. `suggest_reschedule()` is unchanged.
- Mutation-checked: disabling any one check, or the lock refusal, fails a test.

**Decision recorded (Donnie, 2026-11-05):** Session 8 makes `SafetyBrief.recommended_action` always deterministic. The LLM may only rephrase the summary (AGENTS.md rule 7).

**Known gaps (for Session 11's review):**
- The block is "starts in the shift"; a package starting late in one shift and running into the next moves with its starting shift.
- Only the target's crew moves. If another crew's package is the real cause, no alternative is offered for moving that one instead.
- No preference beyond "earliest passing later shift" (no weekend or overtime cost).
- Certificates never move, so a block needing a permit valid only in its current shift never gets a suggestion. Correct per ADR-031, but the outcome could say "re-issue permit" more helpfully.
- Not wired into the brief or reviewer yet; that's Session 8.

**Next up:** Session 8 -- wire suggestions into the brief and reviewer, with an Apply that re-checks, and a deterministic `recommended_action`.

## Review 02 · Session 7

Reviewed `session-07-shift-suggester` at `5dfdcbc00786ce28b531e27e1e912c8ff0a1fd18` against `main` at `c3a41ffd579048019dbecf2b2fbee3fa192cd986`, on `review-02`. Findings are in `reviews/review-02-session-07.md`: five reproduced issues, including incomplete crew members omitted before lock/availability checks, destination shift misidentification for shorter shifts, and unlocated overhead work getting a passing suggestion. Hold for triage of the two high-severity findings. All 387 tests passed and eval matched its baseline. Independent revalidation of 141 returned candidates, shift-edge, overnight, DST, calendar-gap and input-purity checks passed within the documented limits.

## 30. Session Notes — 2026-11-05: review-02 (Session 7) triage and fixes

**Branch:** `session-07-shift-suggester` (now includes the `review-02` report). Not merged; waiting on Codex's re-check.
**Review (Codex at `5dfdcbc`):** 5 findings, 2 high. Incomplete crew members bypassed block, lock, and availability checks; unlocated overhead work got a passing suggestion; a short destination shift could be misnamed; negative `max_shifts` was accepted; two tests passed with empty results.
**Builder:** 5/5 independently reproduced (`reviews/review-02-repro.py`); verdicts committed first (`d52dde4`); fixed in `b6ce52f` with one more builder-found overhead gap; 399 tests passed; eval baseline unchanged.
**Decision for Donnie:** the inherited gap where detection and judgment never report unlocated overhead work. Option: new judgment rule `WS-JF-006` routed to the Safety Officer (all judgment flags go to the GFE today). Logged as Known Debt until decided.
**Environment note:** `pip install -e ".[dev,retrieval,reviewer]"` as root works (399 passed via `python3 -m pytest`), but this image's bare `pytest` is a separate uv-tool install that can't see system packages. A Watchstander environment's setup script should account for that.
**Next up:** Codex re-check of review-02 → merge Session 7 → Session 8.

## Review 02 re-check

Reviewed `session-07-shift-suggester` at `f7634875572dce340d1008ce64ba2d0addb0475d` on `review-02-recheck`. S07-01, S07-02, S07-04 and S07-05 are confirmed fixed. S07-03 remains open: hazard-only overhead classification with complete overlapping frames bypasses the missing-data guard and the spatial-flag-only detector. Reproduced for moved and fixed overhead jobs. New rejection-reason serialization, mixed reasons/rule IDs, whole-crew refusal, time boundaries and purity checks passed. All 399 tests passed and eval matched the baseline. Details are under **Reviewer re-check** in `reviews/review-02-session-07.md`. Hold for triage of S07-03.

## 31. Session Notes — 2026-11-06: review-02 re-check triage and fix

**Re-check (Codex at `f763487`):** 4 confirmed fixed; S07-03 reopened. Hazard-labelled overhead work with complete frames and the spatial flag unset still got a suggestion directly over other work, because `WS-OH-001` reads the flag only.
**Builder:** 3/3 variants reproduced; verdict first (`d5f05b6`); fixed in `e5d5794`. The broad overhead signal now drives separation as well as completeness. 404 tests passed; eval baseline unchanged.
**Lesson (second time, after review-01 R02):** a signal accepted by one check must drive every check it bears on.
**Open for Donnie:** make detection see hazard-labelled overhead and add `WS-JF-006` (unlocated overhead → Safety Officer)? Both change inherited detection and judgment routing.
**Next up:** Codex re-check 2 → merge Session 7 → Session 8.

## Review 02 re-check 2

Reviewed the current `session-07-shift-suggester` tip `4432f5771e662451f84c6e6bd14db65592ad374a` on `review-02-recheck2`. S07-03 is confirmed fixed, with no new regression identified. Independent checks covered 96 overhead signal/orientation/frame/time combinations, later-shift recovery, DST separation, purity, ordering and JSON serialization. All 404 tests passed and eval matched the baseline. Review-02 findings are closed for the suggester. The inherited detector/judgment debt remains separately documented. Details are under **Reviewer re-check 2** in `reviews/review-02-session-07.md`. Donnie's merge approval and required CI still apply.

## 32. Session Notes — 2026-11-06: Upgrade Session 8a of 16 -- overhead detection, WS-JF-006, deterministic recommendation

**Branch:** `session-08-brief-apply`, from `main` @ `91405be` (Session 7 and review-02 merged). Not merged. Session 8 is split: **8a** (this entry) changes detection and the brief; **8b** wires suggestions into the brief and reviewer with an Apply that re-checks.
**Status:** 8a done. 418/418 tests passing (404 → 418); eval 14/14, baseline unchanged.

**Pre-build search:** `_vertically_stacked` read only the spatial flags. `shift_suggester` had its own broader `_is_overhead`. With the LLM on, `generate_safety_brief` took `recommended_action` from the model (rule 7 violation). Nothing called either suggester, and the graph state carries no crews, calendar, or certificates.

**What was built** (commit `3945e39`):
- `deconfliction.is_overhead()` is the one shared definition (flag OR `working_aloft` / `over_the_side` label), used by detection, its rationale, and the shift suggester.
- WS-JF-006 (judgment) covers overhead work with no frame range and routes to the **Safety Officer**. It's the first judgment rule not routed to the GFE.
- Rule 7: the LLM prompt no longer asks for a recommendation; `recommended_action` is always the deterministic text; the LLM may still phrase the summary and precedent.
- Three older tests updated for the approved change, each with a comment.

**Decisions recorded:** Donnie, 2026-11-06, yes to both detection questions (treat hazard-labelled overhead as overhead; WS-JF-006 to the Safety Officer). Rule-7 decision from 2026-11-05 implemented.

**Next up (8b):** carry crews, calendar, and certificates in graph state; put the crew-shift suggestion in the brief's deterministic recommendation; show it in the reviewer; Apply re-checks against current state before changing anything. Then a Codex review of 8a and 8b together before merge.

## 33. Session Notes — 2026-11-06: Upgrade Session 8b of 16 -- suggestion in the brief and reviewer, Apply that re-checks

**Branch:** `session-08-brief-apply` (8a + 8b). Not merged; a Codex review of 8a and 8b together comes first.
**Status:** 8b done. 431/431 tests passing (418 → 431); eval 14/14, baseline unchanged.

**Pre-build search:** each flagged package gets its own `interrupt()`, resumed by the reviewer's approve/reject. A run's packages are fixed at seed time. Nothing carried crews, calendar, or certificates into a run, and nothing called either suggester.

**What was built** (commit `b3bf591`):
- `GraphState.run_inputs`: an untouched copy of the seeded inputs (plain dicts).
- `reasoning_node` calls `suggest_crew_shift` per flagged package when crew data exists. `SafetyBrief.shift_outcome` holds the outcome, and `recommended_action` gains a deterministic sentence (suggested-not-applied / no suggestion and why / no crew data).
- `ReviewerService.seed_run`, `run_inputs`, and `apply_shift_suggestion`. Apply re-runs the suggester on the run's inputs and proceeds only on an exact match with the brief. It then: starts a new run with the moved times, with moved packages `requires_hitl_review` (never approves); rejects the old run's pending reviews as superseded; and records that in `registry`. Otherwise nothing changes.
- Reviewer UI: the suggestion in the brief, an Apply form that explains the re-check, the outcome on the dashboard, and superseded runs labelled.
- Mutation-checked on the three safety properties.

**Design choice, for the review:** Apply supersedes the *whole* old run, including already-approved packages in it. Their approvals were made against a schedule that no longer exists, so the new run re-reviews everything that is flagged.

**Known gaps (for the review / Session 11):**
- The demo fixture has no crews or calendar, so the ACUSHNET demo never shows a suggestion; Session 10's notional dataset fixes that.
- Apply re-checks against the run's own inputs. There is no live "current yard state" outside a run yet.
- `run_inputs` adds more types to the checkpoint; the existing msgpack "unregistered type" warning debt still applies.
- The new-run ID is derived (`<thread>-applied-<interrupt prefix>`). A second Apply on the same review is impossible because the old review is closed, but this hasn't been stress-tested.

**Environment note:** this session's machine was replaced mid-session (worker restart). The rebuilt venv uses `--system-site-packages` plus its own pytest, so plain `pytest` resolves to the venv.

**Next up:** Codex review of Session 8 (8a + 8b) → triage → merge → Session 9 (decision log).

## Review 03 · Session 8

Reviewed `session-08-brief-apply` at `2f94ed570302cc106062c36731592f68fb7553a3` against `main` at `91405be784bc32889c725012d50c45865f5bfc26`, on `review-03`. Included the documentation-only branch update received during review. Findings are in `reviews/review-03-session-08.md`. Four reproduced high-severity issues cover concurrent successor runs, interrupted Apply leaving old reviews open, inherited approval on moved packages, and WS-JF-006 missing the normal graph review gate. A medium finding covers hidden rejection evidence, with a related low-severity test observation. Hold for triage. All 431 tests passed and eval matched its baseline. Sequential Apply/reload/exact-match checks and deterministic recommendation isolation passed within the reported limits.

## 34. Session Notes — 2026-11-07: review-03 (Session 8) triage and fixes

**Branch:** `session-08-brief-apply` (now includes the `review-03` report). Not merged; waiting on a cheaper-model re-check.
**Review (Codex, strongest model, at `2f94ed5`):** 6 findings, 4 high. Concurrent Apply created two successors; an interrupted Apply left the old schedule approvable; Apply carried a seeded approval into a moved package; WS-JF-006 never reached the review gate; why every shift failed was hidden; one test passed with fabricated text.
**Builder:** 6/6 reproduced (`reviews/review-03-repro.py`); verdicts first (`43886e6`); fixed in `c9314ec`. Every fix mutation-checked; two tests strengthened.
**Builder-found, same class (Donnie: fix now):** certificate and schedule findings never reached review, so a missing permit passed as cleared. Fixed in `3578393` with a findings node.
**Status:** 457 tests passed; eval baseline unchanged.
**Process note:** the review cost policy is now in AGENTS.md (strongest model for first reviews, cheaper for re-checks, reviews at Sessions 8, 11, 16).
**Next up:** cheaper-model re-check → merge Session 8 → Session 9 (decision log).

## Review 03 re-check

Tested `session-08-brief-apply` at `78fad145f2dbcb41920d85d5afa43029a8253763` on `review-03-recheck`. S08-03 through S08-06 and the findings gate are confirmed fixed. S08-01 and S08-02 reopened: startup recovery can delete a live Apply claim before successor creation, permitting a second successor or approval of the old schedule while Apply is in progress. Both were reproduced. All 457 tests passed and eval matched the baseline. See **Reviewer re-check** in `reviews/review-03-session-08.md`. Hold for triage.

## 35. Session Notes — 2026-11-07: review-03 re-check triage and fix

**Re-check (Codex, cheaper model escalated to the strongest at `78fad14`):** S08-03..06 and the findings gate confirmed fixed. S08-01/02 reopened: startup recovery deleted a *live* Apply's claim, allowing two successors or an old-schedule approval during Apply.
**Builder:** 2/2 reproduced, plus a same-class race in `submit_decision` (check-then-resume). Verdicts first (`5ae3946`); fixed in `bbb1c51` with one leased lock per run shared by Apply and decisions; recovery acts only on expired leases; superseded runs never report cleared. Mutation-checked.
**Status:** 462 tests passed; eval baseline unchanged.
**Next up:** cheaper-model re-check 2 → merge Session 8 → Session 9 (decision log).

## Review 03 re-check 2

Tested `session-08-brief-apply` at `557f3f6c1546997333c98efc6f5067288369783b` on `review-03-recheck2`. S08-01 and S08-02 reopened. Recovery can remove an expired lock from a live Apply, and Apply can use a pending review read before a racing decision completes. All 462 tests passed, eval matched its baseline, and both builder re-check probes reported NOT REPRODUCED within their scenarios. The reproduced interleavings and verdicts are under **Reviewer re-check 2** in `reviews/review-03-session-08.md`. Hold for triage.

## 36. Session Notes — 2026-11-07: review-03 re-check 2 — change of approach

**Re-check 2 (Codex at `557f3f6`):** S08-01/02 reopened a third time. A *live* Apply whose lease expired lost its lock, so two successors were created; and Apply acted on a review approved after it was read.
**Builder:** 2/2 reproduced. Verdict and design first (`3f0958d`). Patching one interleaving at a time was the wrong approach, because a lease can't prove its owner is dead. Fixed in `4865ce3`: an exclusive per-database service lock (flock; the OS releases it on crash), recovery only under that lock, and one in-service lock serializing Apply and decisions with a re-read. A real-crash test uses a killed subprocess.
**Constraint (documented in reviewer/README.md):** one reviewer service per database. Multi-user review is out of scope unless Donnie wants it.
**Status:** 465 tests passed; eval baseline unchanged; 6 mutations caught.
**Next up:** cheaper-model re-check 3 → merge Session 8 → Session 9.

## Review 03 re-check 3

Tested `session-08-brief-apply` at `23b05e8abe810cc90444bec1ff8408c125882e31` on `review-03-recheck3`. S08-01 and S08-02 reopened. The same-path service exclusion and in-service decision serialization pass, but a symlink alias acquires a separate sidecar lock for the same SQLite database. Startup recovery then removes a live Apply marker, permitting either a second successor or old-schedule approval. Both effects were reproduced. All 465 tests passed and eval matched the baseline. Details are under **Reviewer re-check 3** in `reviews/review-03-session-08.md`. Hold for triage.

## 37. Session Notes — 2026-11-07: review-03 re-check 3

**Re-check 3 (Codex at `23b05e8`):** S08-01/02 reopened. A symlink to the same database got a different lock file, so a second service ran recovery over a live Apply.
**Builder:** reproduced, plus the hard-link alias (same class); verdict first; fixed in `09a1636` by keying the lock on the database's device and inode. 469 tests passed; eval baseline unchanged.
**Next up:** cheaper-model re-check 4 → merge Session 8 → Session 9.

## Review 03 re-check 4

Tested `session-08-brief-apply` at `103488af71b4f82761ef3aa55f65dc0b2b571df5` on `review-03-recheck4`. Symlink, hard-link and path-spelling exclusion passed in the common lock directory. S08-01 and S08-02 reopened because differing temp directories give two services different locks on the identical local database. Reproduced two successors and old-schedule approval during live Apply across processes. High impact with low likelihood in a normal single-reviewer launch. All 469 tests passed and eval matched the baseline. See **Reviewer re-check 4** in `reviews/review-03-session-08.md`. Hold for triage.

## 38. Session Notes — 2026-11-07: review-03 re-check 4; lock class closed

**Re-check 4 (Codex at `103488a`, medium):** two processes with different `TMPDIR` locked the same database separately.
**Builder:** confirmed with two real processes (a first in-process probe gave a false "refused" through RecursionError and was discarded). Fixed in `a9c0672`: the lock sits beside the database's real file, independent of the environment. 470 tests passed; eval baseline unchanged.
**Donnie's decision:** option 1. Fix this, then close the class. Remaining aliasing paths (cross-directory hard links, network filesystems, bind mounts) are in ARCHITECTURE.md Known Debt and reviewer/README.md as unsupported.
**Next up:** a narrow cheaper-model re-check 5 → merge Session 8 → Session 9 (decision log).

## Review 03 re-check 5

Tested `session-08-brief-apply` at `4b14cc19e8af755b553c3e81d053dfeadca99733` on `review-03-recheck5`. S08-01 and S08-02 confirmed fixed within the accepted local database scope. The named TMPDIR regression and a separate live Apply probe verified that a second process with a different temp directory is refused, the marker is preserved and exactly one successor is registered. All 470 tests passed and eval matched the baseline. Details are under **Reviewer re-check 5** in `reviews/review-03-session-08.md`.

## 39. Session Notes — 2026-11-07: Upgrade Session 9 of 16 -- decision log

**Branch:** `session-09-decision-log`, from `main` @ `1f3b716` (Session 8 and review-03 merged; CI green on main). Not merged.
**Status:** Done. 485/485 tests passing (470 → 485); eval baseline unchanged. No separate review: per the review cost policy this rolls into the Session 11 review.

**Pre-build search:** `rules_audit.py` kept an append-only JSONL log of rule changes only, append-only by convention (AUD-15) and fragile to one bad line (AUD-14). Human decisions lived only in graph checkpoint state, with no who, when or why, and no record of refused Applies, supersession or recovery. The reviewer had no user identity.

**What was built** (commit `4fa101d`):
- `agent_core/decision_log.py`: `DecisionLog` in the reviewer's SQLite database, with a closed set of kinds. Triggers refuse UPDATE and DELETE. A hash chain (prev hash + content, including seq) is checked by `verify_chain()`, which names the first bad entry.
- `ReviewerService` logs every decision (the stored disposition), refused decision, Apply (successor and moves), refused Apply (reason), supersession rejection (actor `system`), and recovery (actor `system`).
- Reviewer: "Your name" on the decision and Apply forms (blank becomes `unidentified reviewer`); a `/log` page with the chain status.

**Known gaps (Session 11 review):**
- **Tail truncation:** deleting the newest entries isn't detectable by the chain alone (documented with a test). Fix: anchor the head hash outside the database. Session 10's daily brief could print it.
- Actor is self-declared (no auth); the log records it honestly as such.
- A crash between a decision's checkpoint write and its log append loses that one log entry. The decision itself is safe and recorded in graph state.
- `rules_audit.py` (AUD-14/15) isn't migrated onto this mechanism.

**Next up:** Session 10 -- notional carrier dataset and a text daily brief.

## 40. Session Notes — 2026-11-07: docs sync (pause between Sessions 9 and 10)

**Branch:** `docs-sync`, from `session-09-decision-log` @ `de00709`. Docs only; no code changes. Not merged.
**Why:** Donnie asked for a whole-repo docs check: anything a reader sees should match what the code does now.

**What was stale, and what changed:**
- **README.md:** graph diagram and module list predated judgment, findings gate, certificates, crews, named rules, shift suggester, Apply and the decision log; install command missed the extras CI uses. Rewritten from the code, with an honest note on which demo data is real-public vs notional.
- **ARCHITECTURE.md:** header said Phase 11; no ADRs after ADR-034; component table and Known Debt predated Sessions 2–9. Added ADR-035 to ADR-047, component rows, Known Debt rows (29 CFR cites unverified, demo data vs rule 6, decision-log tail truncation, others) and closed or marked superseded the rows the sessions fixed.
- **MIGRATION.md:** last updated 2026-07-25, no upgrade plan. Added the 16-session table with status.
- **SECURITY.md:** referred to `requirements.txt` (the project uses `pyproject.toml`) and "chit-expiration" (now certificates).
- **reviewer/README.md:** didn't mention the reviewer's name field, crew-shift suggestions, Apply, or `/log`.
- **docs/architecture-diagram.html:** pre-rendered old graph; added an out-of-date banner rather than regenerating.
- Historical ADRs and session notes left as written (they're a record).

**For Donnie:** the ACUSHNET demo is derived from public-domain HAER drawings of a real cutter, which conflicts with rule 6. Logged as Known Debt; proposed fix is Session 10's notional carrier dataset replacing it as the default demo.
**Next up:** Session 10.

## 41. Session Notes — 2026-11-08: Upgrade Session 10 of 16 -- notional carrier dataset and text daily brief

**Branch:** `session-10-carrier-brief`, from `docs-sync` (which sits on `session-09-decision-log`). Not merged; Sessions 9, docs-sync and 10 are stacked and waiting for Donnie's go.
**Status:** Done. 518/518 tests passing (485 → 518); eval baseline unchanged. No separate review: rolls into Session 11 per the review cost policy.

**Pre-build search:** the only demo was `demo_fixtures.py` (4 ACUSHNET packages, real-ship HAER data, no times, crews, certificates or projects). Every check existed; no daily brief; nothing recorded the decision-log head outside the database.

**What was built:**
- `case_data/carrier_notional_v1.json` + `agent_core/carrier_demo.py`: invented carrier, 11 packages, 10 crews (one contractor), a 3-day DAY/SWING/MID calendar, 5 certificates, 4 projects. Loader refuses `notional` other than a real JSON `true` and dangling project/certificate references. Each scenario is pinned to the one rule it triggers (WS-HZ-001, WS-JF-001, WS-OH-001, WS-CT-003, WS-CT-001, WS-SC-002; two packages clean).
- `agent_core/daily_brief.py`: `run_checks()` and `render()`, plus `python -m agent_core.daily_brief --as-of ... [--db] [--anchor SEQ:HASH]`. Deterministic, no LLM, never applies or approves.
- `DecisionLog.head()` and `verify_anchor()`: with a recorded anchor, cutting entries off the end is now caught (Session 9's gap).
- Reviewer: default **Seed** button runs the notional carrier; ACUSHNET moved to a labeled second button (`seed_acushnet_demo`). ACUSHNET-pinned tests now call it by name, assertions unchanged.

**Found while building:** the first dataset draft double-booked two crews (WS-SC-004); the pinned-rule tests caught it. Mutation testing found `"notional": "yes"` loading as true; fixed with StrictBool in both the dataset and the Session 5 roster (same class), failing tests first.

**Known gaps (Session 11 review):** the anchor only helps if someone records the head line outside the database; nothing does it automatically. The brief is pre-review (every flagged package reads pending). LangGraph's checkpoint deserialization warning (Known Debt) now also names CertificateKind.
**Next up:** Session 11 -- independent review of the engine (strongest model), covering Sessions 9 and 10.

## 42. Session Notes — 2026-11-08: real-ship demo deleted (Donnie: "1 delete")

**Branch:** `session-10-carrier-brief` (follow-up commit, so the Session 11 review sees it). Not merged.
**Donnie's decisions:** (1) delete ACUSHNET; (2) merge Sessions 9, docs-sync and 10 after the Session 11 review; (3) proceed to Session 11.

**What was removed (ADR-049):** `agent_core/demo_fixtures.py`, the reviewer's ACUSHNET seed button and route, the HAER visualizer backgrounds, the 3D blockout (`Main3D.*`, `OrbitCamera.*`), and the ACUSHNET and Turner Joy source docs. Historical ADRs and phase notes are kept and marked superseded.
**What replaced it:** the reviewer and `visualizer/demo_broadcaster.py` use the notional carrier; `Main.gd` draws on the generated schematic (`bg_blueprint.png`) with new frame and band calibration; "4th"/"5th" deck labels go to the hold band; the default marker color is light for the dark background.
**Tests:** ACUSHNET reviewer tests ported to the notional carrier with the same assertions. New: a guard that fails on any real-ship reference in code, data or the visualizer (confirmed failing before the cleanup); a check that the broadcaster's scripted conflicts equal the real deconfliction on the dataset; the old seed route is gone. 521 passed; eval unchanged.
**Not verified:** the Godot scene. Running a downloaded Godot binary was refused in this environment, so `Main.gd`'s edits were not run. Donnie: open `visualizer/` in Godot once and report anything off.
**Next up:** Session 11 review (prompt in `reviews/review-04-session-11-prompt.md`).

## 43. Session Notes — 2026-11-08: Session 11 review (review-04) triaged and fixed

**Review:** separate reviewer session (Donnie reports GPT-6 Astra) at `96447220`, report on `review-04-session-11` @ `167ea54`. 521 passed, eval 14/14 and 7/7. Three medium findings, all reproduced by the reviewer.
**Builder triage** (branch `fix-review-04`, from `session-10-carrier-brief`): all three **CONFIRMED** with my own probes before any fix.
- **S11-01:** an unknown interrupt went unlogged; a stale resubmission wrote a `decision` entry with no package or disposition. Now refused and logged as `decision_refused` before the graph is touched; graph errors log `decision_failed`; a `decision` entry always names a stored disposition.
- **S11-02:** an Apply that raised before its successor existed left no log entry, even after restart. Now logged as `apply_failed` with whether a marker is left for recovery.
- **S11-03:** the daily brief dropped a routing reason that wasn't a catalogue rule. It now prints every routing note as "Why:", and says so when a pending package has no reason at all.
**Tests:** `tests/test_review04.py` (11, failing first), 532 passed, eval unchanged. Each fix mutation-tested: undoing any one fails the tests. `reviews/review-04-builder-repro.py` prints FIXED/REPRODUCED/ERROR per finding (the reviewer's own script now stops at the new refusal by design).
**Donnie's calls this session:** showcase = one-page carrier mockup from real check results, screenshots reviewed before the full build; Godot stays as an optional demo.
**Next up:** cheaper-model re-check of these fixes → merge Sessions 9, docs-sync, 10 and these fixes (Donnie's go) → Session 12 mockup.

## Review 04 re-check

Tested `fix-review-04` at `2cde436ff5322e09de29807139cb919dae964f8f` on `review-04-recheck`. S11-03 confirmed fixed. S11-01 and S11-02 reopened for a shared initial checkpoint-read exception path that leaves decision and Apply attempts unlogged. Independently reproduced through restart with the log still operational. All 532 tests passed, eval matched the baseline, and the builder probes passed their original scenarios. Details are under each **Reviewer re-check** line in `reviews/review-04-session-11.md`. Hold for triage.

## 45. Session Notes — 2026-11-09: review-04 re-check: S11-03 fixed, S11-01/02 reopened and fixed again

**Re-check** (cheaper model at `2cde436`, pushed `review-04-recheck` @ `e084084`): 532 passed, eval baseline, all builder probes FIXED. S11-03 confirmed fixed. S11-01 and S11-02 **reopened**: a fault in the first checkpoint read, before the per-step guards, left the decision or Apply unlogged.
**Builder:** CONFIRMED independently (OSError injected into `get_state`). Fix on `fix-review-04`: one guard wraps the whole body of each operation, so every outcome writes exactly one entry. Tests now inject a fault at six internal steps for both operations. Mutation-tested. Same lesson as reviews 01–03: the signal has to cover every path, not the reported one.
**Donnie:** the mockup's look is approved as the base for Sessions 13–15.
**Next up:** cheaper-model re-check 2 of S11-01/02 → merge (Donnie's go) → Session 13.

## 46. Session Notes — 2026-11-09: review-04 closed; Sessions 9–11 merged to main

**Re-check 2** (cheaper model at `78d2a64`, pushed `review-04-recheck2` @ `cf2a57c`): S11-01 and S11-02 confirmed fixed; first-read faults leave exactly one `decision_failed` / `apply_failed` entry after restart. 546 passed, eval 14/14 and 7/7, all five builder probes FIXED. **Review 04 closed.**
**Merge:** per Donnie's standing go ("merge after 11 review"), `main` fast-forwarded to this commit after CI passed on it: Session 9 (decision log), docs-sync, Session 10 (notional carrier, daily brief, real-ship demo deleted), and the review-04 fixes. `session-12-showcase` is not merged (unreviewed UI work; rolls into the next review).
**Fable 5.2:** included in Pro/Team weekly limits through Nov 16. Plan: use it as a separate reviewer session (red team of the safety engine), never as this builder.
**Next up:** Fable red-team review (separate session) → Session 13 (live showcase).

## 47. Session Notes — 2026-11-09: docs status sync

**Branch:** `docs-status`, from `main` @ `96b207a`. Docs and one test; no engine code. Not merged.
**Why:** Donnie: dates and status across the docs didn't match the repo. GitHub's per-file dates are last-commit dates and will always differ; the problem was stale text inside the docs.
**Fixed:** README opening still described "real HAER ship drawings" (deleted in Session 10); added a README "Current status" block as the one place to check; MIGRATION header (said Sessions 1–10), Phase 4 status (said in progress; actually paused since 2026-07-24), case counts dated; ARCHITECTURE header; AOSE status said "Proposed" though it has run four review rounds.
**Kept from recurring:** AGENTS.md rule 8 now includes the README status block; `tests/test_docs_status.py` fails if the README's date falls behind the newest PASSDOWN entry, or if the README mentions the deleted real-ship visuals.

## 48. Session Notes — 2026-11-09: review-05 (Fable red team) triaged and fixed

**Review:** Fable 5.2 in a separate session, `main` @ `439c4b1`, report on `review-05-redteam` @ `61d5c7c`: 11 findings (5 high, 6 medium), all reproduced by the reviewer. 548 passed, eval baseline.
**Builder:** all 11 **CONFIRMED** with an independent probe. Fixed on `fix-review-05`.
**Donnie's rulings:** R05-03 an approval can't clear an open certificate or schedule finding (emergency override → Known Debt). R05-02 a rejection carries into Apply's successor. R05-05 a hazard implies its authorization; aloft is an aloft chit (CSOOW, for the day) or a standing aloft (CO, date range), not the fall protection plan, which is a ship's standing order. Zones, over-the-side and site prerequisite documents are logged as Known Debt / tabled.
**What changed:** new `agent_core/intake.py` (graph entry); `open_findings` on packages; WS-CT-006 and `aloft_authorization`; `extra="forbid"` on every input model; fire-watch key; model text kept apart (`model_explanation`); `_call_llm` catches API failures; `*_requested` log entries and `open_requests()`; crew rules without a calendar; read-only log for the brief.
**Tests:** `tests/test_review05.py` (written failing first); older fixtures given permits via `tests/notional_permits.py`; review-04 tests count outcome entries. 596 passed; eval unchanged. Each fix mutation-tested (14 mutations, all caught). `reviews/review-05-builder-repro.py`: FIXED ×11 here, REPRODUCED/ERROR ×11 on `main`.
**Next up:** cheaper-model re-check → merge on Donnie's go → Session 13.
