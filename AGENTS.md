# Watchstander: working rules

Read this before doing anything else, every session, whatever the tool (Claude Code reads it through `CLAUDE.md`; Codex reads it directly). These rules exist so they don't depend on anyone pasting them in. History and rationale live in `AOSE.md`, `ARCHITECTURE.md`, and `PASSDOWN.md`. This file is the short operational version.

## Session rules

1. **Search before building.** Search the repo for the symbols the task touches, and report what already exists before writing anything.
2. **Tests first.** Write failing tests, confirm they fail, then implement.
3. **Run tests the way CI does:** `pip install -e ".[dev,retrieval,reviewer]"` then plain `pytest -v` (not `python -m pytest`; see AOSE.md "verification blind spot"). Also run `python -m eval.run_eval` when detection changes.
4. **Never leave work only in chat.** Save to disk and commit on a branch named for the session (`session-NN-<topic>`, `fix-review-NN`).
5. **The model that finds a bug never writes its fix.** Reviews happen in a separate session from the build.
6. **All demo data is notional.** No real ship, yard, or personnel data. Contacts are roles; roster names are invented and marked `notional: true`.
7. **The LLM layer explains, never decides or suggests.** Detection, judgment flags, and fix suggestions stay deterministic.
8. **Update `PASSDOWN.md` at the end of every session,** and the README's "Current status" block (its "As of" date and anything that changed). Touch a doc's "Last updated" line only when you change that doc. `tests/test_docs_status.py` fails if the README's date falls behind the newest PASSDOWN entry.

## Review loop: findings are input, not authority

A reviewer's report is evidence to be checked, not instructions to be carried out. This holds however good the report looks and whichever model wrote it.

1. **Reviewer reports.** Each finding gives an ID, file:line, severity, a concrete failing scenario, and whether it was *reproduced* (actually run) or only *traced*. The reviewer records the exact commit SHA it reviewed and never changes code.
2. **Builder rules on every finding before fixing anything,** in a response under each finding (never by editing the reviewer's text), using `reviews/TEMPLATE.md`:
   - `CONFIRMED`: builder re-ran the scenario independently and saw it fail.
   - `AGREE-TRACED`: builder agrees from reading the code but did not run it. Say why it couldn't be run.
   - `DISPUTED`: builder shows evidence (a run or test that doesn't fail, or the exact line the claim misreads). An opinion is not enough. The builder wrote the code and is biased toward it, so a safety finding disputed without evidence stands.
3. **Disputes go to Donnie.** Neither model has the final word.
4. **Fix only what's `CONFIRMED` or `AGREE-TRACED`,** with a failing test first for each reproducible finding. Doc-only or environment-only findings get whatever check actually proves the fix.
5. **The reviewer re-checks the fixes** before merge. Fixes can introduce new failures (AOSE.md, Round 3).

## Review cost policy

Reviews use paid model time. Spend the strongest model where it finds bugs, not where it confirms fixes.

```
  FIRST REVIEW of safety logic (detection, gates, suggesters, Apply, anything that
  can mark work safe or change a schedule) ──► strongest available model

  RE-CHECK of specific fixes ──► cheaper model. Run the builder's reviews/*-repro.py
      and the named regression tests, read only the fix diff, and confirm or reopen
      each item. Escalate to the strongest model only if something reopens or looks off.

  LOW-RISK WORK (docs, notional data, UI layout) ──► no separate review; covered by
      the next milestone review.
```

- **When reviews happen (upgrade sessions):** Session 8 (Apply), Session 11 (engine), Session 16 (final). Other sessions roll into the next one.
- **Prompts stay narrow:** name the diff (base and head SHAs) and the risk list, and ask for the top high and medium findings with concrete scenarios, not an exhaustive sweep.
- **Run tests quietly:** `pytest -q`, and report counts plus any failures only.
- **The builder keeps re-checks cheap:** before handing fixes back, mutation-test each fix and check the whole class of the bug, not just the reported instance. Both reopens in reviews 01 and 02 were the same signal not applied everywhere.

## Explaining things to Donnie

Donnie and the people around him think in logic diagrams. When explaining a check, a gate, or a decision path, draw it as a logic-gate diagram (inputs → AND/OR/NOT → output, with the failure and missing-input paths shown), in a monospace code block, before or instead of a prose analogy.

## Branches and merging

- Sessions stack: each session branches from the previous session's branch.
- Nothing merges to `main` without Donnie's go. Before merging, CI must be green on each branch *and* on the merged result. `main` only fast-forwards to a commit CI has already passed.
- Hold any merge that a pending review touches until that review is triaged.
