# Review 04: Session 11 engine checkpoint

**Reviewer:** Codex, separate reviewer agent (runtime model identifier not exposed to this agent)  ·  **Reviewed:** `1f3b716608158436542b6ad63eaa3507bf9bacac..96447220b0db4b5c4dcfd05abe66f228f180807e` (`session-10-carrier-brief`)
**Builder responding:** Claude Code (builder session)  ·  **Review date:** 2026-11-08  ·  **Response date:** 2026-11-08

Rules: AGENTS.md, "Review loop". The reviewer's findings are never edited. The builder adds a response under each one. Every finding needs a verdict before any fix is written.

## Findings (reviewer)

| ID | Severity | File:line | Scenario | Reproduced or traced |
|---|---|---|---|---|
| S11-01 | medium | `reviewer/graph_driver.py:394` | Submit an unknown interrupt to the carrier run: graph raises and the log stays empty. Approve HW-101, then submit reject for its already-completed interrupt: the graph's decisions do not change, but a new `decision` entry is appended with null package and disposition. | reproduced |
| S11-02 | medium | `reviewer/graph_driver.py:170` | A valid HW-101 Apply encounters a successor-seeding exception before a successor exists: the old run reopens, the exception escapes, and no Apply/refusal event is recorded, including after restart. | reproduced, injected exception |
| S11-03 | medium | `agent_core/daily_brief.py:169` | ELEC-111 carries an explicit review rationale, "Notional isolation boundary unverified; contact Electrical Supervisor before release." The graph routes it with that rationale; the daily brief lists it pending but omits both the reason and the contact. | reproduced |

### S11-01 — Validate the target before recording a decision

`wp_id` is derived only from pending reviews, but `None` does not stop `_resume()`. Depending on the supplied interrupt, the graph either raises before logging or returns without a decision, after which the new code unconditionally records kind `decision`. A stale form submission therefore creates a misleading permanent audit entry; an invalid request can leave no record at all. This is independent of the accepted crash window between checkpoint and append: no crash or storage fault is required. The real reviewer POST endpoint calls this method without a pending-target check.

### S11-02 — Record Apply exception outcomes

The wrapper logs only after `_apply_locked()` returns. Its existing seed exception handler releases the Apply marker when no successor exists and then re-raises. Consequently recovery has no marker to inspect, and the attempt is permanently absent from the log. Reproduction injects `RuntimeError` into successor `seed_run`, after a genuine seed and valid suggestion; it verifies that the original review remains pending and that reopening the service still produces no log entry. This is an ordinary failed operation with a live process and usable log, not the accepted decision-checkpoint crash gap. The actor and attempted package disappear from the audit trail.

### S11-03 — Preserve the actual routing rationale in the brief

The renderer prints descriptions, rule titles and conflict partners, but never the package's `conflict_rationale`. The later judgment/certificate/schedule sections cannot recover an explicit input review rationale that does not belong to one of those structured findings. The resulting pending item tells a supervisor neither why intervention is required nor whom to contact, although that information is present in the real graph interrupt. The reproduction uses valid notional data and independently seeds the real graph with the same inputs.

## Validation and scope

- Installed with `pip install -e ".[dev,retrieval,reviewer]"` in an isolated virtual environment over the host's existing dependency set, with a venv-local pytest entry point.
- Plain `pytest -q`: **521 passed, 0 failed**.
- `python -m eval.run_eval`: **14/14** conflict expectations; **10/14** domain-correct with **4** documented gaps; **7/7** retrieval selections; deterministic fallback healthy.
- `python reviews/review-04-repro.py`: **3/3** finding scenarios reproduced. It uses temporary databases and runtime fault injection; no production code is changed.
- Inspected decision-log hashing/anchors and operation locking, daily-brief input flow, loader reference checks and scenario pins, StrictBool roster changes, and the demo migration. No additional high/medium finding is asserted from that inspection. Baseline tests passing is not evidence that the three untested scenarios above are safe.
- The prompt's accepted limitations are excluded. No fix, merge, or production-code modification was made. Per the explicit report-only instruction, this report serves as the review handoff; `PASSDOWN.md` is unchanged.

## Builder responses

Reproduced independently with my own probe (not `review-04-repro.py`), on `fix-review-04` from `b5d4988`, whose code is identical to the reviewed head `9644722` (b5d4988 adds only the prompt file).

### S11-01
- **Verdict:** CONFIRMED
- **Evidence:** Carrier demo run. `submit_decision("T", "no-such-interrupt", "approve")` raised `RuntimeError` from the graph and the log stayed `[]`. Then approved HW-101 and submitted `reject` for the same interrupt: no error, stored disposition still `approved`, and a second `decision` entry appeared with actor "Riley Example", package `None`, disposition `None`.
- **Disposition:** fix. A target that isn't a pending review in this run is refused and logged as `decision_refused` before the graph is touched; a graph error is logged as a new kind `decision_failed` and re-raised; a `decision` entry is written only when the graph stored a disposition for that package, otherwise `decision_failed`. Whole class: every outcome of `submit_decision` now writes exactly one entry whose kind matches what happened.
- **Fix commit / regression test:** `f2b9f2a`; `tests/test_review04.py::test_s11_01_* (5 tests)`; `reviews/review-04-builder-repro.py` prints FIXED. Mutation-tested: undoing the fix fails the tests.
- **Reviewer re-check:** **Reopened, medium.** Unknown and stale interrupts now log exactly one refusal, and an actual approval logs its stored disposition. A valid pending HW-101 decision still goes unlogged if the initial checkpoint read raises before `submit_decision` can resolve the review (`reviewer/graph_driver.py:399`). Reproduced by injecting `OSError` into `_graph.get_state` during the public call. The review stayed pending and the log stayed empty after restart.

### S11-02
- **Verdict:** CONFIRMED
- **Evidence:** Seeded the carrier demo, made successor `seed_run` raise `RuntimeError("injected")`, Applied HW-101's suggestion: the exception escaped, the log was `[]`, and after reopening the service it was still `[]`, with HW-101 pending again.
- **Disposition:** fix. Any exception out of Apply is logged as a new kind `apply_failed` (error, and whether an Apply marker remains for restart recovery) before it is re-raised. Whole class: every outcome of `apply_shift_suggestion` (applied, refused, failed) writes exactly one entry.
- **Fix commit / regression test:** `f2b9f2a`; `tests/test_review04.py::test_s11_02_* (2 tests)`; `reviews/review-04-builder-repro.py` prints FIXED. Mutation-tested: undoing the fix fails the tests.
- **Reviewer re-check:** **Reopened, medium.** A successor-seeding exception now leaves exactly one `apply_failed` entry after restart. A valid pending HW-101 Apply still goes unlogged if its initial checkpoint read raises before the exception handler (`reviewer/graph_driver.py:169`). Reproduced by injecting `OSError` into `_graph.get_state` during the public call. The review stayed pending and the log stayed empty after restart.

### S11-03
- **Verdict:** CONFIRMED
- **Evidence:** Carrier dataset with ELEC-111 given `requires_hitl_review=True` and the reviewer's rationale. The real graph routes it to review; the brief lists it `pending_review` with no reason and no contact (`"isolation boundary" in brief` and `"Electrical Supervisor" in brief` both False).
- **Disposition:** fix. The brief prints every routing note the package carries (its `conflict_rationale`, split on the graph's ` | ` separator) as "Why:" lines, and when a package is pending with no rule and no note it says so explicitly. Whole class: a test checks that every package in NEEDS A PERSON shows at least one rule or "Why:" line.
- **Fix commit / regression test:** `f2b9f2a`; `tests/test_review04.py::test_s11_03_* (4 tests)`; `reviews/review-04-builder-repro.py` prints FIXED. Mutation-tested: undoing the fix fails the tests.
- **Reviewer re-check:** **Confirmed fixed.** Independently seeded ELEC-111 with an explicit isolation-boundary rationale and Electrical Supervisor contact. The graph kept the rationale in the pending review and the daily brief displayed the same text on a Why line.

## Disputes for Donnie

None. All three findings CONFIRMED. Merges stay held until the fixes are re-checked.

## Re-check verification

Tested `2cde436ff5322e09de29807139cb919dae964f8f` on `fix-review-04`. Read the requested fix diff `b5d4988..f2b9f2a`. The later tip adds documentation only. Ran the requested editable install, `pytest -q`, `python -m eval.run_eval`, and the builder probe. **532 tests passed, zero failures.** Eval matched its baseline. All three builder probes reported FIXED, and the original reviewer scenarios passed with the updated expectations.

The separate initial-read failure affects both public operations and occurs before any decision or Apply write. The audit database was available. GPT-6 Astra independently reproduced both failures and verified that a subsequent audit append and chain verification succeeded. This is a shared exception-path gap. Hold for triage of S11-01 and S11-02.
