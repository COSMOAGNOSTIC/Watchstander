# HITL Reviewer — real approve/reject interface

A small local FastAPI app that is the human-facing counterpart the visualizer
was always missing: it shows the *full* flagged-package brief — description,
conflict rationale, synthesized safety brief, and whether that brief came
from a live LLM call or the deterministic fallback — and takes a real
Approve/Reject decision that resumes the actual LangGraph `interrupt()`. Not
a demo, not simulated: the same `build_graph()` the test suite exercises,
running for real.

## Why this exists

`visualizer/` (the Godot 2D/3D views) shows *that* a package is flagged and
waiting — a status light. It deliberately never shows *why*:
`agent_core/events.py` has an explicit policy to never broadcast full
descriptions, conflict rationale, or safety-brief content over its WebSocket.
That's correct for a public event stream, but it also means nothing in this
repo, before this app existed, let a human actually read a flagged package's
brief and make a real decision — the only things that ever answered a real
`interrupt()` were the test suite (hardcoding `"approve"`) and
`demo_broadcaster.py` (which doesn't even go through the real graph). See
ARCHITECTURE.md ADR-024 for the full design writeup.

## Running it

```
pip install -e ".[dev,reviewer]"
uvicorn reviewer.app:app --reload
```

Open `http://127.0.0.1:8000/`. Click **"Seed the notional carrier demo run"**.
This runs the notional carrier dataset (`case_data/carrier_notional_v1.json`,
invented end to end) through the real graph: real deconfliction, judgment flags,
certificate and schedule findings, real reasoning (deterministic fallback unless
`ANTHROPIC_API_KEY` is set), and a real `interrupt()` for every flagged package.
Nine of its eleven packages wait for review, each built to trigger one named rule
(hazard pair, overhead work, a judgment flag routed to the notional Gas Free
Engineer, a missing and an expiring certificate, a contractor outside its window).
Two show crew-shift suggestions you can Apply.

Click into a review, read the full brief and provenance tag, and hit Approve
or Reject with an optional note and your name (recorded in the decision log;
there is no login yet, so a blank name is recorded as "unidentified reviewer").

If the run was seeded with crews and a shift calendar (`ReviewerService.seed_run`),
a flagged package's brief also shows a deterministic crew-shift suggestion and
why any earlier shift was rejected. **Apply schedule change** re-checks the move
first, starts a new run with the moved times, supersedes this run's open reviews,
and never approves anything: every moved package still needs a decision. A run
seeded without crew data never shows a suggestion.

For a plain-text summary of the same checks, run
`python -m agent_core.daily_brief --as-of 2027-03-15T06:00 --db <reviewer db>`.
It prints the decision log's head hash; keep that line somewhere else and pass it
back with `--anchor SEQ:HASH` to detect entries removed from the end of the log.

`/log` lists every decision event (decisions, refused decisions, Applies,
supersessions, crash recovery) with the hash-chain check. That decision genuinely resumes the graph
— `reviewer/graph_driver.py`'s `submit_decision()` calls
`graph.invoke(Command(resume={interrupt_id: decision_text}), config=...)`,
the same mechanism `tests/test_graph.py` exercises directly. State persists
in `reviewer/reviewer_state.db` (gitignored, local only) via a real
`SqliteSaver`, so a review queued in one request survives to be decided in a
completely separate later request — this is what makes it usable as an
actual app instead of a single-process demo script.

## What it deliberately doesn't do (yet)

- **No auth.** Anyone who can reach the port can approve or reject anything.
  Fine for one local reviewer working their own queue on their own machine
  (same trust boundary the visualizer's undefended `ws://localhost:8081`
  already assumes) — not safe to expose beyond localhost as-is.
- **No real work-package intake form.** The only way to create a pending
  review right now is seeding a demo (or `ReviewerService.seed_run` from code). A real intake form (or an
  API endpoint a scheduling system could POST to) is a natural next step,
  not built this session.
- **No live-updating dashboard.** Refresh the page to see new state; no
  WebSocket push like the visualizer has.

## Relationship to the visualizer

Independent, not a replacement. The visualizer is a live *status* view (what's
happening, right now, across a whole roster). This is a *work* interface (what
needs a decision, and the full context to make it). A production system would
likely want both, wired to the same underlying graph runs.

## One reviewer service per database

`ReviewerService` holds an exclusive lock for as long as it runs, in a hidden file next to the database's real file, named by its identity (device and inode), so symlinks and other spellings of the path share it and the environment (e.g. `TMPDIR`) doesn't matter, and a second service on the same database refuses to start with "another reviewer service already has this database open". This is deliberate (review-03): Apply and decisions are serialized inside the one service, and crash recovery is only safe because no other live service can exist. If a service crashes, the OS releases the lock, and the next service to start finishes or rolls back any interrupted Apply. Multi-user review against one database would need a database server and real transactions; it is out of scope for now.

`flock` is not reliable on some network filesystems; keep the database on a local disk.

Don't open one database through hard links in different directories: SQLite itself documents multiple names for one database file as unsafe, and the reviewer's lock doesn't cover that case.
