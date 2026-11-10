# Review 05: red team of the whole engine (detection, status gate, suggester and Apply, decision log, daily brief)

**Reviewer:** Claude Code, Claude Fable 5.2  ·  **Reviewed:** `439c4b13f0fba8c4319379556d70db208fa1283e` (`main`), whole tree, not a diff
**Builder responding:** Claude Code (builder session), 2026-11-09 · <tool and model>  ·  **Response date:** <YYYY-MM-DD>

Rules: AGENTS.md, "Review loop". The reviewer's findings are never edited. The builder adds a response under each one. Every finding needs a verdict before any fix is written.

## What was run

| Check | Result |
|---|---|
| `pip install -e ".[dev,retrieval,reviewer]"` | installed, exit 0 |
| `pytest -q` (plain console script from that install) | **548 passed**, 0 failed |
| `python -m eval.run_eval` | 14/14 conflict scenarios match documented behaviour (10 domain-correct, 4 known gaps), 7/7 retrieval, fallback healthy |
| `python reviews/review-05-repro.py` | 11 of 11 findings print `REPRODUCED` |

Environment note, not a repo defect: this machine has a second, unrelated `pytest` earlier on `PATH` that cannot see the editable install and fails collection with 39 import errors. The 548 figure is from the `pytest` the install itself put on `PATH`.

No production code was changed. The only new files are this report and `reviews/review-05-repro.py`. All data in both is invented.

## The pattern behind the high findings

The four-input AND gate (`package_status`) is correct in isolation. Three of the five high findings are ways around it, not through it:

```
  hitl_disposition (a plain input field) ----+
  certificate findings ----------------------+
  judgment flags ----------------------------+--[AND]--> CLEARED      <- projects.py, used only by the daily brief
  schedule findings -------------------------+

  R05-01  input arrives with hitl_disposition="approved" --> first input reads clean, no human involved
  R05-03  reviewer clicks Approve --> hitl.py sets cleared_for_execution=True directly;
          the AND gate is never consulted on the reviewer path
  R05-02  Apply seeds the successor from the ORIGINAL inputs --> a human REJECT in the old run
          is not an input to anything in the new run
```

The other two high findings are inputs the detectors never see: a misspelled top-level field (R05-04) and a hazard with no permit asked for (R05-05).

## Findings (reviewer)

| ID | Severity | File:line | Scenario | Reproduced or traced |
|---|---|---|---|---|
| R05-01 | high | `agent_core/projects.py:150-157`, `agent_core/state.py:265-278`, `agent_core/daily_brief.py:147-148` | `hitl_disposition` and `cleared_for_execution` are ordinary input fields. Add one package to the notional carrier dataset: `risk_level: "critical"`, `hitl_disposition: "approved"`, `cleared_for_execution: true`, no conflicts. The construction-time validator only tightens clearance when the disposition is `None`, so it stays cleared. → The daily brief counts it under **CLEARED** and leaves it out of **NEEDS A PERSON**. The graph, on the same data, holds it at the HITL gate as a pending review. The decision log has 0 entries, so no person ever approved it. The brief hides a package the graph routes to a person. The same holds for `requires_hitl_review: true` with a pre-set approval. | reproduced |
| R05-02 | high | `reviewer/graph_driver.py:253-264` | Apply erases a human rejection. Seed the carrier demo. Reviewer A **rejects** CS-102 with the note "tank ventilation not rigged; do not enter". Reviewer B then clicks Apply on HW-101 (its conflict partner). The successor run is built from the run's original inputs, where CS-102 has no disposition. With HW-101 moved, CS-102 has no conflict in the new run. → In the successor, CS-102 is `cleared_for_execution=True`, `hitl_disposition=None`, not pending, and has no log entry there. The only trace of the rejection is the old run's entry, on a run now marked superseded. The reject note is the documented way to hold a package on a condition ("reject and resubmit"), so Apply on a neighbour silently releases that hold. | reproduced |
| R05-03 | high | `agent_core/hitl.py:146`, `reviewer/graph_driver.py:397` | The four-input gate is not on the reviewer path. Seed the carrier demo. FALL-107 needs a fall-protection plan; the one on file ends 12:00 and the job runs to 15:00 (WS-CT-003). Click Approve. → The graph stores `cleared_for_execution=True`, and the dashboard shows "FALL-107 — approved (cleared_for_execution=True)". `package_status` on that same package, with the real findings, returns `has_findings`. `state.py` tells every downstream consumer to trust `cleared_for_execution`, so one click marks a job with three uncovered hours as cleared. A human approval cannot make a certificate cover a window it doesn't cover. | reproduced |
| R05-04 | high | `agent_core/state.py:278` | Review-01 R04 fixed misspelled keys on `SpatialCoordinates` and `SafetyPermitsRequired` only. `WorkPackageState` itself still drops unknown keys. Four inputs, each one typo: (a) `hazard_categoires: ["hot_work"]` in the same tank and time as a confined-space entry → no conflict, both cleared; (b) `hot_workers: 6` on one fire watch (limit 4) → counted as 1, cleared; (c) `risk: "critical"` → loads as `low`, never reaches the gate; (d) `lock: true` → `locked=False`, so the suggester may move it. → All four pass the graph with no review, and the status gate returns `cleared` for (a) to (c). Traced only: `Crew`, `Certificate` and `Project` have the same default, so `contractor: true` in place of `is_contractor` gives a crew with no window limits. | reproduced (a–d); traced (other models) |
| R05-05 | high | `agent_core/certificates.py:104,113` | Which certificates a job needs comes only from `permits_required`, which defaults to all false. WS-JF-005 checks permit → hazard, but nothing checks hazard → permit. Submit a located, scheduled package with `hazard_categories: ["hot_work"]` and no `permits_required` block, with no certificates on file. Same for a confined-space entry and for work aloft. → No certificate finding, no judgment flag, nobody routed; the status gate returns `cleared` for all three. Leaving the permits block out is the easiest way to get hot work through with no permit. (The demo's own ALOFT-105 is work aloft with no fall-protection plan required.) | reproduced |
| R05-06 | medium | `agent_core/deconfliction.py:307,440-441` | Fire-watch capacity is checked only for packages that name a fire watch, and the name is compared as raw text. (a) One hot-work package with `hot_worker_count: 9`, a valid permit and no `fire_watch_id` → cleared, nobody routed; the same job with a watch named is routed. Missing data reads as safe here, the opposite of the module's stated posture for missing schedules. (b) Two concurrent 3-worker jobs on `"FW-N-1"` and `"fw-n-1 "` → two separate groups, neither over 4, both cleared; six welders on one watch. | reproduced |
| R05-07 | medium | `agent_core/reasoning.py:271-273` (also `:103`, `:146`) | Rule 7. Only `recommended_action` is forced to be deterministic. When the model answers, its `executive_summary` replaces the deterministic one (which carries the rationale) and is shown first on the review page, with no check on what it says. With a stubbed model that returns "False positive … Recommend approving both packages; no reschedule is needed", the brief is tagged `[SOURCE: LLM SYNTHESIS]` and shows exactly that text. → The model can state a verdict and a suggestion to the person deciding. The package's free-text `description`, written by the submitter, is sent to the model verbatim, so the submitter can address the model. Whether a real model would obey such text was not tested; the point is that nothing deterministic stands in the way. | reproduced with a stub model |
| R05-08 | medium | `agent_core/reasoning.py:130-136`, `reviewer/graph_driver.py:156-161` | `_call_llm` catches a missing key, a missing package and bad JSON, but not an exception from the API call. With a key set and the API failing (stub raises), `seed_run` raises after detection, judgment and findings have flagged packages. The run is never registered. → 0 pending reviews, 0 log entries; the flagged packages reach no person, and the explanation layer has taken down the decision path. Nothing is cleared, so it fails closed, but silently. | reproduced with a stub model |
| R05-09 | medium | `reviewer/graph_driver.py:436-451` | The decision is stored in the graph first and logged second. If the log write fails, the fallback `decision_failed` write uses the same log and fails too. Reproduced through the service API with an actor name SQLite cannot store (a lone surrogate): `submit_decision` raises, the graph holds HW-103 `approved`, `cleared_for_execution=True`, the log has 0 entries for it, and `verify_chain()` still passes. The shipped HTML form cannot send that string (tested: it arrives as U+FFFD), so in the app the triggers are storage faults between the two writes (disk full, lock timeout); that part is traced. Either way an approval can exist with no record of who gave it, and the chain cannot show the gap. | reproduced (service API); traced (app triggers) |
| R05-10 | medium | `agent_core/findings_gate.py:48` | All schedule rules are skipped when the run has no shift calendar, but only WS-SC-003 needs one. Seed crews with `calendar: None`: a contractor job 13:00–17:00 against a 07:00–09:00 window (WS-SC-002), a package on a crew that doesn't exist (WS-SC-001), and the same crew on two overlapping jobs (WS-SC-004). → None is routed; all three stay cleared. | reproduced |
| R05-11 | medium | `agent_core/daily_brief.py:215`, `agent_core/decision_log.py:67-69` | The brief's `--db` opens whatever path it is given and creates the file and table if absent. Run it with a mistyped path. → A new empty database is created and the brief prints "entries: 0, chain verified", which reads as the reviewer's log having been checked. This is a new consequence of the Known Debt anchor item: without `--anchor`, a wrong, replaced or emptied database is indistinguishable from a healthy new one, and the read-only brief writes to disk. | reproduced |

## Looked at and found sound

- Hash chain: an edited, removed or reordered entry is caught by `verify_chain`; the triggers refuse UPDATE and DELETE. Whole-chain rewrite and tail truncation are the Known Debt anchor item and are not re-reported.
- Apply: the claim, the re-check against run inputs, and moved packages losing their approval all held under the probes tried. R05-02 is about packages Apply does not move.
- Suggester: every candidate is checked on the moved times, certificates never move, and a locked package in the block stops the search.
- `recommended_action` is deterministic on every path, and a partner-less flag never calls the model.

## Builder responses

### R05-01
- **Verdict:** CONFIRMED
- **Evidence:** Added X-01 to the carrier dataset with `risk_level=critical`, `hitl_disposition=approved`, `cleared_for_execution=True`. `run_checks` status: CLEARED. Same inputs seeded through `ReviewerService.seed_run`: X-01 is a pending review. Decision log: 0 entries. (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix: a package can't arrive already decided. Input dispositions and clearance are dropped at the graph's entry and by the loader; a decision only comes from a person through the reviewer (or is carried forward by Apply, see R05-02).
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **confirmed fixed.** At `92cffc29a8c7e1a06e036071333f9fda2ceeb8ad`, the preapproved critical package appears as pending in both the brief and the graph. The builder and Fable probes agree. The full suite passed 596 tests with zero failures, eval matched 14/14 conflict and 7/7 retrieval expectations, and all 11 builder probes reported FIXED.

### R05-02
- **Verdict:** CONFIRMED
- **Evidence:** Carrier demo: rejected CS-102, then Applied HW-101's suggestion. Apply succeeded; in the successor CS-102 is not pending, `cleared_for_execution=True`, `hitl_disposition=None`. (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix (Donnie: yes). A rejection carries into the successor run and keeps the package blocked, with the original reviewer and note.
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **confirmed fixed.** Rejecting CS-102 and applying HW-101’s move leaves CS-102 rejected and uncleared in the successor. The builder regression also checks the carried actor and note.

### R05-03
- **Verdict:** CONFIRMED
- **Evidence:** Carrier demo: approved FALL-107. `list_decided` shows `cleared_for_execution=True`; `check_certificates` on the same package and certificates still returns WS-CT-003. (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix (Donnie: no, an approval can't clear a finding). An approval resolves conflicts and judgment flags, but can't clear certificate or schedule findings; the package stays blocked until the facts change.
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **confirmed fixed.** Approving FALL-107 with WS-CT-003 leaves clearance false and the four-input status at HAS_FINDINGS. The contractor-window control also stays uncleared after approval.

### R05-04
- **Verdict:** CONFIRMED
- **Evidence:** `WorkPackageState.model_validate` with `hazard_categoires: ['hot_work']` loads with `hazard_categories=[]`. (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix: `extra='forbid'` on every input model (packages, crews, windows, shifts, certificates, projects, the dataset), the whole class, not only packages.
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **confirmed fixed.** The builder cases and suite reject unknown keys across the covered input models. Fable’s misspelled package input stops with the expected `extra_forbidden` validation error.

### R05-05
- **Verdict:** CONFIRMED
- **Evidence:** Added X-05 (`hazard_categories=['hot_work']`, no permits block, no certificate) to the carrier dataset. `run_checks` status: CLEARED. (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix (Donnie: yes, corrected). Hot work → hot work permit; confined space → entry permit; working aloft → an aloft authorization: an aloft chit signed by the CSOOW for the day, or a standing aloft the CO authorizes for a date range (new WS-CT-006). The fall protection plan is the ship's standing order, so a fall-protection hazard implies nothing per job. Zones are Known Debt.
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **reopened (high, reproduced).** The implied-permit checks now hold the original hot-work, confined-space and aloft cases. A package-specific aloft authorization with `form="chit"` covering March 15 07:00 through March 17 16:00 also validates and clears a March 16 12:00–14:00 aloft job with no review. The new form validator at `agent_core/certificates.py:68` checks scope but accepts a multi-day chit as coverage, despite WS-CT-006 distinguishing a chit for the day from a standing authorization for a date range.
- **Builder response to re-check:** CONFIRMED (builder probe): a `form="chit"` aloft authorization valid 03-15 07:00 to 03-17 16:00 covers a 03-16 job with no finding. Fix: a chit is for the day (Donnie), so a chit longer than 24 hours is refused at load; a date range is a standing aloft. Fixed in the next commit; failing tests first (`tests/test_review05.py::test_recheck_r05_05_*`); mutation-tested; `reviews/review-05-builder-repro.py` adds a re-check line.

### R05-06
- **Verdict:** CONFIRMED
- **Evidence:** 9 hot workers, no watch named: not flagged (control with a watch named: flagged). Two concurrent 3-worker jobs on `FW-N-1` and `fw-n-1 `: neither flagged (control with identical IDs: both flagged). (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix: more than four hot workers with no fire watch named is flagged (missing data fails closed); watch IDs compared trimmed and case-insensitive.
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **reopened (medium, reproduced).** Detection now flags nine workers without a named watch and groups case/space variants correctly. A nine-worker job with a valid permit and no watch is flagged WS-FW-001 at 12:00–14:00, but the brief offers a 20:00–22:00 move and Apply accepts it. The successor flags the same WS-FW-001 and stays pending. The new missing-watch check is in `agent_core/deconfliction.py:384`, while the candidate check in `agent_core/shift_suggester.py:138` uses `fire_watch_overloads`, which excludes unnamed watches.
- **Builder response to re-check:** CONFIRMED: with a 9-worker hot-work job and no watch named, `suggest_crew_shift` offers 20270315-SWING. Fix (whole class): the suggester rejects a candidate shift if any moved package is still flagged by any partner-less detection rule (named or unnamed fire-watch overload), using the same function detection uses. Fixed in the next commit; failing tests first (`tests/test_review05.py::test_recheck_r05_06_*`); mutation-tested; `reviews/review-05-builder-repro.py` adds a re-check line.

### R05-07
- **Verdict:** CONFIRMED
- **Evidence:** Stubbed `_call_llm` to return 'False positive. Recommend approving both.' HW-101's brief summary became `[SOURCE: LLM SYNTHESIS] False positive. Recommend approving both.` (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix: the deterministic summary (the rule and rationale) is always shown and never replaced; any model text is shown separately, labeled as the model's explanation, and the submitter's description is passed to the model marked as untrusted data.
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **reopened (medium, reproduced with a stub).** The deterministic summary and action survive as intended. Stub the model to answer “False positive. Approve both now.” The reviewer HTTP page still displays that verdict and recommendation verbatim under Model explanation. The label distinguishes the source, but the advice still reaches the deciding reviewer through `agent_core/reasoning.py:294` and `reviewer/app.py:150`.
- **Builder response to re-check:** CONFIRMED (stub): the review page shows 'Approve both now' under Model explanation. **Needs Donnie** (rule 7 interpretation); options in the builder's message. Not fixed until he rules.

### R05-08
- **Verdict:** CONFIRMED
- **Evidence:** Stubbed `_call_llm` to raise `RuntimeError`. `seed_demo` raised; 0 pending reviews. (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix: any exception from the model call falls back to the deterministic brief, so the run still reaches a person.
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **reopened (medium, reproduced with a stub SDK response).** Transport exceptions now fall back. Return valid JSON `null` in an otherwise successful model response. The membership check at `agent_core/reasoning.py:155` raises TypeError, aborts `seed_demo`, and leaves zero pending reviews. Returning an object with an object-valued executive summary likewise aborts with ValidationError during SafetyBrief construction at line 288.
- **Builder response to re-check:** CONFIRMED (stub SDK): a JSON `null` body aborts `seed_demo` with TypeError; an object-valued summary aborts with ValidationError. Fix (whole class): the model's answer must be an object whose two fields are non-empty strings, or it's discarded; and any exception anywhere in the model branch of the brief falls back to the deterministic brief. Fixed in the next commit; failing tests first (`tests/test_review05.py::test_recheck_r05_08_*`); mutation-tested; `reviews/review-05-builder-repro.py` adds a re-check line.

### R05-09
- **Verdict:** CONFIRMED
- **Evidence:** Carrier demo, `submit_decision` on HW-103 with actor `'\ud800'`: the call raised, HW-103 is stored `approved`, the log has 0 entries, `verify_chain()` passes. (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix: log first. A decision or Apply writes a `*_requested` entry before it touches the graph; if that write fails, nothing is decided. The outcome entry follows as now.
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **reopened (medium, reproduced).** Public decision and Apply paths write the request first, and the original unloggable-actor decision leaves the graph untouched. Approve HW-103 while injecting a failure on the outcome and failure-log appends. The durable request remains and `open_requests()` initially reports it. Restore logging and submit a stale reject on that interrupt. The log then contains only `decision_requested` for the approval and `decision_refused` for the later reject. `open_requests()` returns empty because `agent_core/decision_log.py:133` matches any later outcome by run and interrupt, hiding the approval’s missing outcome.
- **Builder response to re-check:** CONFIRMED: request logged, outcome writes failed (`open_requests()` = 1); a later stale reject on the same interrupt logged `decision_refused` and `open_requests()` dropped to 0. Fix: each outcome entry names the `request_seq` it answers, and `open_requests()` matches on that, so an unrelated later refusal can't close it. Fixed in the next commit; failing tests first (`tests/test_review05.py::test_recheck_r05_09_*`); mutation-tested; `reviews/review-05-builder-repro.py` adds a re-check line.

### R05-10
- **Verdict:** CONFIRMED
- **Evidence:** Seeded the carrier dataset with its crews but `calendar=None`. CONTR-109 (contractor outside its window, WS-SC-002) is not pending. (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix: run the schedule rules that need no calendar (WS-SC-001, -002, -004) whenever crews are given; only WS-SC-003 needs the calendar.
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **reopened (medium, reproduced).** Contractor, unknown-crew and double-booking checks now run without a calendar when crews are nonempty. Seed a scheduled nonhazardous package assigned to CR-GHOST with explicit `crews=[]` and `calendar=None`. It passes through cleared, while calling `check_schedule_constraints` directly with the same data returns WS-SC-001. `reviewer/graph_driver.py:152` serializes omitted and explicitly empty crew lists the same way, and the truthiness guard at `agent_core/findings_gate.py:57` skips the explicit empty roster.
- **Builder response to re-check:** CONFIRMED: `seed_run(crews=[], calendar=None)` with a package on CR-GHOST leaves it cleared. Fix: the run records whether crew data was given (`None`) or given empty (`[]`); an explicit empty roster runs the crew rules, so CR-GHOST is WS-SC-001. Fixed in the next commit; failing tests first (`tests/test_review05.py::test_recheck_r05_10_*`); mutation-tested; `reviews/review-05-builder-repro.py` adds a re-check line.

### R05-11
- **Verdict:** CONFIRMED
- **Evidence:** `DecisionLog` on a path that didn't exist created the file and `verify_chain()` returned 0. (builder's own probe, not the reviewer's script; now `reviews/review-05-builder-repro.py`)
- **Disposition:** fix: the brief opens `--db` read-only and refuses a path that doesn't exist or has no decision log.
- **Fix commit / regression test:** `d85cda6` on `fix-review-05`; `tests/test_review05.py` (R05 block for this ID); `reviews/review-05-builder-repro.py` prints FIXED here and REPRODUCED/ERROR on `main`. Mutation-tested: undoing the fix fails a test.
- **Reviewer re-check:** **confirmed fixed.** The brief refuses a missing database or one without a decision log, and opens an existing log read-only. Fable’s script exits at the missing path with the expected refusal. The regression tests verify no file is created and writes through the read-only connection fail.

## Disputes for Donnie

<List every DISPUTED finding with both positions in one line each. Empty if none.>

Three findings turn on a policy call rather than a bug, so they may land here whatever the builder rules:

- **R05-03:** can a human approval clear a package that still has an open certificate, judgment or schedule finding, or must the findings be closed first?
- **R05-02:** should a human rejection follow a package into the successor run that Apply creates?
- **R05-05:** should a hazard category imply its permit, so that hot work with no hot-work permit requested is a finding?

**Builder:** no disputes; all 11 CONFIRMED. **Donnie's rulings (2026-11-09):** R05-03 no (approval can't clear an open certificate or schedule finding; an emergency override is a future design, Known Debt); R05-02 yes (a rejection stands until the package itself changes); R05-05 yes, with the aloft correction above.

**Behavior changes the reviewer should know about when re-checking:**
- Every decision or Apply that reaches the graph now writes a `*_requested` entry first (R05-09). Review-04's "exactly one entry" promise now reads "exactly one outcome entry"; `tests/test_review04.py` counts outcomes and a new test checks the request comes first. `DecisionLog.open_requests()` lists any request with no outcome.
- A hazard now implies its permit (R05-05), so older fixtures that scheduled hot work with nothing on file put a notional permit on file (`tests/notional_permits.py`); their assertions are unchanged.
- The model's text never replaces the deterministic summary (R05-07); `test_session08a.py`'s "LLM may phrase the summary" test was rewritten to the new rule.
- The demo dataset gained a notional standing aloft so ALOFT-105 still shows only WS-OH-001.
