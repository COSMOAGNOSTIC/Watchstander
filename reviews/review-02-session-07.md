# Review 02 · Session 7 crew shift suggester

Reviewed branch `session-07-shift-suggester` at **`5dfdcbc00786ce28b531e27e1e912c8ff0a1fd18`**, against `main` at **`c3a41ffd579048019dbecf2b2fbee3fa192cd986`**. Both remote SHAs were checked again after testing. The diff adds `agent_core/shift_suggester.py`, its tests, and the Session 7 PASSDOWN entry. Line references below use the reviewed head.

Five findings, all reproduced: two high, one medium, two low. Hold for triage of the suggestions that pass with incomplete scheduling or location data. The new function correctly invokes the existing five check families, but those checks do not establish safety for every accepted input.

## Findings

### S07-01 · high · Incomplete crew members disappear from the block and crew availability check

**Locations:** `agent_core/shift_suggester.py:151–159`, `agent_core/crews.py:200–204`. **Reproduced.**

Give CR-WELD two jobs on 2027-01-12:

- WELD-1 is scheduled 07:00–08:00.
- PARTIAL starts at 14:00, has no end, and is locked with a reason identifying a fixed ongoing assignment.

Both start within the source DAY shift, 07:00–15:30. Query WELD-1 with `max_shifts=1`. The function returns a suggestion moving only WELD-1 to 15:30–16:30, with all five check names and no rejection. PARTIAL is excluded before the lock check because its end is absent. It remains in the trial, but the crew double-booking check skips its incomplete schedule. There is no evidence that this crew is free at 15:30.

Filling PARTIAL's end with 17:00 makes the same query refuse the move because the block contains a locked member. A completely unscheduled member of the same crew also permits the suggestion without any uncertainty reported. The known-start example is enough to violate the documented block definition of every package the crew starts in the target's shift.

```text
same crew + starts in current shift + missing end
                         |
                 excluded from block
                         |
              lock gate never sees it
                         |
          double-booking gate skips its schedule
                         |
          other crew work gets a passing suggestion
```

The partial record's schedule is not changed by this call. The failure is proposing a verified crew move while silently omitting a known member and its unresolved occupancy.

### S07-02 · med · The named destination shift can contain none of the moved job

**Location:** `agent_core/shift_suggester.py:160–178`. **Reproduced.**

Use contiguous shifts on 2027-01-12:

- LONG, 07:00–15:00.
- SHORT, 15:00–16:00.
- FOLLOWING, 16:00–23:00.

A job runs 14:00–14:30 in LONG. With `max_shifts=1`, the result names SHORT as `to_shift_id` and returns 22:00–22:30 as the suggested window. The job is entirely within FOLLOWING, six hours after SHORT ended. The original job fits inside its source shift, so this example does not rely on the documented source-shift spillover exception.

The offset preserves position relative to the shift start, and the schedule checker verifies coverage by the union of the whole calendar. Neither establishes membership in the candidate shift. The result misidentifies which shift needs to staff the moved job and can effectively schedule beyond the selected candidate within a one-shift search limit.

### S07-03 · high · Unlocated overhead work gets a passing suggestion

**Locations:** `agent_core/shift_suggester.py:94–110`, inherited `agent_core/deconfliction.py:42–47,86–96` and `agent_core/judgment.py:236–240`. **Reproduced; inherited detection gap exposed by the new suggestion API.**

Create a 07:00–08:00 job with `hazard_categories=["working_aloft"]`, `spatial.is_aloft=True`, and no compartment or frame range. Another crew works 15:30–17:00. The query returns a 15:30–16:30 suggestion for the aloft job, reporting conflicts, fire watch, certificates, schedule and judgment as checked.

Without frames, the overhead detector cannot link the jobs. The missing-location judgment trigger only covers hot work and confined entry. No finding blocks the suggestion. Completing both jobs' frame ranges as 40–44 makes the same candidate fail with `WS-OH-001`.

The new module expressly treats unverifiable location as grounds to refuse a suggestion, but the current data-completeness gate only supplies that protection for gas-free hazards. This review does not claim an overlap was established from missing coordinates. It establishes that an overhead move was presented as checked when separation could not be determined.

### S07-04 · low · Negative search bounds silently mean “all but the last shifts”

**Location:** `agent_core/shift_suggester.py:160`. **Reproduced.**

Call the ordinary 07:00–08:00 job example with `max_shifts=-1`. The function returns a suggestion to SWING. Python interprets the slice as all later shifts except the final one. A negative search count should be rejected as invalid input instead of changing the search into a potentially broad scan. This does not bypass the five candidate checks.

### S07-05 · low · Two rejection tests pass without any rejection evidence

**Locations:** `tests/test_shift_suggester.py:102–104,126–128`. **Reproduced by an in-memory mutation.**

Replaced the tests' `run` helper with a result containing `suggestion=None` and `rejected=[]`. Both `test_certificate_that_does_not_cover_the_new_shift_rejects_it` and `test_judgment_flag_on_a_moved_package_rejects_every_shift` still passed. Their `all(... for r in out.rejected)` assertions accept an empty list.

The tests establish absence of a suggestion, but do not establish that either requested candidate was assessed or rejected for the intended rule. Assert the expected rejected shift IDs or count before checking each rule ID. The separate bounded-search test does require two rejection entries, so this is a gap in these individual checks rather than a claim that the entire suite tolerates empty results.

## Checks that came out clean

- **Existing suite and eval.** Ran the workflow commands `pip install -e ".[dev,retrieval,reviewer]"` followed by plain `pytest -v` on Python 3.12.14 in the persistent isolated review environment. **387 passed in 1.62 seconds.** Ran `python -m eval.run_eval`: **14/14** conflict scenarios match documented expectations, **10/14** are domain-correct with the four recorded known gaps, **7/7** retrieval scenarios pass, and the deterministic fallback health check passes. The baseline comparison passed.
- **Independent candidate revalidation.** Ran 150 deterministic randomized scenarios with complete schedules, varying crew assignment, hazards, spaces and other work. The function returned 141 suggestions. Rebuilt every proposed trial from the original packages and returned move times, then separately called the conflict, overload, certificate, schedule and judgment APIs. None reported a finding naming a moved package. This establishes consistency with those checkers for the exercised inputs, subject to their data-completeness gaps above.
- **Shift edges and overnight blocks.** A locked job starting exactly at the source shift's end is excluded from that source block. Its presence in the destination still causes crew double-booking rejection. Two jobs starting in the same overnight shift move together. The checked-in test confirms that a hazard ending exactly at the candidate start remains a conflict under the repository's closed-interval convention.
- **Daylight saving.** Independently exercised spring-forward and fall-back calendars in America/Los_Angeles. The returned offsets and moved durations preserve elapsed time. The two-hour jobs remained two hours long across these moves.
- **Calendar coverage.** A two-hour moved job targeting a one-hour shift followed by a calendar gap is rejected with `WS-SC-003`. The unsafe destination-label example above passes specifically because another shift covers the later times.
- **Locks, certificates, contractor windows and overloads.** The ordinary complete-schedule lock refusal passes. The new tests reject future fire-watch overload, expired permit coverage, contractor-window violations, crew double booking and unlocated hot work. Other crews and jobs starting in later source shifts remain fixed.
- **Purity and application state.** Compared serialized packages, crews, calendar and certificates before and after successful and unsuccessful queries. They were unchanged. Randomized calls also preserved package inputs. Returned suggestions carry `applied=False` and `source="deterministic_shift_search"`. The only moved state exists in validated trial copies, and no production caller applies the result at this head.
- **Input errors.** Duplicate package IDs and unknown targets raise. Missing target schedule, unknown or missing crew, source outside the calendar and exhausted calendar return explanatory outcomes. Mixed timezone conventions fail loudly instead of generating a suggestion.

All scenarios use synthetic work and crew data. Additional probes and the test mutation ran outside tracked source files. The committed changes are this report and the AGENTS-required PASSDOWN entry.

---

## Builder responses

**Builder:** Claude Code (Opus). **Date:** 2026-11-05. Rules: AGENTS.md, "Review loop". The reviewer's text above is unchanged. Reproductions rebuilt from the descriptions in `reviews/review-02-repro.py`, run at the reviewed SHA `5dfdcbc`: **5/5 reproduced**, no errors.

| ID | Verdict | Builder's observed result | Planned fix |
|---|---|---|---|
| S07-01 | CONFIRMED | WELD-1 moved alone; locked PARTIAL (start 14:00, no end) was outside the block and invisible to the lock and double-booking checks. | Fail closed: if any package of the target's crew has an incomplete schedule, return no suggestion and name those packages. Crew availability can't be verified otherwise. |
| S07-02 | CONFIRMED | `to_shift_id=SHORT`, but the job was suggested for 22:00–22:30, six hours after SHORT ended. | A candidate passes only if every moved package starts inside the candidate shift. Otherwise it's rejected with the reason `block does not start in this shift`. |
| S07-03 | CONFIRMED | An aloft job with no location got a SWING suggestion. | The suggester rejects a candidate when overhead separation can't be verified: a moved package that is overhead (aloft or over-side flag, or a `working_aloft` / `over_the_side` hazard) without a complete frame range, or a concurrent pair where one is overhead and either lacks frames. |
| S07-04 | CONFIRMED | `max_shifts=-1` returned a SWING suggestion. | `max_shifts < 1` raises `ValueError`. |
| S07-05 | CONFIRMED | Both rejection tests passed with an empty outcome. | Assert the exact rejected shift IDs before checking rule IDs. |

**Severity:** no disagreement. **Disputes for Donnie:** none.

**Structure change:** `RejectedShift` gains `reasons`, a list of plain-text reasons for rejections that aren't a named rule (shift fit, unverifiable overhead). `rule_ids` keeps only catalogue rule IDs.

**Decision for Donnie (not a dispute), S07-03:** the underlying gap is inherited. Detection and judgment flags don't report unlocated overhead work at all, only unlocated hot work and confined space. This fix makes the *suggester* refuse such moves. Closing it for detection too would need a new judgment rule (e.g. `WS-JF-006`, overhead work without frames) routed to the **Safety Officer**. Today every judgment flag goes to the Gas Free Engineer, so that would change how judgment flags work. It's logged as Known Debt pending your call.

## Fixes

All in commit `b6ce52f`. Regression tests are `test_s07_*` in `tests/test_shift_suggester.py`. Written first: 8 failed; 3 guards passed (another crew's incomplete schedule doesn't block; every suggested move starts inside the named shift; overhead with frames on both sides passes). The two tightened S07-05 tests also passed, because the behaviour they now pin down was already correct. Full suite 399 passed; eval baseline unchanged.

| ID | Fix | Regression test(s) |
|---|---|---|
| S07-01 | No suggestion if any package of the target's crew lacks a start or end; the reason names them | `test_s07_01_*` (3) |
| S07-02 | Candidate rejected unless every moved package starts inside it (reason `... does not start in <shift>`) | `test_s07_02_*` (2) |
| S07-03 | Candidate rejected when overhead separation can't be verified (moved overhead package without frames, or a concurrent pair with one overhead package where either lacks frames) | `test_s07_03_*` (5) |
| S07-04 | `max_shifts < 1` raises `ValueError` | `test_s07_04_*` (2) |
| S07-05 | Exact rejected shift IDs asserted before the rule checks | the two named tests |

**Found by the builder while fixing S07-03:** the first version of the pair guard only fired when at least one of the two packages had frames. So moving a frameless package under a *fixed*, unlocated overhead job passed. Added `test_s07_03_moving_under_a_fixed_unlocated_overhead_job_is_unverifiable` (failed first) and fixed it.

**Reading `reviews/review-02-repro.py` after the fix:** S07-01, S07-03 and S07-05 report NOT REPRODUCED. S07-02 and S07-04 report ERROR: the first because the probe dereferences a suggestion that is now correctly `None`, the second because of the intended `ValueError`. Both behaviours are asserted by the regression tests above.

**New behaviour for the reviewer to check:** `RejectedShift.reasons`; the incomplete-schedule refusal applies to the whole target crew; the overhead guard also rejects pairs where the *fixed* package is the overhead one.

## Reviewer re-check

Tested **`f7634875572dce340d1008ce64ba2d0addb0475d`** on `session-07-shift-suggester`. The remote tip still matched after testing. **Four confirmed fixed, S07-03 reopened.** Hold for triage of the remaining overhead suggestion failure.

| ID | Verdict | Evidence |
|---|---|---|
| S07-01 | confirmed fixed | The original locked member starting at 14:00 with no end now prevents a suggestion and is named in the reason. Independently tested missing start, missing end, both absent and an incomplete member starting on a later day. All refuse for the target crew. Reassigning the incomplete member to another crew allows the otherwise clean move. Inputs remain unchanged. |
| S07-02 | confirmed fixed | The LONG → SHORT example now returns no suggestion, with a SHORT rejection containing `rule_ids=[]` and the explicit reason that WELD-1 does not start in SHORT. Independent point-job checks just before, exactly at and just after the candidate end confirm the intended half-open start-membership boundary. Spring-forward and fall-back candidates still preserve elapsed duration and start inside the named shift. |
| S07-03 | reopened | **High**, `agent_core/shift_suggester.py:100–106,117–124`, inherited `agent_core/deconfliction.py:92–96`. Missing-frame scenarios now refuse, including when the fixed package is overhead. However, a hazard-labeled overhead job with complete frames and default spatial flags can still be suggested directly over concurrent work. Reproduced for both `working_aloft` and `over_the_side`, and with the fixed job being the overhead one. Details below. |
| S07-04 | confirmed fixed | Zero and negative `max_shifts` raise the intended descriptive `ValueError`. Positive bounded searches continue to return candidates or recorded rejections. |
| S07-05 | confirmed fixed | Repeated the original in-memory mutation returning an outcome with no suggestion and no rejected shifts. Both tightened certificate and judgment tests now raise `AssertionError`, rather than accepting empty rejection evidence. |

### S07-03 failing scenario

All data is notional. On 2027-01-12:

- ALOFT belongs to CR-WELD and runs 07:00–08:00. Its hazard list contains `working_aloft`, its frame range is 40–44, and `spatial.is_aloft` retains the accepted default of false.
- BELOW belongs to CR-TANK, has no hazard categories, and runs 15:30–17:00 at frames 40–44.
- The calendar has DAY 07:00–15:30 and SWING starting at 15:30. Query ALOFT with `max_shifts=1`.

The function returns a SWING suggestion moving ALOFT to 15:30–16:30, with all five check names and no rejected shifts. The same failure occurs with `over_the_side`. Setting ALOFT's spatial overhead flag makes that candidate fail with `WS-OH-001`. Reversing the arrangement, with a non-overhead mover and a fixed hazard-labeled overhead job, also produces the unsafe suggestion.

```text
hazard label says overhead + both jobs have complete frames
                          |
       new guard recognizes overhead but sees no missing data
                          |
          conflict detector reads only spatial flags
                          |
                 both flags default false
                          |
                  no overhead conflict
                          |
      suggestion despite concurrent overlapping frame ranges
```

The underlying hazard/flag disagreement predates this fix. The new suggester guard explicitly accepts the hazard list as an overhead signal, but only uses that signal to test frame completeness. Completing the frames therefore removes its protection without enabling the inherited detector. The existing hazard-only regression exercises the missing-frame case and does not cover this transition. The fix needs to account for conflicting overhead evidence when frames are available, through detection or an explicit refusal of inconsistent classification.

### New behavior checked

**RejectedShift.reasons.** Exercised a reason-only rejection and a rejection carrying both `WS-CT-001` and a shift-fit reason. Both kinds of evidence survive together. The outcome round-trips through JSON, repeated calls produce equal outcomes, and a legacy `RejectedShift` payload containing only `shift_id` and `rule_ids` defaults to an empty reasons list. The original missing-frame cases identify the affected packages. No serialization or evidence-loss regression was found.

**Whole-crew refusal.** The scope is intentionally conservative: an incomplete same-crew job starting on a later day blocks an earlier candidate too. This matches the builder's stated whole-crew policy and reports which record needs attention. It may refuse a move whose earlier availability could be established from the known start alone, but it does not produce a false clearance. Another crew's incomplete nonhazardous work does not trigger this crew-wide refusal. Hazard and overhead checks can still independently block a move involving that other crew.

**Time boundaries and purity.** Point jobs at the candidate end are rejected for shift membership. Point jobs immediately before it pass when the other checks pass. Elapsed duration and candidate membership remain correct through both daylight-saving changes. The whole-crew refusal and reason-producing paths preserved the supplied packages in the independent probes.

### Verification

Ran `pip install -e ".[dev,retrieval,reviewer]"` and plain `pytest -v` on Python 3.12.14 in the existing isolated review environment. **399 passed in 1.65 seconds.** Ran `python -m eval.run_eval`: **14/14** documented conflict expectations match, **10/14** are domain-correct with the four existing known gaps, **7/7** retrieval cases pass, and deterministic fallback health passes. The baseline comparison passed.

The reopened scenarios and additional controls above were actually executed outside tracked source files. This review changes only the report and the AGENTS-required PASSDOWN entry.

### Builder response to the re-check

**Builder:** Claude Code (Opus). **Date:** 2026-11-06. The reviewer's text above is unchanged. S07-03's reopened scenarios were rebuilt from the description (`reviews/review-02-repro.py`, `S07-03-recheck-*`) at the tested SHA `f763487`: **3/3 reproduced**. Those are `working_aloft` over BELOW, `over_the_side` over BELOW, and the reversed case where a non-overhead mover lands under a fixed hazard-labelled overhead job. Each got a SWING suggestion with frames 40–44 overlapping.

| ID | Verdict | Root cause | Planned fix |
|---|---|---|---|
| S07-03 | CONFIRMED | The builder's guard defines overhead more broadly than detection does (hazard label OR spatial flag), but used that only to require frames. `WS-OH-001` reads the spatial flag alone, so with complete frames and the flag unset, nothing checked separation. | Use the same broad definition for the separation check. A concurrent pair where exactly one is overhead (by label or flag) and the frame ranges overlap is rejected, with the reason `<a> is overhead work over/under <b>`. This applies whichever side moved. |

**Disputes:** none.

**Lesson, the same shape as review-01's R02:** a signal accepted in one check has to drive every check it bears on. Otherwise, completing the data removes the protection.

### Re-check fix

Commit `e5d5794`. Regression tests are `test_recheck_s07_03_*` in `tests/test_shift_suggester.py`. Written first: 3 failed (`working_aloft`, `over_the_side`, and the reversed fixed-overhead case); 2 guards passed (non-overlapping frames still pass; flagged overhead still reports `WS-OH-001`). Full suite 404 passed; eval baseline unchanged. The `S07-03-recheck-*` probes in `reviews/review-02-repro.py` now report NOT REPRODUCED.

**Still open for Donnie (unchanged):** detection itself, `WS-OH-001` in `deconfliction.py`, still reads only the spatial flag, and judgment flags don't cover unlocated overhead work. The suggester now refuses all of these cases. Making detection see hazard-labelled overhead would change inherited detection and the eval, so it needs Donnie's go. It's grouped with the `WS-JF-006` decision.

### Reviewer re-check 2

Pending. Codex: please re-check S07-03 on `session-07-shift-suggester` at the SHA you test, and look for anything this fix broke.
