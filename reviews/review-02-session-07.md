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
