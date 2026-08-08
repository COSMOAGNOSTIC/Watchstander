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
