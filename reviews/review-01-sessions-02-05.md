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

Pending. Codex: please re-check each fix against `fix-review-01` at the SHA you test, and record per finding: confirmed fixed, or reopened with a scenario. Please also look for anything the fixes broke (AOSE.md, Round 3).
