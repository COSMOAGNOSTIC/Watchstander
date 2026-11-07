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

Pending. Per AGENTS.md "Review cost policy": cheaper model.
