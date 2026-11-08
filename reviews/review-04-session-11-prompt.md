# Review 04 (upgrade Session 11): prompt for the reviewer

Paste everything below the line into a **separate** session running the **strongest available model** (AGENTS.md review cost policy: first review of safety logic). The builder doesn't review its own work (AGENTS.md rule 5).

---

You are reviewing the Watchstander repo (https://github.com/COSMOAGNOSTIC/Watchstander). Read `AGENTS.md` first and follow its "Review loop" section. Change no code. Write your report to `reviews/review-04-session-11.md` using `reviews/TEMPLATE.md`, on a new branch `review-04-session-11` cut from the head below, then commit and push that one file (plus an optional `reviews/review-04-repro.py`).

**Diff under review:** `1f3b716608158436542b6ad63eaa3507bf9bacac..96447220b0db4b5c4dcfd05abe66f228f180807e` on branch `session-10-carrier-brief` (the commit after the head only adds this prompt file). Record the exact head SHA you reviewed. The base is `main` (Sessions 1–8 and reviews 01–03, already reviewed). The diff stacks three branches: Session 9 (decision log), a docs-only sync, and Session 10 (notional carrier dataset, daily brief, real-ship demo deleted). Docs-only changes are low priority.

**Setup, exactly as CI runs it:**
```bash
pip install -e ".[dev,retrieval,reviewer]"
pytest -q
python -m eval.run_eval
```
Use plain `pytest`, not `python -m pytest`. Report counts and failures only.

**What to look for.** The top high and medium findings, each with a concrete failing scenario. Not an exhaustive sweep, not style. For each finding give an ID (S11-NN), `file:line`, severity, the scenario (input → observed result), and whether you **reproduced** it (actually ran it) or only **traced** it.

**Risk list, highest first:**

1. **Decision log completeness** (`reviewer/graph_driver.py`, `agent_core/decision_log.py`). Is there any path where a decision, refused decision, Apply, refused Apply, supersession or crash recovery happens but isn't logged, or is logged with the wrong disposition, actor, run or package? Check exception paths and the op lock. Can a logged entry claim something that didn't happen?
2. **Log integrity.** Triggers refuse UPDATE/DELETE, `verify_chain()` recomputes hashes, and `verify_anchor(seq, hash)` checks an externally recorded head. Can any edit, reorder, insert, truncation or replacement pass `verify_chain()` plus a correct anchor? Can `append()` produce a broken chain under concurrency (two services, two threads)? Does canonicalization cover every stored column?
3. **Daily brief fidelity** (`agent_core/daily_brief.py`). It's meant to show every finding the graph would route to a person. Find a package the graph routes to review whose rule, contact or reason is missing from the brief, a package the brief shows as cleared that the graph wouldn't clear, or a suggestion shown that `Apply` would refuse. Does `run_checks()` compute its findings from the same inputs the graph nodes use? Rule 7: does anything here decide or suggest beyond deterministic code?
4. **Dataset loader** (`agent_core/carrier_demo.py`). Can data that isn't notional, or that has dangling references, load? Do the scenario-to-rule pins in `tests/test_session10.py` actually prove each scenario triggers its rule, or could a scenario stop working while the tests still pass?
5. **Roster StrictBool change** (`agent_core/judgment.py`). Any regression in routing or roster loading?
6. **Reviewer default demo and ACUSHNET deletion.** Any remaining real-ship data (rule 6) the guard test misses? Any test that lost meaning when it was ported from ACUSHNET to the notional carrier?

**Known and accepted, don't report unless you find a new consequence:** actor names are self-declared (no login); nothing records the head anchor automatically; a crash between a decision's checkpoint write and its log append loses that one log entry; `rules_audit.py` isn't on the new log; the brief is pre-review (flagged packages read pending); the Godot scene change wasn't run in Godot; LangGraph's msgpack deserialization warning; database aliasing (hard links, network filesystems, bind mounts). See ARCHITECTURE.md Known Debt.

Keep it narrow: base and head SHAs, the risk list above, and the top findings only.
