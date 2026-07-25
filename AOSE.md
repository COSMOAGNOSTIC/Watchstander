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

## Where the discipline is still open

- The non-idempotent multi-package HITL loop (`hitl_gate_node`'s `interrupt()`-in-a-loop pattern) is a known, disclosed gap, not yet restructured — see ARCHITECTURE.md Known Debt.
- `is_over_side`'s underlying semantic model (treated as "overhead" the same as aloft work) is still domain-backwards; only the *labeling* bug on top of it was fixed in Round 3.
- Temporal deconfliction is advertised but not implemented — `check_conflict()` never reads `scheduled_start`/`scheduled_end`.

These are listed here, not hidden, because AOSE's Step 10 says a discovered failure becomes one of three things: fixed and tested, an accepted risk, or documented technical debt. All three categories exist in this repo on purpose.

---

See [ARCHITECTURE.md](ARCHITECTURE.md) for the component map and full decision log (ADR-001 through ADR-013), and [MIGRATION.md](MIGRATION.md) / [PASSDOWN.md](PASSDOWN.md) for the phase-by-phase and session-by-session record this file draws from.
