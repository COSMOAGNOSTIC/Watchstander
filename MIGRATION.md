# Watchstander — Migration Plan

> **Goal:** From a deterministic rules-engine scaffold to a fully case-grounded, HITL-reviewed multi-agent safety system — building each phase on a verified previous phase, never freelancing ahead of the plan.
> **Companion doc:** PASSDOWN.md covers team roles and session continuity; this file is the build road.
> **Rule of the road:** one phase per sitting where practical, each phase ends with tests passing. Never start a phase with the previous one's Definition of Done unmet.
> **Last updated:** 2026-07-24

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

**Definition of done:** ✅ Complete — 2026-07-24. HITL reviewer sees a natural-language explanation, not just a template string, and that explanation is traceable to real case data every time.

---

## Phase 3 — Real retrieval (RAG proper)

- [ ] Replace flat JSON lookup with embedding-based retrieval once case count justifies it
- [ ] Evaluate vector store options (lightweight first — avoid over-engineering for ~25-50 cases)

**Definition of done:** Retrieval scales past simple category-matching without losing citation accuracy.

---

## Phase 4 — Case data expansion

- [ ] Round out to 5-10 cases per hazard category (currently light: hot work needs more discrete cases, over-the-side needs dedicated pulls)
- [ ] Continue public OSHA/DOL sourcing only — no Navy data (see PASSDOWN.md Section 7)

**Definition of done:** Every hazard category has 5+ sourced, cited cases.

---

## Phase 5 — Digital twin readiness (deferred)

- [ ] JSON spatial payload export shape defined
- [ ] Not built until Phases 1-4 are solid — explicitly deferred, not urgent

**Definition of done:** N/A — deferred phase, revisit after Phase 4.

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
| 3 — Real retrieval (RAG) | ⬜ | |
| 4 — Case data expansion | ⬜ | |
| 5 — Digital twin readiness | ⬜ (deferred) | |
| 6 — Lock it in | ⬜ | |