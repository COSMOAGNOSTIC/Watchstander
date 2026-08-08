# Adversarial Operational Systems Engineering (AOSE)

**Status:** Proposed / Living Engineering Practice
**Author:** Donnie Langford

## What this is

AOSE is a repeatable engineering discipline for building AI-enabled systems: build the smallest working version, then deliberately try to break it — as an inexperienced user, an expert user, a malicious actor, a failed component, and a changed environment would — before fixing what's found and converting every real failure into a permanent regression test. It treats AI-generated critique as input to be judged, never as authority to be trusted, and it explicitly expects the loop to repeat every time the system changes.

The full methodology is written up separately; this file exists so the practice is traceable *in this repo*, not just described in the abstract. Everything below is a real instance of the loop, not a hypothetical.

## The loop, as it actually happened here

```
BUILD → TRY TO BREAK IT → ASSUME USER ERROR / CLEVER MISUSE / MALICIOUS USE →
ASSUME COMPONENT FAILURE → ASSUME ENVIRONMENT CHANGES →
HAVE OTHER AI MODELS CRITIQUE IT → FIX HIGHEST-RISK PROBLEMS →
ADD REGRESSION TESTS → REPEAT
```

**Round 1 (2026-07-25, "external review response," ADR-007/ADR-008):** an independent Fable-model code review — no shared context with the sessions that built this repo — was asked to trace the code, not read the docs. It found `graph.py` didn't import on a clean install (a required dependency was undeclared, and no test had ever imported the module, so CI stayed green over a broken flagship component), and that the HITL gate's human decision was recorded only as prose, with no structural difference between an approval and a rejection. Both were reproduced directly before being fixed — see MIGRATION.md Phase 5.5.

**Round 2 (2026-07-25, evaluation harness, ADR-009):** rather than leave the same review's domain-correctness findings (no adjacency tolerance on frame ranges, `deck_level` never used, `is_over_side` mislabeled in rationale text, a debatable hazard pair) as qualitative prose, they were converted into `eval/scenarios.py` — a fixed, checked-in scenario suite with four scenarios that deliberately reproduce known gaps on purpose, scored against a committed baseline that CI re-checks on every run. See MIGRATION.md Phase 5.75.

**Round 3 (2026-07-25, second-pass review response, ADR-010 through ADR-013):** a second independent Fable review pass was pointed at the *fixes from Round 1* — asked to line-trace `state.py`, `deconfliction.py`, and `hitl.py` cold. It found the disposition-enforcement fix itself had a fail-open gap (`cleared_for_execution` still defaulted `True` while a review was pending, not just when one was never needed), and that the decision parser could be fooled by hedged text ("approve only if X re-certifies" parsed as `APPROVED`). Both were real regressions in work done earlier the same day, not issues in old code nobody had looked at yet. See MIGRATION.md Phase 5.85.

## Why round 3 matters more than round 1

Round 1 demonstrates that adversarial AI review catches real bugs. Round 3 demonstrates something the methodology needs to keep repeating: **fixing a finding can introduce a new, related failure mode, and only re-attacking the fix (not just the original code) catches it.** A single review pass, however good, is a snapshot — the loop's value is in the "repeat," not the first iteration.

## A caveat this methodology needed, found the same day

The same evening, a *different* external model (Gemini) was asked for a portfolio assessment and produced confident, specific-sounding praise and recommendations — including recommending an addition (a Mermaid architecture diagram in cosmoai-adept's README) that already existed, and a description of this repo's purpose that didn't match what the code does. When asked directly, it admitted it had never fetched the repo — it had pattern-matched on names and prior chat context, not traced anything.

The methodology's existing rule — "AI-generated criticism is input, not authority" — already covered this in principle, but this was the concrete case that earned it a second half: **an AI reviewer can also be confidently, ungroundedly wrong in the *complimentary* direction, not just the critical one.** Uncritical praise from a model that never examined the artifact is exactly as unreliable as an ungrounded criticism, and both need the same check before being acted on: did this reviewer actually look at the thing it's describing? The fix here was direct — a second review was run against the specific files in question, with an instruction to trace cold rather than accept anything at face value (see Round 3 above).

## A verification blind spot the CI badge caught, not any review pass

The evaluation harness added in Round 2 broke CI on every single push from the moment it landed — `tests/test_eval_harness.py` couldn't import the `eval` package, because `eval/` was never registered in `pyproject.toml`'s package list. Every local test run throughout this whole process — including the ones that "verified" Round 2 and Round 3's fixes — used `python -m pytest`, which prepends the current directory to `sys.path` and masked the problem completely. CI runs the plain `pytest` console script, which does not do that, and failed consistently. Neither the original Fable review, the second Fable pass, nor Gemini's or Grok's assessments caught this — it surfaced only because Donnie noticed the GitHub Actions badge and asked about it directly.

This is the same principle as the section above, aimed at a different actor: **verifying a fix by re-running it the same way you always have isn't verification, it's repetition.** The fix here (`eval*` added to `packages.find`, same as `agent_core` already was) was confirmed by installing into a genuinely fresh virtualenv and invoking `pytest` exactly as CI does — the same discipline this document already argues for when judging AI critique, applied to a human-run (i.e. Claude-run) test command that had quietly been checking the wrong thing all along.

**Round 4 (2026-08-08, real HITL reviewer web app, ADR-024):** the finding this round started from didn't come from an AI review pass — it came from Donnie actually watching the visualizer run live for the first time and asking two direct questions: where's the data explaining why a package was flagged, and where's the actual human decision interface. Both answers traced to the same real, previously-undocumented-as-a-gap fact: `events.py`'s broadcast policy correctly keeps review content off the public WebSocket (Section 8/ADR-013), but nothing in the repo had ever built the other half of a HITL system — a real interface where a human reads that content and answers the real `interrupt()`. Every existing consumer of `interrupt()` either hardcoded the answer (`tests/test_graph.py`/`test_hitl.py`) or never touched the real graph at all (`demo_broadcaster.py`'s fully scripted event replay). This is the same class of gap Round 3's "fixing a finding can hide a related failure mode" lesson describes, but caught by a human directly exercising the system end-to-end rather than by a model tracing code.

A second, real bug surfaced while building the fix, caught by testing the actual approve flow rather than by inspection: `state.tasks[i].interrupts` (LangGraph's own state snapshot) keeps listing a `Send()`-fanned-out task's original `Interrupt` object even after that task has been resumed and completed — only `task.result` being non-`None` actually distinguishes "done" from "still genuinely paused." The first version of `reviewer/graph_driver.py`'s `list_pending_reviews()` read `task.interrupts` without checking `task.result`, so an approved package never left the dashboard's pending list even though the underlying graph state (`reviewed_packages`, `hitl_disposition`, `cleared_for_execution`) was already correct. Reproduced directly with a debugging script before the fix, then caught again by `tests/test_reviewer.py::test_approving_one_package_leaves_the_others_pending` actually driving the flow through FastAPI's `TestClient` rather than asserting against `graph.invoke()` in isolation. Fixed by skipping any task where `task.result is not None`.

**Outcome:** one real design gap (no human-facing decision interface existed) closed by building `reviewer/`; one real state-handling bug (stale interrupt objects on resolved tasks) found and fixed by testing the actual end-to-end flow, not the individual functions in isolation. Also verified against a genuinely live running server (`uvicorn` + `curl`), not just the in-process test client, catching nothing further but confirming the in-process tests weren't hiding a request/response-layer issue.

## Where the discipline is still open

- `_fire_watch_capacity_conflicts()`'s size gate checks raw per-fire-watch package count, not per-time-window concurrency — found 2026-08-08 while updating its tests for ADR-023's limit change (1 → 4). A group spread across genuinely non-overlapping schedule windows can still exceed the raw-count gate and get flagged, even though no more than the limit was ever concurrently active. Over-flagging direction, not under-flagging — lower severity than most rows in ARCHITECTURE.md Known Debt, where this is tracked in full. Not fixed this pass.
- `reviewer/` has no auth, no real work-package intake form, and no live-updating dashboard — see ARCHITECTURE.md §8.5 Known Debt. Acceptable for one local reviewer on their own machine; would need addressing before any wider exposure.

## Accepted, not open

- `is_over_side`'s underlying semantic model (treated as "overhead" the same as aloft work) is still domain-backwards, and only the *labeling* bug on top of it was fixed in Round 3 — but this is a deliberate call (2026-07-27, ADR-016), not an oversight. It never causes an under-flag; the conflict is still conservatively caught, only the rationale's wording is domain-imprecise. Tracking it as indefinitely-open competed for attention against gaps that actually affect detection correctness, so it moved to accepted risk instead.
- Temporal deconfliction, previously advertised but not implemented, is now implemented (2026-07-27) — `check_conflict()` reads `scheduled_start`/`scheduled_end` via `_schedules_overlap()`.
- Event payloads previously had no version marker; `events.py` now stamps `schema_version` on every broadcast.

These are listed here, not hidden, because AOSE's Step 10 says a discovered failure becomes one of three things: fixed and tested, an accepted risk, or documented technical debt. All three categories exist in this repo on purpose.

---

See [ARCHITECTURE.md](ARCHITECTURE.md) for the component map and full decision log (ADR-001 through ADR-013), and [MIGRATION.md](MIGRATION.md) / [PASSDOWN.md](PASSDOWN.md) for the phase-by-phase and session-by-session record this file draws from.
