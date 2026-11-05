# Watchstander review 01 · Sessions 2–5

Reviewed `aa3a4b5353549947124e15b72c9b5f9ced43e9d3..12d3873496ca6ca1d69148755e82428d08bb250b`. The latter SHA was the tip of `session-05-judgment`. Line references below are to that SHA. Only this report was added. Reproductions used synthetic inputs and public functions unless an internal helper or test is explicitly named.

## Findings

| ID | Severity | File and line | Concrete scenario and observed result |
|---|---|---|---|
| R01 | high | `agent_core/projects.py:93–100` | **Reproduced.** Create a scheduled package, then set `requires_hitl_review=True` on the live model. With no disposition, `package_status` still returns `CLEARED`. The construction-time validator tightened the clearance bit only at creation. The rollup consults the more recent review requirement only if that bit is already false. |
| R02 | high | `agent_core/projects.py:98–100,125` | **Reproduced, documented integration gap.** A scheduled, unlocated hot-work package requiring a hot-work permit returned `MISSING` from the certificate checker and `WS-JF-003` from judgment. The same object returned `CLEARED` from the status API. A one-member rollup uses that status as its overall result. The checks intentionally report separately, so the current label cannot establish readiness for execution. PASSDOWN defers graph/reviewer integration. |
| R03 | high | `agent_core/certificates.py:87–90` | **Reproduced.** Use Python datetimes with the same `ZoneInfo("America/Los_Angeles")`. Issue a permit for 01:15–01:45 PDT on 2026-11-01 and schedule the job at 01:15–01:45 PST (`fold=1`) that day. The permit ended 30 minutes before the job began. The checker returned zero findings because comparisons with the same zone object used wall-clock time. Compare instants for ordering and coverage. |
| R04 | high | `agent_core/certificates.py:123–125`, `agent_core/state.py:128–133` | **Reproduced.** Supply a scheduled package with `permits_required={"hot_work_permti": true}` and no certificates. The nested model discards the unknown key and defaults every known permit flag to false. The checker returns an empty list. The enum correctly rejects an unknown kind on a certificate record, which exercises a different input path. |
| R05 | high | `agent_core/certificates.py:52–55,126–128` | **Reproduced.** An imported job and an unrelated permit both carry the empty string as their package ID. A full-window permit of the required kind satisfies the job by empty-string equality. An empty certificate ID also passes validation. Reject blank identifiers before joining records. |
| R06 | high | `agent_core/judgment.py:163–169`, `agent_core/deconfliction.py:125–126` | **Reproduced.** Two simultaneous records, one hot work and one confined entry in the same tank, share ID A. The conflict lookup returned `None` and the judgment scan returned `[]`. Both paths skip equal IDs as a self-comparison. The project rollup already rejects duplicate records, but these APIs accept the batch independently. The detector skip predates the refactor. |
| R07 | high | `agent_core/judgment.py:122–132,175–187` | **Reproduced.** The welder is located by tank ID only and the concurrent confined entry by frames 1–3 only. Even if the tank is at frame 2, there is no common coordinate for this pair. Both packages count as located, detection returned `None`, and judgment returned `[]`. A separate single-package probe with a whitespace-only compartment and no frames also suppressed the missing-location flag. |
| R08 | high | `agent_core/judgment.py:118–119,186–190` | **Reproduced.** A tank-entry record sets `spatial.is_enclosed_or_confined=True` and requires a confined-space entry permit, but omits the optional hazard list and has no location. The accepted record generated no judgment flag. The only trigger input is the hazard list. Surface inconsistent or missing hazard classification when the data already identifies an entry. |
| R09 | high | `agent_core/deconfliction.py:277–282` | **Reproduced, inherited.** Assign five simultaneous hot workers in one package to one fire watch. The peak exceeds the configured limit of four, but the one-member group has no package pairs. `find_all_conflicts` returned a package with empty conflicts and its scheduled status was `CLEARED`. The named capacity rule exists at this head, but no finding reaches the caller. |
| R10 | med | `agent_core/deconfliction.py:141–149` | **Reproduced.** Hot work marked aloft and confined work below share frames 10–12. Both the hazard-pair and overhead predicates apply. `conflict_rule_ids` returned only `WS-HZ-001`, omitting `WS-OH-001` and its Safety Officer contact. The old first-match rationale is preserved, but the new list of rule IDs is incomplete. The pair is still blocked. |
| R11 | med | `agent_core/judgment.py:59–70,139–149` | **Reproduced.** A primary Gas Free Engineer with empty person ID and display name passed roster validation. An unlocated hot-work job routed successfully with the message ending “Gas Free Engineer  ().” There is no identifiable recipient. |
| R12 | med | `agent_core/judgment.py:139–143` | **Reproduced.** Pairs `["A+B","C"]` and `["A","B+C"]` are simultaneous confined entries in two different tanks. Both flags received `WS-JF-002:A+B+C`. A reviewer or acknowledgement store keyed by flag ID would merge two independent decisions. The returned list itself retained both. |
| R13 | med | `agent_core/certificates.py:90` | **Reproduced.** A locally entered naive 07:00–08:00 job and an imported UTC-aware permit both validate separately. Checking coverage raises `TypeError` when comparing bounds. The caller gets no assessment. Define a common timezone contract at intake, including for project due dates compared with schedules. |
| R14 | low | `agent_core/certificates.py:79–80,146–151` | **Reproduced.** Renew at 07:00:30 after expiry at 07:00:10. The checker catches the gap, but the human-facing finding says “07:00 to 07:00”. The structured bounds preserve seconds. The gap tuple also carries only boundary times, so a consumer needs to know that the adjacent permits cover both endpoints of an interior gap. |
| R15 | low | `tests/test_named_rules.py:236` | **Reproduced by mutation in memory.** Replaced the common detector with a function always returning `None`. The entire “agree … on every case” test still passed, including the known-conflict cases. It checks two wrappers against each other. Other tests do assert particular positive IDs. Give each case an independent expected outcome. |
| R16 | low | `tests/test_named_rules.py:67` | **Reproduced by mutation in memory.** Replaced a contact role in the loaded test catalogue with the notional personal name “Riley Example”. The “roles not named people” test passed because it rejects only digits and the at-sign. An expected role set would test the stated property. |
| R17 | med | `agent_core/judgment.py:159–165` | **Reproduced with an in-memory catalogue addition.** Added a well-formed fourth judgment ID with the same valid contact and applicability as JF-003. The roster preflight accepted it, but an unlocated package still emitted only JF-003. The new ID can enter the catalogue with no implemented trigger. Check the catalogue judgment IDs against the implemented trigger IDs in both directions. |

## Checks that came out clean

- Checked 660 small schedule/certificate combinations against an independent coverage oracle that sampled all endpoints and all intervening half-steps. These covered zero, one and two certificates, nested and disjoint intervals, touching renewals, uncovered edges, point certificates and point jobs. For comparable naive datetimes the gap/no-gap decision matched in every case.
- Checked 100 ordered schedule/frame interval pairs, including point jobs and shared endpoints. Temporal overlap, spatial overlap and nearest-frame distance matched independent integer-set calculations. The judgment threshold includes a gap of three and excludes four. The checked-in tests also cover scheduling uncertainty, due-date equality, and project membership errors.
- The current certificate kinds exactly match the permit flags. Unknown explicit certificate kinds and hazard enum values raise validation errors. Wrong-package and wrong-kind records fail to cover a required permit. An incomplete schedule with a required permit yields an unscheduled finding. Duplicate certificate IDs raise.
- The current named-rule catalogue covers every configured incompatible hazard pair and certificate kind. The supplied roster has identifiable notional primaries for the judgment contacts. The project tests exercise missing members, duplicate IDs, empty projects, rejected dispositions and worst-member aggregation.
- **Citation provenance.** All five true flags reference four IDs recorded individually as verified in the PSNS 2014 source ledger: NAVSEA8010-4.2, 4.3, 4.4.3 and 4.4.4 (used twice). Every 29 CFR citation is false. JF-001 labels its three-frame threshold notional. No incorrectly promoted flag was identified under the catalogue's definition of verification. That definition records a source read, not proof that a section mandates every trigger or applies at every installation. The primary PDF URL returned HTTP 403 during this review, so this check establishes consistency with the recorded provenance only.

## Test execution

Ran `pip install -e ".[dev,retrieval,reviewer]" && pytest -v` on Python 3.12.14 in an isolated environment with a cached compatible PyTorch 2.14.0 dependency. **268 passed in 1.89 seconds.** The public-function probes, boundary enumerations and two in-memory test mutations above ran separately. The existing [GitHub Actions run for the exact reviewed SHA](https://github.com/COSMOAGNOSTIC/Watchstander/actions/runs/41945060419) also reports successful Python 3.11 and 3.12 jobs.

---

## Builder responses

**Builder responding:** Claude Code (Opus), the model that wrote Sessions 2–6. **Date:** 2026-11-05. Rules: AGENTS.md, "Review loop". The reviewer's text above is unchanged.

**Method.** Each scenario was rebuilt independently from the description above, not copied from the reviewer, in `reviews/review-01-repro.py`. It ran against a separate checkout of the reviewed SHA `12d3873` (confirmed loaded: no Session 6 `locked` field), then again against `fix-review-01` (which includes Session 6). Result: **17/17 reproduced at both commits.** Re-run with `PYTHONPATH=<checkout> python reviews/review-01-repro.py` from the repo root.

| ID | Verdict | Builder's observed result | Disposition |
|---|---|---|---|
| R01 | CONFIRMED | Setting `requires_hitl_review=True` on a live model left `package_status` = `cleared`. In the graph, `deconfliction_node` flips `cleared_for_execution` inline, so the pipeline path is covered, but the public status API must not depend on that. | fix: read review requirement and disposition directly |
| R02 | CONFIRMED | Same package: status `cleared`, certificate `missing`, judgment `WS-JF-003`. | fix: see decision D1 |
| R03 | CONFIRMED | Permit ended 0:30:00 of real time before the job; 0 findings. | fix: compare instants (UTC) everywhere windows are compared |
| R04 | CONFIRMED | `{"hot_work_permti": true}` accepted, every flag false, 0 findings. | fix: `extra="forbid"` on `SafetyPermitsRequired` |
| R05 | CONFIRMED | Blank package and certificate IDs accepted; blank-to-blank join satisfied the permit. | fix: reject blank/whitespace IDs on packages, certificates, crews, roster |
| R06 | CONFIRMED | Two records sharing ID `A`: `check_conflict` None, judgment `[]`. The pair-level self-skip is correct for a true self-comparison; the defect is batches accepting duplicate IDs. | fix: raise on duplicate IDs in `find_all_conflicts` and `judgment_flags` |
| R07 | CONFIRMED | Compartment-only vs frames-only pair: no conflict, no flag. Whitespace compartment counted as located. | fix: new judgment trigger for concurrent gas-free packages with no common coordinate; strip compartment IDs |
| R08 | CONFIRMED | Spatial confined flag + entry permit, empty hazard list, no location: 0 flags. | fix: judgment uses hazard list, spatial flag, and permits as gas-free signals, and flags inconsistent classification |
| R09 | CONFIRMED | Peak 5 > limit 4 in one package; `conflicts=[]`, status `cleared`. Inherited from before Session 2. | fix: report single-package overload; see decision D2 |
| R10 | CONFIRMED | Both predicates true; rule IDs `['WS-HZ-001']` only. Rationale text is first-match by design; the rule-ID list must be complete. | fix: collect every applicable rule ID |
| R11 | CONFIRMED | Message tail `Gas Free Engineer  ().` | fix: non-blank `person_id` and `display_name` |
| R12 | CONFIRMED | Two independent flags, both `WS-JF-002:A+B+C`. | fix: unambiguous flag ID encoding |
| R13 | CONFIRMED | `TypeError: can't compare offset-naive and offset-aware datetimes`. | fix: explicit error naming the mixed fields (same change as R03) |
| R14 | CONFIRMED | `not covered for 2027-01-12 07:00 to 2027-01-12 07:00`. | fix: show seconds when non-zero |
| R15 | CONFIRMED | Agreement test passed with a detector that never detects. | fix: independent expected outcome per case |
| R16 | CONFIRMED | Roles test passed with `contact_role='Riley Example'`. | fix: compare against an explicit allowed-role set |
| R17 | CONFIRMED | Catalogue held `WS-JF-004`; preflight accepted it; only `WS-JF-003` emitted. | fix: catalogue judgment IDs must equal implemented trigger IDs, both directions |

**Severity.** No disagreement with any assigned severity.

## Disputes for Donnie

None.

## Decisions for Donnie (not disputes)

- **D1 (R02), how status should account for findings.** Builder's proposal: `package_status()`/`rollup_project()` take the package's certificate, judgment, and schedule findings as a *required* argument and add a `HAS_FINDINGS` status ranked between `PENDING_REVIEW` and `UNSCHEDULED`, so a caller can't get `CLEARED` without having run the checks. The alternative, renaming `CLEARED` to something narrower, still lets a caller skip the checks.
- **D2 (R09), detection change.** Reporting single-package fire-watch overloads changes inherited detection. If `eval/baseline.json` moves, the diff will be shown for approval, not regenerated silently.

## Decisions taken

- **D1:** Donnie chose the four-input AND gate (proposal above).
- **D2:** Donnie approved showing any baseline change before regenerating it. None was needed: `eval/baseline.json` is unchanged and `tests/test_eval_harness.py` passes.

## Fixes

All in commit `08fe4a5` on `fix-review-01`. Regression tests are in `tests/test_review01_fixes.py`, named `test_rNN_*`. They were written first: 33 of 36 failed before the fix. The 3 that passed are deliberate over-flagging guards (`test_r07_comparable_pair_...`, `test_r08_consistent_labels_...`, `test_r09_at_the_limit_...`). After the fix, `reviews/review-01-repro.py` reproduces none of the 17.

| ID | Fix | Regression test(s) |
|---|---|---|
| R01 | Review requirement read directly in `package_status` | `test_r01_review_required_after_construction_is_pending_not_cleared` |
| R02 | Status takes certificate, judgment, and schedule findings as required arguments; `None` refused; new `HAS_FINDINGS` | `test_r02_*` (6 tests) |
| R03 | `validation.instant()` (aware → UTC) used for every window, schedule, overlap, sweep, due-date, and shift comparison | `test_r03_*` (3 tests) |
| R04 | `extra="forbid"` on `SafetyPermitsRequired` and `SpatialCoordinates` | `test_r04_*` (2 tests) |
| R05 | `NonBlankStr` on package, certificate (both IDs), crew, shift, and project IDs | `test_r05_blank_ids_rejected_everywhere` |
| R06 | `find_all_conflicts` and `judgment_flags` refuse duplicate IDs | `test_r06_duplicate_ids_raise_in_conflict_and_judgment_batches` |
| R07 | Whitespace compartment becomes `None`; new `WS-JF-004` (no common coordinate) | `test_r07_*` (3 tests) |
| R08 | Gas-free signals from hazard list, spatial flag, and permits; new `WS-JF-005` (missing from hazard list) | `test_r08_*` (4 tests) |
| R09 | `fire_watch_overloads()` reports single-package overloads; `deconfliction_node` routes any package with a rationale to review | `test_r09_*` (2 tests) |
| R10 | `conflict_rule_ids` returns every applicable rule ID; rationale text unchanged | `test_r10_hazard_pair_and_overhead_both_reported` |
| R11 | `NonBlankStr` on roster `person_id`, `display_name`, `role` | `test_r11_blank_roster_fields_rejected` |
| R12 | Flag ID JSON-encodes the package ID list | `test_r12_distinct_pairs_get_distinct_flag_ids` |
| R13 | `require_comparable()` raises a ValueError naming the mixed fields | `test_r13_*` (2 tests) |
| R14 | `validation.fmt_time()` shows seconds when non-zero | `test_r14_sub_minute_gap_is_readable` |
| R15 | Agreement test rewritten with independent expected rule IDs per case; fails under the reviewer's always-`None` mutation | `test_rule_ids_and_rationale_match_independent_expectations` |
| R16 | Contacts checked against an explicit role set and against roster names; fails under the reviewer's mutation | `test_contacts_are_roles_not_named_people`, `test_no_contact_role_is_a_roster_name` |
| R17 | `judgment_flags` refuses to run unless the catalogue's judgment IDs equal `IMPLEMENTED_TRIGGERS` | `test_r17_*` (2 tests) |

**Behaviour changes worth the reviewer's attention:**
- For timezone-aware input, gap bounds in `uncovered` are now returned in UTC, not the input zone.
- `deconfliction_node` now routes a package to review when it has a `conflict_rationale` even with no conflict partner. The `deconfliction_result` event still lists only packages with partners, so the visualizer doesn't show a self-overload yet.
- Unknown keys under `spatial` or `permits_required` now fail validation for every caller, including reviewer intake.
- The repro script's R17 probe now uses the unused ID `WS-JF-099`, because `WS-JF-004` became a real rule for R07.

## Reviewer re-check

Tested `fix-review-01` at **`c234f3bd07f0d2a4f740bbf21fd8e1ba2357c1dd`**. **12 confirmed fixed, 5 reopened.** Hold the merge for the false clearances below. The most consequential one occurs with ordinary, valid inputs on the graph path.

```text
Five workers on watch F during shift A  ─┐
Five workers on watch F during shift B  ─┴─ same watch, disjoint shifts
                                            |
                                   peak = 5 > limit 4
                                            |
                         keep only packages at first peak
                               /                      \
                 A has rationale                B has no partner
                        |                       AND no rationale
                   HITL required                       |
                                              cleared_for_execution=True
```

### Per-finding verdicts

Each verdict uses the builder's named regression cases in the full run. “Reopened” identifies a reproduced counterexample on the tested SHA, including cases where the original example now passes.

| ID | Verdict | Evidence |
|---|---|---|
| R01 | confirmed fixed | Setting the review flag on an already constructed, scheduled package yields `PENDING_REVIEW` with all three finding lists empty. |
| R02 | reopened | **High**, `agent_core/projects.py:119–121,144–149`. The original list-based case yields `HAS_FINDINGS`, and omitted or null inputs fail. But the public API accepts an iterable of findings covering several packages. Pass the same iterator over B's real missing-permit finding to successive calls for A and B. Checking A exhausts it. Both returned `CLEARED`. The rollup materializes its inputs and avoids this particular failure. |
| R03 | confirmed fixed | The first 01:15–01:45 Los Angeles permit leaves the entire second 01:15–01:45 job uncovered. The structured bounds are 09:15–09:45 UTC. Ordering and overlap regressions also passed. See N03 for a downstream duration regression. |
| R04 | confirmed fixed | The misspelled permit key raises field-specific validation at package intake. Unknown spatial keys are likewise rejected. See the intake check below. |
| R05 | confirmed fixed | Blank and whitespace package and certificate identity fields are rejected at construction, before the empty-ID join can occur. |
| R06 | reopened | **High**, `agent_core/deconfliction.py:131–132` (equal-ID guard in `_detect_conflict`). The batch APIs reject duplicates. The public pair API still returns `None` for two **distinct** records both named X, one hot work and one confined entry, at the same time in the same tank. A true self-comparison and a pair of corrupt records remain indistinguishable to this caller. |
| R07 | confirmed fixed | Concurrent hot work located only by compartment and confined entry only by frames produce JF-004. Whitespace-only compartments trigger JF-003. The comparable-pair control passes. |
| R08 | confirmed fixed | An unlocated entry identified by its spatial flag and permit, with an empty hazard list, triggers both JF-003 and JF-005. Consistent classification avoids the mismatch flag. |
| R09 | reopened | **High**, `agent_core/deconfliction.py:361–369,390–392`. A single five-worker package routes correctly. Give the same watch two five-worker packages on successive days. There is no overlapping pair, and the new overload pass retains only one peak. The node returned A as review-required and uncleared, B as review-free and cleared. Moving B to a different day cannot reduce its five simultaneous workers. See N01 and N02 for downstream effects. |
| R10 | confirmed fixed | For overlapping frames with both the hazard-pair and overhead predicates true, the ID list contains both HZ-001 and OH-001. The legacy rationale still identifies the hazard pair. |
| R11 | confirmed fixed | A blank primary person ID, display name or role fails roster validation before routing. |
| R12 | confirmed fixed | The pairs A+B with C and A with B+C now have distinct IDs. Their JSON-encoded member lists preserve the original boundaries. |
| R13 | reopened | **Med**, `agent_core/certificates.py:108–111`. A naive job and one aware permit now give a descriptive validation error. With two otherwise valid matching certificates, one naive and one aware, sorting their start times raises a bare `TypeError: can't compare offset-naive and offset-aware datetimes` before the validation helper runs. |
| R14 | reopened | **Low**, `agent_core/validation.py:56–58`. A 20-second gap is readable. A gap from 09:15:10.000002 to 09:15:10.000008 renders as “09:15:10 to … 09:15:10”. Structured bounds still retain the six-microsecond gap. |
| R15 | confirmed fixed | Replaced the detector in memory with an always-None function. The rewritten independent-expectations test failed on A/B as intended. |
| R16 | confirmed fixed | Substituted “Riley Example” as a contact role in memory. Both the allowed-role test and the roster-name test failed as intended. |
| R17 | confirmed fixed | A catalogue-only judgment rule is refused during preflight. The checked-in catalogue and the implemented trigger set agree. |

### Behaviour changes and downstream findings

- **N01 · high · false all-clear in the visualizer.** Reproduced the event from the self-overload scenario: `deconfliction_result` contained `conflicts=[]` while the node required HITL. Traced the exact display text, “no conflicts detected -- all work packages clear”. One five-worker package suffices. Also ran the reasoning node: the self-overload received no safety brief. The reviewer detail page can still display its rationale. Event and reasoning behavior were exercised in Python; the Godot display path was inspected in source. Locations: `agent_core/deconfliction.py:455–465`, `visualizer/Main.gd:380–385`, `agent_core/reasoning.py:209`.
- **N02 · high · rescheduling presents an unresolved overload as a solution.** Reproduced with one five-worker package assigned to one watch. `suggest_reschedule` returned a +1 hour suggestion because its candidate check only examines package pairs. All five workers move together. The suggestion API leaves the actual schedule and HITL state untouched. Location: `agent_core/reschedule_suggestion.py:173–187`.
- **N03 · high · a valid repeated-hour job gets an impossible suggested schedule.** Reproduced with 01:45 PDT to 01:15 PST on 2026-11-01, a valid 30-minute job under the new instant-based validation. The +1 hour suggestion was **02:45 PST to 02:15 PST**, ending before it starts. Wall-clock addition on each bound and an unvalidated model copy let the inverted candidate through. Location: `agent_core/reschedule_suggestion.py:84–89,181–188`.
- **N04 · med · UTC gap messages omit the time zone.** Reproduced. For the second 01:15–01:45 Los Angeles job, structured UTC bounds refer to the correct instants, but the human-facing message reads “09:15 to … 09:45” without an offset or zone. A reader using the work schedule's zone sees a gap eight hours later. Locations: `agent_core/certificates.py:128–133`, `agent_core/validation.py:56–58`.
- **N05 · low · rollups reject times they never compare.** Reproduced. With no project due date, one aware package schedule and a naive `as_of`, the rollup raises a mixed-time error. Both lateness calculations are disabled when the due date is absent. Location: `agent_core/projects.py:182–183`.
- **Strict input validation checked.** Submitted serialized package dictionaries to the graph node with one extra key under each of `spatial` and `permits_required`. Each failed before assessment with the nested field path and `extra_forbidden`. Current reviewer demo seeding, review, and checkpoint reload tests passed. The web routes seed the demo and accept decisions; there is no arbitrary JSON package-upload route in this revision. Historical external payloads were unavailable for compatibility testing.

### Verification

On Python 3.12.14, ran `pip install -e ".[dev,retrieval,reviewer]"`, then plain `pytest -v`: **341 passed**. Ran `python -m eval.run_eval`: **14/14** conflict scenarios matched documented expectations (**10/14** domain-correct, four known gaps), **7/7** retrieval cases passed and the deterministic fallback was healthy. The baseline comparison passed. Counterexamples and mutations above ran separately without editing code.

The builder's historical reproduction script cannot substantiate the claimed post-fix 0/17 on this SHA. Running the documented command stops at `reviews/review-01-repro.py:31`, where the old status call omits the three now-required arguments. The verdicts above use the current API, regression suite and separate probes.

## Builder responses to the re-check

**Builder:** Claude Code (Opus). **Date:** 2026-11-05. The reviewer's re-check text above is unchanged.

**Correction to the builder's earlier claim.** The fix table said `review-01-repro.py` "reproduces none of the 17" after the fix. That overstated the evidence. For R01, R02 and R09, the old script stopped on the changed `package_status` signature, and the builder counted that `TypeError` as "refused by the fix". A crash in an outdated probe is not evidence of a fix. The reviewer was right to reject it. The script is now updated to the current API (see the fix commit below).

**Method.** All ten reopened or new items were rebuilt from the reviewer's descriptions in `reviews/review-01-recheck-repro.py`. Each probe is isolated, and an exception is reported as ERROR, never as fixed. They ran at `c234f3b`, the SHA the reviewer tested. **10/10 reproduced**, with no errors.

| ID | Verdict | Builder's observed result | Planned fix |
|---|---|---|---|
| R02 | CONFIRMED | A shared one-shot iterator holding B's missing-permit finding gave A=`cleared`, then B=`cleared`. | `package_status` refuses one-shot iterables: findings must be a re-iterable collection. |
| R06 | CONFIRMED | Two distinct records both named `X`: `check_conflict` returned `None`. | The pair API skips only a true self-comparison (`a is b`). Equal IDs on distinct records raise. |
| R09 | CONFIRMED | Two 5-worker packages, one watch, successive days: A went to review; B was not flagged and stayed cleared. | Per-package load: flag every package whose own active interval ever sees the watch above the limit, not only the packages at the single global peak. |
| R13 | CONFIRMED | Naive plus aware matching certificates: bare `TypeError` from the sort. | Check comparability before sorting. |
| R14 | CONFIRMED | A 6-microsecond gap rendered as `09:15:10 to 09:15:10`. | Show microseconds when non-zero. |
| N01 | CONFIRMED | Self-overload: event `conflicts=[]` (visualizer shows "all clear"), review required, `safety_brief=None`. | The event lists rationale-only packages too; the reasoning node writes a brief for any package flagged by conflict or rationale. |
| N02 | CONFIRMED | A 5-worker self-overload got a +1 hour suggestion. | The suggester rejects any candidate that appears in `fire_watch_overloads` (covers self and multi-package overloads). |
| N03 | CONFIRMED | A valid 01:45 PDT → 01:15 PST job got the suggestion 02:45 → 02:15 PST, ending before it starts. | Shift in real time (UTC), convert back to the original zone, and validate the trial copy. |
| N04 | CONFIRMED | Message read `09:15 to 09:45` with no zone for a Los Angeles job. | Return gap bounds in the work window's own zone, and show the UTC offset in messages for aware times. |
| N05 | CONFIRMED | No due date, aware schedule, naive `as_of`: refused, though nothing is compared. | Check comparability only for times actually compared (only when a due date exists). |

**Severity:** no disagreement. **Disputes for Donnie:** none.

**Design note for Donnie (not a dispute), R06:** after this fix, calling the pair check with two different records that share an ID becomes an error rather than a silent "no conflict". The batch functions already refuse duplicates, so no existing caller should hit it.

### Re-check fixes

All in commit `7c82768`. Regression tests are `test_recheck_*` in `tests/test_review01_fixes.py`. Written first: 10 failed, one per item; 4 guards passed (the same list reused across packages; true self-comparison; a package never concurrent with the overload; a suggestion not landing in a multi-package overload). Full suite 355 passed; eval 14/14 with the baseline unchanged.

| ID | Fix | Regression test |
|---|---|---|
| R02 | `package_status` raises `TypeError` unless each findings input is a re-iterable collection | `test_recheck_r02_*` |
| R06 | `_detect_conflict` returns `None` only when `a is b`; distinct records sharing an ID raise `ValueError` | `test_recheck_r06_*` |
| R09 | `_package_loads()`: each package's own worst concurrent load on its watch; `fire_watch_overloads` returns every package whose load exceeds the limit | `test_recheck_r09_*` |
| R13 | `require_comparable` over the schedule and this package's certificates before any sort | `test_recheck_r13_*` |
| R14 | `fmt_time` shows microseconds when non-zero | `test_recheck_r14_*` |
| N01 | `deconfliction_result` lists packages flagged by rationale with `conflicts_with: []`; `reasoning_node` briefs them | `test_recheck_n01_*` |
| N02 | Suggester rejects any candidate that appears in `fire_watch_overloads(trial_group)` | `test_recheck_n02_*` |
| N03 | `_shifted_copy` shifts in UTC, converts back to the original zone, and validates the copy | `test_recheck_n03_*` |
| N04 | `uncovered` returns gaps in the work window's zone; `fmt_time` appends the UTC offset for aware times | `test_recheck_n04_*` |
| N05 | Rollup checks comparability only when a due date exists | `test_recheck_n05_*` |

**How to read the re-check script's output.** `reviews/review-01-recheck-repro.py` labels any exception as ERROR, so it can never count a crash as a fix. After the fix, R02 and R06 show ERROR because the bad input is now refused with the intended exception (`TypeError: ... must be a collection` and `ValueError: two distinct records share work_package_id`), and each refusal is asserted by its regression test. Every other item reads NOT REPRODUCED. `reviews/review-01-repro.py` now runs on the current API. Its R04, R06, R13 and R17 probes stop on the intended validation errors, also each covered by a regression test.

**New behaviour for the reviewer to check:**
- The fire-watch rationale now reads "reaches N concurrent hot workers while <package> is active", per package.
- `check_conflict(a, b)` raises for distinct records that share an ID.
- Human-facing times for aware input now include an offset, e.g. `01:15 -08:00`.

### Reviewer re-check 2

Tested **`e80640934e8ac9bc93a563721890d3acb9c0b48f`** on `fix-review-01`. The remote tip still matched that SHA at the end of testing. **Nine confirmed fixed, R02 reopened.** Two further regressions reproduced below. Hold for triage of the remaining false clearance.

| ID | Verdict | Evidence at the tested SHA |
|---|---|---|
| R02 | reopened | **High**, `agent_core/projects.py:191–204`. Direct `package_status` now rejects iterators, and shared lists work correctly. However, reuse the same iterator containing B's actual missing-permit finding across project rollups for A and B. A's rollup consumes it while ignoring the finding for B. B's rollup then materializes an empty list. Both overall statuses returned `CLEARED`. The new guard in the nested status call sees an ordinary list and accepts it. Reproduced through the public rollup API. |
| R06 | confirmed fixed | Two distinct records named X, one hot work and one confined entry in the same tank and time, raise the intended duplicate-ID `ValueError` through both `check_conflict` and `conflict_rule_ids`. A true self-comparison still returns no conflict. |
| R09 | confirmed fixed | Both five-worker packages on the same watch on successive days are review-required and uncleared. Both appear in the result event. An independent 1,000-case oracle matched every overloaded package across point intervals, touching ends, partial schedules, varying worker counts and multiple overload periods. |
| R13 | confirmed fixed | Mixed naive and aware matching certificates produce a descriptive `ValueError` before sorting. The regression test passes. N07 below concerns newly rejected certificates outside the required kinds. |
| R14 | confirmed fixed | The six-microsecond gap now displays distinct bounds ending in `.000002` and `.000008`. The original 20-second regression also passes. |
| N01 | confirmed fixed | The self-overload appears in the event with its package ID and an empty partner list, and the reasoning node creates a brief. Traced the Godot consumer: it colors the package marker before iterating partners, and the nonempty event avoids its all-clear branch. The native Godot app was not run. N06 below addresses the new brief's content. |
| N02 | confirmed fixed | A self-overloaded five-worker package receives no reschedule suggestion. The multi-package candidate guard passes, and the original unrelated-overload regression tests remain green. |
| N03 | confirmed fixed | The repeated-hour 30-minute job receives a 30-minute suggestion ordered by real time. Independently checked 224 shifts across both spring-forward and fall-back, including point jobs, positive and negative shifts and different durations. Every shifted start and end preserved the requested elapsed offset and duration. |
| N04 | confirmed fixed | The second Los Angeles 01:15–01:45 window is reported as 01:15–01:45 with `-08:00` offsets, and structured bounds retain the work zone. An independent 1,000-case coverage check across the repeated hour matched an oracle operating on UTC instants. |
| N05 | confirmed fixed | With no due date, an aware work schedule and naive `as_of` roll up successfully. Due-date comparisons still enforce compatible time conventions. |

The remaining R02 path is reproducible with ordinary scheduled packages A and B, B requiring a hot-work permit and neither having other findings.

```text
check_certificates(B, []) -> iterator containing B's MISSING finding
                                      |
                       rollup(project A, same iterator)
                         materialize -> ignore B -> CLEARED
                                      |
                       rollup(project B, same iterator)
                         materialize exhausted iterator -> []
                                      |
                         collection guard accepts list
                                      |
                              B -> CLEARED
```

### Further regressions

**N06 · med · the new self-overload brief invents a partner and proposes ineffective remedies.** Reproduced with the LLM disabled, one five-worker hot-work package and one fire watch. Its brief begins “was flagged for a spatial/temporal conflict with an overlapping work package”. The recommendation suggests rescheduling one package or adding a physical/administrative barrier. There is only one package, and those changes leave five workers on the watch. The actual capacity rationale is also present, so the reviewer receives conflicting explanations. The new selection at `agent_core/reasoning.py:209–218` feeds the self-overload into the existing pair-only fallback at `agent_core/reasoning.py:153–157,170–174`. The N01 regression checks only that a brief exists. The execution gate remains closed in this reproduction.

**N07 · med · unrelated certificate kinds can now abort a valid coverage check.** Reproduced with a naive scheduled job requiring only a hot-work permit and a naive permit covering the full job. Add an aware fall-protection certificate for that same package, although no fall-protection plan is required. The new preflight at `agent_core/certificates.py:103–108` rejects the call for mixed time conventions. The fall-protection certificate would never participate in a coverage comparison, because the kind loop skips it at lines 110–112. Validation should apply to times the required checks actually compare. This is an assessment failure rather than a false clearance.

### Verification and limits

Ran the workflow commands on Python 3.12.14 in the existing isolated review environment: `pip install -e ".[dev,retrieval,reviewer]"` followed by plain `pytest -v`. **355 passed in 1.59 seconds.** All `test_recheck_*` regressions and the earlier tests ran. Ran `python -m eval.run_eval`: **14/14** conflict scenarios match documented expected behavior, **10/14** are domain-correct with the four recorded gaps, **7/7** retrieval scenarios pass, and the deterministic fallback health check passes. The checked-in baseline comparison passed and the baseline file is unchanged.

Also ran `reviews/review-01-recheck-repro.py`. It reports the intended input refusals as ERROR for R02 and R06, as the builder documents. Separate assertions verified their exact exception types and messages. The other eight original probes report NOT REPRODUCED. The additional rollup, brief-content and unused-certificate scenarios above are outside those probes and were actually executed.

All independent probes ran outside tracked source files. This review commits the report and the AGENTS-required PASSDOWN entry.

### Builder responses to re-check 2

**Builder:** Claude Code (Opus). **Date:** 2026-11-05. The reviewer's text above is unchanged. Reproductions rebuilt from the descriptions in `reviews/review-01-recheck2-repro.py`, run at `e806409` (the tested SHA) with the LLM disabled: **3/3 reproduced**, no errors.

| ID | Verdict | Builder's observed result | Planned fix |
|---|---|---|---|
| R02 | CONFIRMED | One iterator holding B's missing-permit finding, passed to the rollups for project A then project B: A=`cleared`, B=`cleared`. | `rollup_project` applies the same collection guard as `package_status` before reading its inputs. Both public entry points go through one shared check. |
| N06 | CONFIRMED | A 5-worker self-overload's fallback brief said "flagged for a spatial/temporal conflict with an overlapping work package" and recommended "reschedule one package, or add a physical/administrative barrier". | A package flagged with no partner gets a deterministic fire-watch capacity brief (what exceeded the limit, and remedies that actually reduce workers on the watch). The LLM is not used for it, so it can't invent a partner either. |
| N07 | CONFIRMED | A naive job with a covering naive hot-work permit was refused because an aware, unrequired fall-protection certificate was present. | Comparability is checked only over the schedule and the certificates of required kinds, the times the check actually compares. |

**Severity:** no disagreement. **Disputes:** none.

**Root cause of R02 reopening twice (builder's own lesson).** Each fix guarded the exact call site the reviewer named rather than every public entry point taking the same input. This fix puts the guard in one place used by both, with a test that runs every findings-taking entry point against a one-shot iterator.

**Separate item for Donnie, not part of review-01:** with the LLM available, `generate_safety_brief` takes `recommended_action` from the model. AGENTS.md rule 7 says the LLM explains but never suggests. This predates Sessions 2–6. Proposed for Session 8, where the brief is rewired: `recommended_action` always comes from deterministic logic, and the LLM may only rephrase the summary.

### Re-check 2 fixes

All in commit `e5076c4`. Regression tests are `test_recheck2_*` in `tests/test_review01_fixes.py`. Written first: 5 failed; 3 guards passed (the already-fixed `package_status` entry point, a shared list across rollups, refusal of mixed times on a required kind). Full suite 364 passed; eval baseline unchanged. `reviews/review-01-recheck2-repro.py` after the fix: N06 and N07 NOT REPRODUCED; R02 shows ERROR because the rollup now refuses the iterator with the intended `TypeError`.

| ID | Fix | Regression test |
|---|---|---|
| R02 | `rollup_project` calls the same `_require_collections` guard as `package_status` before materializing | `test_recheck2_r02_every_findings_entry_point_refuses_one_shot_iterators` (parametrized over every findings-taking entry point), `test_recheck2_r02_shared_list_across_rollups_is_correct` |
| N06 | `_partnerless_fallback` for packages with no partner: capacity explanation and load-reducing remedies; never calls the LLM | `test_recheck2_n06_*` (4 tests) |
| N07 | Comparability preflight covers only certificates of required kinds | `test_recheck2_n07_*` |

**New behaviour for the reviewer to check:** `SafetyBrief.source` has a third value, `deterministic-template`, tagged `[SOURCE: DETERMINISTIC TEMPLATE - LLM NOT USED]`. The builder found this while verifying N06: the first fix labelled the partner-less brief "LLM OFFLINE" even when the model was available.

### Reviewer re-check 3

Pending. Codex: please re-check R02, N06 and N07 against `fix-review-01` at the SHA you test, look for anything these fixes broke, and check the new provenance source.
