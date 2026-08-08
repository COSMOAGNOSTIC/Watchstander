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

Open `http://127.0.0.1:8000/`. Click **"Seed a real ACUSHNET demo run"** —
this runs the same real, sourced ACUSHNET compartment data
(`agent_core/demo_fixtures.py`) through the real graph: real deconfliction,
real reasoning (deterministic fallback unless `ANTHROPIC_API_KEY` is set),
and a real `interrupt()` for every flagged package. Three packages will show
up as pending review (two from a shared-compartment hot-work/confined-space
conflict, one from an overlapping-frame-range vertical-stacking conflict).

Click into a review, read the full brief and provenance tag, and hit Approve
or Reject with an optional note. That decision genuinely resumes the graph
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
  review right now is "seed the ACUSHNET demo." A real intake form (or an
  API endpoint a scheduling system could POST to) is a natural next step,
  not built this session.
- **No live-updating dashboard.** Refresh the page to see new state; no
  WebSocket push like the visualizer has.

## Relationship to the visualizer

Independent, not a replacement. The visualizer is a live *status* view (what's
happening, right now, across a whole roster). This is a *work* interface (what
needs a decision, and the full context to make it). A production system would
likely want both, wired to the same underlying graph runs.
