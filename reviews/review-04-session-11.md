# Review 04: Session 11 engine checkpoint

**Reviewer:** Codex, separate reviewer agent (runtime model identifier not exposed to this agent)  ·  **Reviewed:** `1f3b716608158436542b6ad63eaa3507bf9bacac..96447220b0db4b5c4dcfd05abe66f228f180807e` (`session-10-carrier-brief`)
**Builder responding:** pending  ·  **Review date:** 2026-11-08

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

### S11-01
- **Verdict:** pending independent builder reproduction
- **Evidence:** pending
- **Disposition:** pending
- **Fix commit / regression test:** pending
- **Reviewer re-check:** pending

### S11-02
- **Verdict:** pending independent builder reproduction
- **Evidence:** pending
- **Disposition:** pending
- **Fix commit / regression test:** pending
- **Reviewer re-check:** pending

### S11-03
- **Verdict:** pending independent builder reproduction
- **Evidence:** pending
- **Disposition:** pending
- **Fix commit / regression test:** pending
- **Reviewer re-check:** pending

## Disputes for Donnie

None yet; builder triage is pending. Hold merges touching these findings until triage and required re-checks are complete.
