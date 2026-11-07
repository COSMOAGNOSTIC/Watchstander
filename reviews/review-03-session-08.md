# Review 03 · Session 8 brief and Apply

Reviewed `session-08-brief-apply` at **`2f94ed570302cc106062c36731592f68fb7553a3`**, against `main` at **`91405be784bc32889c725012d50c45865f5bfc26`**. The branch began this review at `82afd02829db9f07946d0dce60c14d32341ee558` and advanced with an AGENTS/AOSE documentation-only commit. That update was read and included before the final test run. All code probes apply to the final reviewed SHA because executable code and tests are identical across those two branch commits.

**Hold for triage.** Four high-severity findings affect Apply state transitions or human-review routing. One medium finding hides rejection evidence, and one low-severity test observation covers the explicitly requested test-quality check. All findings below were reproduced. All data was synthetic and all databases were temporary, outside tracked files.

## Findings

### S08-01 · high · Concurrent Apply requests create two active successors

**Locations:** `reviewer/graph_driver.py:116–153`, `reviewer/registry.py:43–48`. **Reproduced with two real service instances sharing one SQLite database.**

Seed the ordinary WELD-1 / TANK-ENTRY conflict, with different crews, both scheduled in DAY at TANK-4. Each pending review contains a valid suggestion moving its own crew to SWING. Start Apply for both pending reviews concurrently. A barrier after each fresh suggester result forces both requests past the pending-review check before either closes the old run.

Both calls returned `ApplyResult(applied=True)`. Two different successor runs were registered, each with its own open review. One moved WELD-1 to SWING and kept the entry in DAY, while the other moved the entry to SWING and kept WELD-1 in DAY. The old run's `superseded_by` row names only the last successor because it uses replacement semantics.

There is no run-level claim or transaction spanning the pending check, exact-match check, replacement creation and supersession. Both new plans remain active even though they are incompatible alternatives to the same old plan. If their independently offered moves are both followed, the crews meet in SWING. Serial double Apply is correctly refused, but it does not cover this race.

```text
Apply WELD review                      Apply ENTRY review
       |                                      |
 old review pending                     old review pending
       |                                      |
 own move matches                       own move matches
       |                                      |
 create successor A                     create successor B
       \                                      /
             replace old superseded_by row
                          |
      two active successor plans, only one recorded successor
```

### S08-02 · high · Interrupted Apply leaves the old schedule reviewable

**Location:** `reviewer/graph_driver.py:147–153,170–202`. **Reproduced by fault injection, then service restart.**

Seed the same ordinary conflict and Apply the weld suggestion. Inject a checkpoint-write failure at the first `submit_decision` used to reject the old reviews, after `seed_run` has persisted and registered the successor.

Apply raises. After closing and reopening the service, the pending queue contains both old reviews plus the moved weld review in the new run. The old run has no supersession record. Submitting approval to the old weld review still succeeds and marks that old-schedule package cleared.

Replacement creation, old review closure and supersession are separate durable writes without recovery state. A failure or interruption in that interval leaves contradictory work available for action. The supersession registry also is not consulted when listing pending reviews or submitting decisions. The fault injection establishes this partial-write behavior; it does not claim an actual disk error occurred during ordinary tests.

### S08-03 · high · Apply carries a seeded approval into the moved schedule

**Location:** `reviewer/graph_driver.py:138–144`. **Reproduced through `seed_run` and Apply.**

Seed WELD-1 with `hitl_disposition=APPROVED` and `cleared_for_execution=True`, alongside the ordinary conflicting entry. This is accepted `WorkPackageState` input, such as an imported previously reviewed package. The conflict sends it to review in the old run.

Apply its clean shift suggestion. The new run contains the moved weld package with all three of these fields:

- `hitl_disposition="approved"`
- `requires_hitl_review=True`
- `cleared_for_execution=True`

The new pending interrupt also exists, so the package simultaneously awaits a new decision and advertises clearance. Apply copies every seeded field and changes only schedule bounds and the review-required flag. The construction validator closes clearance only when disposition is absent. Apply must invalidate the old approval and clearance for the moved schedule. This is carried approval, rather than a new approve decision submitted by Apply.

The checked-in never-approves test uses fresh undecided inputs and checks the list of completed decisions, which cannot reveal this inconsistent pending state.

### S08-04 · high · WS-JF-006 never reaches the normal graph review gate

**Locations:** `agent_core/graph.py:48–58`, `agent_core/reasoning.py:311–322`, new trigger at `agent_core/judgment.py:244–247`. **Reproduced through the public reviewer service.**

Seed one scheduled `working_aloft` package with no frame range, using a valid crew and calendar. Calling `judgment_flags` on it returns `WS-JF-006` routed to the Safety Officer.

Calling `ReviewerService.seed_run` on the same data produces no pending review. The graph's `reviewed_packages` contains the package with `cleared_for_execution=True`, `requires_hitl_review=False` and no safety brief.

The graph still routes only detection conflicts or existing review flags. The new judgment rule runs during candidate checking only if another finding already caused reasoning to generate a suggestion. There is no normal graph step that takes the standalone overhead judgment and requires the promised human review. Direct rule tests establish the catalogue recipient, but not the graph route. This is the new rule exposed through an inherited integration gap.

### S08-05 · med · The brief and reviewer hide why every shift failed

**Locations:** `agent_core/reasoning.py:233–235`, `reviewer/app.py:138–151`. **Reproduced through the HTTP detail page.**

Seed the ordinary conflicting weld/entry pair, with WELD-1 requiring a hot-work permit valid only for its original 07:00–11:00 job. Every later candidate fails certificate coverage. The stored `shift_outcome.rejected` correctly contains `WS-CT-001` for the candidate shifts.

The recommendation only says that no shift among the next six passes every check and that six shifts were rejected. The reviewer detail page renders that sentence and no rejection entries. It contains neither `WS-CT-001` nor the certificate failure explanation. The same renderer omits plain-text `RejectedShift.reasons`, including overhead uncertainty and shift-fit failures.

The reviewer cannot distinguish a permit problem from staffing or location problems even though the exact evidence was computed and persisted. Render the structured rejections or include their reasons in the deterministic brief.

### S08-06 · low · The no-suggestion test accepts fabricated suggestion text

**Location:** `tests/test_session08b.py:67–71`. **Reproduced by an in-memory mutation.**

The test named `test_brief_explains_when_there_is_no_suggestion` accepts either suggestion prefix and does not assert that its fixture actually lacks a suggestion. Replacing `describe_shift_outcome` with a function always returning “Suggested, not applied: fabricated move” still passes this test.

A real no-suggestion fixture, with assertions on the outcome and rejection reason visible to the reviewer, would cover the intended behavior and help catch S08-05. This finding concerns this individual test.

## Checks that came out clean

- **Workflow and eval.** On the final head, ran `pip install -e ".[dev,retrieval,reviewer]"`, plain `pytest -v`, and `python -m eval.run_eval` using Python 3.12.14 in the existing isolated review environment. **431 tests passed in 1.74 seconds.** Eval reports **14/14** documented conflict expectations matched, **10/14** domain-correct with four existing known gaps, **7/7** retrieval cases correct and a healthy deterministic fallback. The baseline comparison passed.
- **Model output and rule 7.** Exercised the actual `_call_llm` JSON parsing path with a stubbed SDK response containing an extra `recommended_action="UNTRUSTED MODEL ACTION"`. The model summary was used, but the action was discarded by parsing and the final recommendation was deterministic. Existing tests also exercise a direct model-call stub with the unwanted field. The partnerless template bypasses the model. No live model call was made.
- **Exact-match refusal.** Changed an otherwise valid freshly calculated suggestion's start by one minute in memory. Apply refused it, preserved the old inputs and created no successor. The suite also covers a fresh check returning no suggestion. No ordinary sequential path bypassing this comparison was found.
- **Round trips and restart.** Seeded aware schedules, an aware calendar and an actual certificate model. Closed and reopened the SQLite-backed service. `run_inputs` and `shift_outcome` survived unchanged, and the outcome validates as `CrewShiftOutcome`. Apply succeeded after reload. The old seeded inputs stayed unchanged. Another restart retained supersession and the replacement review.
- **Serial double Apply and decided reviews.** A second Apply after successful completion is refused, including after restart. Apply on an already-approved pending review ID is also refused when that decision completes before the Apply call starts.
- **Fresh undecided inputs.** On ordinary serial Apply, moved packages are pending, uncleared and have no disposition. All old pending reviews are rejected, the successor is recorded, and the old run has no open review. S08-01 through S08-03 describe the concurrency, interruption and imported-state limits of these positive checks.
- **Overhead detection.** Independently checked 48 combinations of hazard label, spatial flag, moved-side ordering, overlapping/touching/disjoint frames and touching/separated times. The shared detector returns the overhead rule and names the correct package when exactly one package is overhead. Both-overhead pairs retain the explicitly tested existing exclusion. The new Safety Officer rule is correct when called directly, subject to the graph gap in S08-04.
- **Input purity and presentation.** Seeding preserved the caller's supplied package models. Successful moves preserve old `run_inputs`. The existing HTTP tests confirm the Apply button and result banner, and the manual detail-page probe verified the rejection-evidence omission. HTTP behavior was tested through FastAPI's test client.

All additional probes, concurrency barriers, SDK stubs and fault injection were outside tracked source. This commit contains the review report and the required PASSDOWN entry.

---

## Builder responses

**Builder:** Claude Code (Opus). **Date:** 2026-11-07. Rules: AGENTS.md, "Review loop". The reviewer's text above is unchanged. Reproductions rebuilt from the descriptions in `reviews/review-03-repro.py`, run at the reviewed SHA `2f94ed5`, each with its own temporary database: **6/6 reproduced**, no errors.

| ID | Verdict | Builder's observed result | Planned fix |
|---|---|---|---|
| S08-01 | CONFIRMED | Two service instances on one database, barrier after the suggester: both Applies returned `applied=True`, creating successors `T1-applied-215b24e3` and `T1-applied-4239c41e`. | An atomic per-run **claim** (a primary-key insert in the registry) is taken *before* anything else. A second Apply on the same run, from any process, can't get the claim and is refused. |
| S08-02 | CONFIRMED | Injected failure at the first old-review rejection, then restart: both old reviews were still pending, and approving old WELD-1 cleared it. | From the moment of the claim, the old run is **closed to decisions**: hidden from the pending list, and `submit_decision` refuses it. Recovery on service start: a claim whose successor exists is finished (old reviews rejected, marked done); a claim with no successor is released, so the old run becomes reviewable again and nothing changed. |
| S08-03 | CONFIRMED | Moved WELD-1 in the new run: `disposition=approved`, `cleared=True`, `requires_review=True`. | Moved packages lose `hitl_disposition` and clearance, so they always need a fresh decision. Every successor package also drops the stale derived fields (`conflicts`, `conflict_rationale`, `safety_brief`), which the new run recomputes. |
| S08-04 | CONFIRMED | `judgment_flags` returned `WS-JF-006`, but `seed_run` left 0 pending reviews. | A **judgment** node in the graph between detection and reasoning. Every package named by a judgment flag is marked `requires_hitl_review`, with the flag, rule, and routed person recorded in its rationale, so it reaches the review gate and gets a brief. This applies to all judgment rules, not just WS-JF-006 (the whole bug class). |
| S08-05 | CONFIRMED | Stored rejections held `WS-CT-001`; the detail page didn't show it. | The deterministic sentence lists each rejected shift with its rule IDs and reasons, and the detail page renders the rejection list. |
| S08-06 | CONFIRMED | The no-suggestion test passed with fabricated suggestion text. | A fixture that guarantees no suggestion, with assertions on the outcome, the reason, and the visible rejection evidence. |

**Severity:** no disagreement. **Disputes for Donnie:** none.

**Note on S08-04's scope (for Donnie):** routing every judgment flag to human review means packages that previously passed straight through (unlocated hot work, simultaneous entries, inconsistent classification, and so on) now pause for a decision. That is what "a person must decide" means, but it's a behaviour change across all judgment rules, not only the new one.

## Fixes

Review findings: commit `c9314ec`. Builder-found same-class gap: commit `3578393`. Regression tests: `tests/test_review03_fixes.py` (`test_s08_*`), `tests/test_findings_gate.py`, and the rewritten `test_brief_explains_when_there_is_no_suggestion`. Full suite **457 passed**; eval baseline unchanged. (`c9314ec`'s commit message says 445; the true count at that commit was 444, because one weak test was replaced rather than added.)

| ID | Fix | Regression test(s) |
|---|---|---|
| S08-01 | Atomic per-run Apply claim, taken before anything else; any second Apply on the run, from any process, is refused | `test_s08_01_two_applies_that_both_pass_the_pending_check_yield_one_successor` (reproduces the reviewer's ordering), `test_s08_01_apply_on_a_superseded_run_is_refused` |
| S08-02 | A claimed or superseded run is closed to decisions (hidden from the queue; `submit_decision` raises; the app reports it). Startup recovery finishes an Apply whose successor exists, or releases the claim | `test_s08_02_*` (3) |
| S08-03 | Moved packages lose disposition and clearance; successor inputs drop stale derived fields | `test_s08_03_*` (2) |
| S08-04 | `judgment_node` in the graph routes every package named by any judgment flag to review | `test_s08_04_*` (4) |
| S08-05 | The deterministic sentence and the detail page list each rejected shift with its rule IDs and reasons | `test_s08_05_*` (3) |
| S08-06 | A guaranteed no-suggestion fixture, with outcome and evidence assertions | rewritten test in `tests/test_session08b.py` |

**Mutation checks (AGENTS.md, Review cost policy):** each fix was disabled in turn. Two tests passed under their mutation at first: the S08-01 race test paused *after* the claim, and the S08-05 page test matched brief text. Both were strengthened and now fail under their mutations.

**Builder-found, same class as S08-04 (Donnie approved fixing now):** certificate and schedule findings never reached review either. A hot-work job with no permit on file, and a job outside every shift, both passed as cleared. `findings_node` (deconfliction → judgment → findings → reasoning) now routes any certificate finding (none on file counts as MISSING), and any schedule finding when the run has a calendar. Four mutations, all caught.

**New behaviour to check:** more packages now pause for review (any judgment flag, missing or partial permit coverage, and schedule findings). The startup recovery runs when a service starts; a recovery racing a live Apply in another process isn't covered.

## Reviewer re-check

Tested current `session-08-brief-apply` tip **`78fad145f2dbcb41920d85d5afa43029a8253763`**. Scoped code review to `git diff 43886e6..HEAD -- agent_core reviewer tests`. **Five confirmed fixed. S08-01 and S08-02 reopened**, both through live Apply racing service startup recovery. Hold for triage.

| ID | Verdict | Scenario and result |
|---|---|---|
| S08-01 | reopened | **High**, `reviewer/graph_driver.py:130–133,182–192`. The named two-Apply regression passes when both services are already running. A service starting during a live Apply can delete its claim. Both Applies then succeed and register separate successors. Reproduced below. |
| S08-02 | reopened | **High**, `reviewer/graph_driver.py:182–192,202–205,278–288`. The named crash/restart cases pass when no Apply is still running. Starting a service during a live Apply makes its old review actionable again. Reproduced an old approval while Apply was paused, followed by successful Apply on the same review. |
| S08-03 | confirmed fixed | Seeded approval and clearance are removed from the moved weld package. The replacement inputs show no disposition, false clearance, and required human review. The stale-derived-fields regression passes. |
| S08-04 | confirmed fixed | A standalone unlocated overhead job now has a pending review with WS-JF-006 and Safety Officer in the rationale. The gate leaves it uncleared. The separate gas-free judgment test and clean-job control pass. |
| S08-05 | confirmed fixed | With a permit valid only for the original shift, the brief includes the rejected shifts and WS-CT-001. The HTTP detail-page test checks the actual rejection list item. A reason-only rejection is also present in the deterministic text. |
| S08-06 | confirmed fixed | The rewritten fixture has no suggestion because the permit expires at the original end. The probe injecting fabricated suggestion text fails the rewritten test, which also checks the stored outcome and WS-CT-001. |
| Builder-found findings gate | confirmed fixed | A missing or expiring permit and an out-of-calendar job reach review with their findings and remain uncleared while waiting. The two-package double-booking case routes both packages. Full permit coverage and clean schedule controls pass. Schedule checks remain conditional on calendar data. |

### Reproduced startup-recovery race

Use the real reviewer service and the builder's two-crew fixture in a temporary SQLite database. Start Apply A for WELD-1. Pause it inside the fresh suggester call, after verifying its claim exists and before seeding its successor. Construct service B on the same database. Its startup recovery finds no successor inputs yet, treats A's claim as abandoned, and deletes it while A is still running.

```text
A holds live Apply claim + successor has not been written yet
                         |
                 B starts recovery
                         |
         no successor inputs -> delete A's claim
                       /   \
        B can Apply          B can approve old review
              |                        |
         A resumes                A resumes
              |                        |
      two successors          old approval retained on old run
```

- **S08-01:** Let B Apply the entry crew's suggestion to completion, then let A resume with the actual suggester. Both results were `applied=True`. Both successor IDs were registered. A's final supersession write replaced B's.
- **S08-02:** In a separate database, use B to approve the old WELD-1 review during A's pause. Approval is accepted and clears the old package. A then returns `applied=True` for that same review. The superseded run retains WELD-1 as approved and cleared. Its still-pending entry review is rejected.

Both interleavings were forced in memory using the actual service, graph, database and suggester. The builder already identified live-startup recovery as uncovered. The missing distinction is between a crashed owner and a live owner that has not yet written its successor.

### Verification

Ran `pip install -e ".[dev,retrieval,reviewer]"`, `pytest -q`, `python -m eval.run_eval`, and `python reviews/review-03-repro.py`. **457 tests passed, zero failures.** Eval matched the baseline: 14/14 documented conflict expectations and 7/7 retrieval cases, with deterministic fallback healthy.

The builder probe printed NOT REPRODUCED for all six items. Its S08-01 worker also raised `BrokenBarrierError`: the probe waits for both workers inside the suggester, but the new claim refuses one worker before that point. The named regression tests place the barrier before the claim and establish the already-running-service control. The two live-startup probes above are separate from the builder script.

The conditional escalation to GPT-6 Astra independently reproduced S08-02 with the real graph and temporary SQLite and confirmed the shared recovery defect reopens both findings. It verified that the old weld approval remains cleared after supersession.

### Builder response to the re-check

**Builder:** Claude Code (Opus). **Date:** 2026-11-07. The reviewer's text above is unchanged. Both reopened scenarios were rebuilt (`reviews/review-03-repro.py`, `S08-0x-recheck`) at the tested SHA `78fad14`: **2/2 reproduced**. With service B started while Apply A was paused after its claim: B's Apply succeeded and A's did too (two successors), and B's approval of old WELD-1 was accepted and stayed cleared after A superseded the run.

| ID | Verdict | Root cause |
|---|---|---|
| S08-01 | CONFIRMED | Startup recovery treated every open claim without a successor as a crash and deleted it, including a live Apply's. |
| S08-02 | CONFIRMED | Same root cause, plus a **builder-found race of the same class**: `submit_decision` checks "closed?" and then resumes. An Apply in another process can claim in between, so an approval can land after the claim even with no restart. |

**Fix design (one mechanism for all three):**
- **One lock per run, for both Apply and decisions.** Apply and `submit_decision` both take an atomic per-run lock (a primary-key insert) for their whole check-then-write sequence. If either is held, the other is refused with "run busy". Neither can interleave with the other, in any process.
- **Leases, not guesses.** Each lock records when it was taken. Startup recovery acts only on locks older than the lease (default 10 minutes, far longer than an Apply takes). A live Apply is never treated as crashed. Within the lease, an interrupted run stays closed, which fails safe.
- **Defense in depth.** `list_decided` reports `cleared_for_execution=False` for any package in a superseded run, so an old-schedule approval can never read as cleared, whatever happened.

**Disputes:** none. **Trade-off for Donnie:** after a real crash, the old run stays closed for up to the lease (10 minutes) before recovery releases or finishes it, instead of immediately.

### Re-check fix

Commit `bbb1c51`. New regression tests are `test_recheck_*` in `tests/test_review03_fixes.py`. Written first: 7 failed. Full suite **462 passed**; eval baseline unchanged. The `S08-0x-recheck` probes in `reviews/review-03-repro.py` no longer reproduce.

| ID | Fix | Regression test(s) |
|---|---|---|
| S08-01 | One atomic per-run lock (`registry.run_locks`) held by Apply for its whole sequence; recovery acts only on locks older than `lease_seconds` (default 600) | `test_recheck_s08_01_service_starting_during_a_live_apply_cannot_apply_too` |
| S08-02 | The same lock is held by `submit_decision` across check-then-resume; a young lock is never released by recovery; superseded runs never report cleared | `test_recheck_s08_02_*` (3), `test_recheck_superseded_run_never_reports_cleared` |

**Builder-found same-class race, fixed by the same lock:** `submit_decision` checked "closed?" and then resumed, so an Apply in another process could claim the run in between. Covered by `test_recheck_s08_02_apply_is_refused_while_a_decision_is_being_recorded`.

**Mutation checks:** recovery ignoring the lease, a decision taking no lock, Apply ignoring the lock, and superseded approvals reading as cleared: all four now fail a test. The decision-lock mutation was initially ineffective (it still took the lock) and was redone.

**Trade-off:** after a real crash, the old run stays closed for up to the lease before recovery releases or finishes it. The two crash-restart tests now construct the service with `lease_seconds=0` to model a restart after the lease expires.

**Note on the builder's original S08-01 probe:** it reported NOT REPRODUCED with a `BrokenBarrierError` in one worker, because the claim now refuses one worker before the barrier. That was expected, and the reopened race is covered by the new tests.

### Reviewer re-check 2

Tested the current `session-08-brief-apply` tip **`557f3f6c1546997333c98efc6f5067288369783b`**. Code inspection was limited to `git diff 5ae3946..HEAD -- reviewer tests`.

| ID | Verdict | Scenario |
|---|---|---|
| S08-01 | reopened | **High, reproduced.** A service starting within a live Apply's lease leaves its lock intact. After the default 600-second lease expires, startup recovery deletes the lock even if the owner is still live. Both requests can then create successors. See `reviewer/graph_driver.py:171,192–205`. |
| S08-02 | reopened | **High for expired-owner approval, medium for the stale pending read. Both reproduced.** A decision already holding the lock blocks Apply. A decision that completes after Apply reads the pending review but before Apply acquires its lock does not block it. Apply proceeds using the stale review. An expired live Apply also permits an old approval after a second service starts. See `reviewer/graph_driver.py:124–143,192–205,294–310`. |

**S08-01 reproduction.** Seed T1 with WELD-1 and TANK-ENTRY pending. Pause service A's Apply inside the real suggester after it acquires the lock. Advance only the reviewer's clock by 601 seconds, then start service B on the same SQLite database. B removes A's lock because the successor has yet to be seeded. Let B Apply TANK-ENTRY and then let A resume. Both return `applied=True` and register distinct successors. The simulated elapsed time models a suspended or delayed owner. A can still write the successor after recovery removes its lock because the operation does not verify ownership before seeding.

**S08-02 reproduction.** Start two services on the same database. Let Apply A read the pending WELD-1 interrupt. Before A acquires the lock, have service B approve that same interrupt and release its decision lock. Verify WELD-1 is no longer pending. Resume A. It acquires the lock, checks only supersession, and successfully Applies the stale review. This reproduced with the default lease and without advancing the clock. In a separate database, let a live Apply's lease expire as above and have the newly started service approve the old review. The approval is accepted and reads as cleared while A is still active. After A supersedes the run, the new reporting mask correctly hides that clearance.

```text
Apply reads pending review
            |
Decision locks -> approves review -> releases lock
            |
Apply acquires lock -> checks supersession -> uses stale review
            |
     successor created
```

The probes used the real services, graph, and suggester with temporary SQLite databases. In-memory hooks forced the ordering. The lease probe advanced a test clock instead of waiting ten minutes.

**Verification.** Ran the requested install, `pytest -q`, `python -m eval.run_eval`, and `python reviews/review-03-repro.py`. **462 passed, zero failures.** Eval matched its baseline. Both `S08-0x-recheck` probes reported NOT REPRODUCED. The historical S08-01 probe still emits its documented worker `BrokenBarrierError`. The named regressions pass for startup within the lease, a decision holding its lock when Apply tries to acquire it, and clearance masking after supersession. The reproduced interleavings above exercise different boundaries. Hold for triage.

The conditional escalation to GPT-6 Astra independently reproduced the two-successor failure and the stale pending read at the same SHA. The stale-read scenario creates a successor requiring a new human review. The expired-owner approval scenario above separately demonstrates old-schedule clearance while Apply is active.

### Builder response to re-check 2

**Builder:** Claude Code (Opus). **Date:** 2026-11-07. The reviewer's text above is unchanged. Both scenarios were rebuilt at the tested SHA `557f3f6` (`reviews/review-03-repro.py`, `*-recheck2-*`): **2/2 reproduced**. A live Apply whose lease had expired (clock advanced 601 s) lost its lock to a newly started service, and both Applies succeeded. An Apply that read the review before another service approved it went on to apply the stale review.

| ID | Verdict |
|---|---|
| S08-01 | CONFIRMED |
| S08-02 | CONFIRMED |

**Why this is the third round, and the change of approach.** Rounds 1 and 2 each closed one interleaving with per-run claims, then leases. A lease can't prove its owner is dead (it may be stalled, suspended, or slow), so cross-process recovery based on time will always have another race. The reviewer app is documented as a local, single-reviewer tool (ARCHITECTURE.md §8.5). The provable design makes that explicit:

1. **One service per database.** `ReviewerService` holds an exclusive OS file lock (`flock` on `<db>.lock`) for its whole lifetime. A second service on the same database refuses to start. The OS releases the lock when the owning process exits for any reason, including a crash or kill.
2. **Recovery only with exclusive ownership.** Startup cleanup runs after the file lock is held, so no other live owner can exist. Every leftover Apply marker is therefore from a dead owner, and is finished (successor exists) or released (no successor). No clock, no lease.
3. **In-service serialization.** One re-entrant lock covers `apply_shift_suggestion` and `submit_decision` end to end. Apply re-reads the pending review inside the lock and refuses if it was decided meanwhile.
4. **Kept from round 2:** superseded runs never report cleared. Apply also releases its own marker if it fails before creating a successor.

**Trade-off for Donnie:** two reviewer app instances can't share one database at the same time. The second gets a clear error. Multi-user review would need a real database server and a proper transaction design, which is out of scope for Sessions 12–15 unless you want it.

**Disputes:** none.

### Re-check 2 fix

Commit `4865ce3`. Tests: `test_recheck2_*` in `tests/test_review03_fixes.py` (8), with the earlier concurrency tests rewritten for one-service-per-database. Full suite **465 passed**; eval baseline unchanged.

| Property | Test |
|---|---|
| A second service on the same database refuses to start; closing releases it | `test_recheck2_a_second_service_on_the_same_database_refuses_to_start`, `test_recheck2_closing_a_service_lets_another_open_the_database` |
| Concurrent Applies in one service yield one successor | `test_recheck2_concurrent_applies_in_one_service_yield_one_successor` |
| A decision during a live Apply is refused once Apply finishes; nothing on the old run reads cleared | `test_recheck2_decision_during_a_live_apply_is_refused_once_apply_finishes` |
| Apply re-reads the review inside the lock (the reviewer's stale-read ordering) | `test_recheck2_apply_rereads_the_review_and_refuses_one_decided_meanwhile` |
| A decision mid-write holds off Apply (direct proof of serialization) | `test_recheck2_a_decision_in_progress_holds_off_apply_until_it_finishes` |
| Failure before a successor reopens the run immediately | `test_recheck2_failure_before_a_successor_reopens_the_run_immediately` |
| A real process killed mid-Apply (`os._exit`) is recovered by the next service | `test_recheck2_a_process_killed_mid_apply_is_recovered_by_the_next_service` |

**Mutations, all caught:** no exclusive database lock; Apply not serialized; decision not serialized; no re-read inside the lock; no recovery; no reopen on early failure.

**Reading `reviews/review-03-repro.py` now:** every probe that opens a second service on the same database reports ERROR "another reviewer service already has this database open". That refusal is the fix. The rest report NOT REPRODUCED. The script's original S08-01 probe also leaked a patched function into the next probe when it failed; that was fixed in the script, and S08-03 no longer errors.

### Reviewer re-check 3

Tested **`23b05e8abe810cc90444bec1ff8408c125882e31`**, the current `session-08-brief-apply` tip. Code inspection was limited to `git diff 557f3f6..HEAD -- reviewer tests`.

| ID | Verdict | Scenario |
|---|---|---|
| S08-01 | reopened | **High, reproduced.** Two services using the identical database path are excluded as intended. With a symlink alias to that same SQLite database, a second service starts, removes the first service's live Apply marker during recovery, and successfully Applies a different review. The first service resumes and also succeeds. |
| S08-02 | reopened | **High, reproduced.** The in-service decision and Apply ordering tests pass, including the stale pending read. A second service using the symlink alias can still approve the old review during a live Apply. The old approval is visible as cleared before supersession. |

**Shared cause** at `reviewer/graph_driver.py:79–86,222–234`. The exclusive lock is tied to the supplied path plus `.lock`. A symlink to the database file resolves to the same SQLite database, but its separately named lock file does not resolve to the first service's lock file.

```text
A opens r.db     -> holds r.db.lock     -> pauses after writing Apply marker
B opens alias.db -> holds alias.db.lock -> reads same database through symlink
                                          |
                                   recovery removes A's marker
                                          |
                       B can Apply or approve an old review while A is live
```

**Reproduction.** Seed the builder's two-crew fixture using service A at `r.db`. Create `alias.db` as a symlink to `r.db` in the same temporary directory. Start Apply for WELD-1 and pause inside the suggester, after verifying the marker exists. Start service B at `alias.db` and verify that A's marker is gone. In one run B Applies TANK-ENTRY, then A resumes. Both report `applied=True`, and the registry lists both successors. In a separate run B approves the original WELD-1 interrupt, and `list_decided` reports it as cleared before A resumes and supersedes the run. No clock change was needed. These are two effects of the same ownership defect.

**Verification.** Ran the requested install, `pytest -q`, `python -m eval.run_eval`, and `python reviews/review-03-repro.py`. **465 passed, zero failures.** Eval matched the baseline. The builder's same-path probes stop with the expected “another reviewer service already has this database open” error. The suite covers same-service Apply and decision serialization, pending-review revalidation, and recovery after process exit. The separate temporary SQLite probes above exercised two paths to the same file. Hold for triage.

GPT-6 Astra independently reproduced both symlink outcomes at the same SHA using the real graph and temporary SQLite databases.

### Builder response to re-check 3

**Builder:** Claude Code (Opus). **Date:** 2026-11-07. The reviewer's text above is unchanged. Reproduced at the tested SHA `23b05e8`, including the rest of the class: a **symlink** and a **hard link** to the same database each started a second service (**reproduced**). A `sub/../r.db` spelling was refused, because its lock-file path resolves to the same file.

| ID | Verdict | Root cause | Fix |
|---|---|---|---|
| S08-01 / S08-02 | CONFIRMED | The exclusive lock was taken on a separate file named after the database's path (`<path>.lock`), so a different name for the same database got a different lock. | Take the exclusive `flock` on the **database file itself**. An `flock` belongs to the file (inode), not the name used to open it, so symlinks, hard links and any path spelling all hit the same lock. SQLite uses POSIX `fcntl` record locks, which are independent of `flock` on Linux, so they don't interfere. |

**Disputes:** none. **Known limit:** `flock` isn't reliable on some network filesystems. The reviewer is a local tool, and this is documented in reviewer/README.md.

### Re-check 3 fix

Commit `09a1636`. The exclusive service lock is keyed on the database file's identity (`st_dev` + `st_ino`), in a fixed directory under the system temp directory. Symlinks, hard links and any path spelling share it. The database file itself is never opened or closed for locking, because closing any handle to a file on Linux drops the process's SQLite POSIX locks on it.

Tests: `test_recheck3_any_other_name_for_the_same_database_is_refused` (symlink, hard link, dot-dot) and `test_recheck3_a_symlinked_service_cannot_disturb_a_live_apply`. Written first: 3 failed (the dot-dot case was already refused). Mutation, reverting to a path-named lock: 3 tests fail. Full suite **469 passed**; eval baseline unchanged.

### Reviewer re-check 4

Tested **`103488af71b4f82761ef3aa55f65dc0b2b571df5`**, the current `session-08-brief-apply` tip. Code inspection was limited to `git diff 23b05e8..HEAD -- reviewer tests`.

| ID | Verdict | Scenario |
|---|---|---|
| S08-01 | reopened | **Medium in the documented local setup. High impact, low likelihood. Reproduced.** Database aliases share one lock within a common temp directory. With different temp directories, a second process opens the identical database path, removes the live Apply marker during recovery, and creates a successor. The original Apply resumes and creates another. |
| S08-02 | reopened | **Medium in the documented local setup. High impact, low likelihood. Reproduced.** With the same separate temp directories, the second process can approve an old pending review while the first Apply is still active. The old approval reads as cleared before supersession. |

**Alias checks pass.** The named tests verify that symlinks, hard links and a `sub/../r.db` path spelling all get the same device and inode lock when the services share the lock directory. The live Apply symlink regression passes. A separate-process control with the same temp directory also refused startup while Apply was paused.

**Remaining gap** at `reviewer/graph_driver.py:41–55,98–102,241–253`. The device and inode match, but the lock directory comes from `tempfile.gettempdir()`. Two launches can resolve that directory differently, for example through different `TMPDIR` settings. Each acquires a distinct lock file. Startup recovery then assumes sole ownership and clears the other process's live marker.

```text
same database device + inode
       |
same temp directory?  yes -> same lock file -> second service refused
       |
       no -> two lock files -> second service starts -> live marker removed
```

**Reproduction.** Seed the real two-crew fixture in a temporary local SQLite database. Start Apply A for WELD-1 and pause it inside the real suggester after it records the marker. Launch a second Python process with the identical database pathname and a different `TMPDIR` from A's lock directory. It opens the service and confirms A's marker is gone. In one run it Applies TANK-ENTRY, then A resumes. Both calls succeed and the database contains two registered successors. In a separate run the second process approves the old WELD-1 interrupt and confirms it reads as cleared while A is still paused. A then successfully supersedes the old run. No symlink, hard link, or clock change is needed.

**Local likelihood.** Low in the documented setup with one reviewer process, one local database and a consistent temp environment. The bypass requires a second overlapping launch with a different effective temp directory, which can happen if a development shell and a service use different environments. The reproduced consequences are the same two unsafe state transitions as the earlier findings. A stable lock namespace shared by all launches that can reach the database is part of the ownership guarantee.

**Verification.** Ran `pip install -e ".[dev,retrieval,reviewer]"`, `pytest -q`, and `python -m eval.run_eval`. **469 passed, zero failures.** Eval matched the baseline. The additional interleavings ran against the real graph and temporary SQLite. Hold for triage.

GPT-6 Astra independently reproduced S08-01 using two subprocesses with distinct actual `TMPDIR` values and the identical absolute database path. It also assessed the bypass as medium severity for the documented local setup because it requires overlapping launches with different temp configuration.

### Builder response to re-check 4

**Builder:** Claude Code (Opus). **Date:** 2026-11-07. The reviewer's text above is unchanged. **CONFIRMED**, reproduced at `103488a` with two real processes. Process A held the database with `TMPDIR=T1`. Process B, started with `TMPDIR=T2`, opened the same database; with the same `TMPDIR` it was refused. The builder's first in-process probe wrongly reported "refused": it patched `tempfile.gettempdir` with a lambda that called `mkdtemp()`, which recursed, and `RecursionError` is a `RuntimeError`. It was discarded and replaced by the two-process run.

**Severity:** agree with medium in the documented local setup. The impact is high, but it needs overlapping launches with different temp configurations.

**Root cause:** the lock directory came from the environment (`tempfile.gettempdir()`), so a different environment meant a different lock.

**Proposed fix (Donnie to choose, given this is the fifth round):** put the lock file in the database's *real* directory (`realpath`), still keyed by device and inode. Nothing from the environment is used, so symlinks resolve to the same place. A hard link from a *different* directory would still differ. SQLite itself documents multiple names for one database file as unsafe (journal and WAL files are path-based), so that case would be documented as unsupported rather than chased.

### Re-check 4 fix (Donnie: option 1, fix and close the class)

Commit `a9c0672`. The service lock is a hidden file next to the database's **real** file (`realpath`), named by device and inode. Nothing comes from the environment. Test: `test_recheck4_two_processes_with_different_tmpdir_cannot_share_a_database` (two real processes; failed first). Mutation, putting the lock back under TMPDIR, makes it fail. A manual two-process run is refused. Full suite **470 passed**; eval baseline unchanged.

**Class closed as Known Debt (Donnie's decision, 2026-11-07):** further ways to give one database several identities to the OS (a hard link in another directory, network filesystems where `flock` is unreliable, bind mounts across namespaces) are documented in reviewer/README.md as unsupported, not chased. SQLite itself documents multiple names for one database file as unsafe. Defense in depth stays in place: a superseded run never reports cleared.

### Reviewer re-check 5

Pending, and narrow: a cheaper model runs the named test and the full suite, and confirms the diff only.
