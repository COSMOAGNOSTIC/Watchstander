# Review 04 re-check: prompt for the reviewer

Per AGENTS.md's review cost policy, this is a **re-check of specific fixes: use a cheaper model.** Escalate to the strongest model only if something reopens or looks off.

---

Re-check the builder's fixes for review-04 in the Watchstander repo (https://github.com/COSMOAGNOSTIC/Watchstander). Read `AGENTS.md`, then `reviews/review-04-session-11.md` (your findings S11-01 to S11-03 and the builder's responses). Change no production code.

**Fixes under re-check:** branch `fix-review-04`, commit `f2b9f2a` (and the docs-only commit after it). Diff to read: `git diff b5d4988 f2b9f2a -- reviewer/ agent_core/ tests/test_review04.py`.

**Do exactly this:**
1. `pip install -e ".[dev,retrieval,reviewer]"`, then plain `pytest -q` and `python -m eval.run_eval`. Report counts and failures only.
2. `python reviews/review-04-builder-repro.py`. Expect FIXED for all three; ERROR or REPRODUCED reopens the item.
3. Your own `reviews/review-04-repro.py` now stops at S11-01's new `ValueError` refusal by design. Run your scenarios with that expectation, or adapt a copy.
4. Read only the fix diff. For each finding, confirm fixed or reopen with a concrete scenario. Look especially for any `submit_decision` or `apply_shift_suggestion` outcome that still writes no log entry, writes two, or writes a kind that doesn't match what happened.

Write your result under each finding's **Reviewer re-check** line in `reviews/review-04-session-11.md` (do not edit the builder's text), on a branch `review-04-recheck` cut from `fix-review-04`, and push it.
