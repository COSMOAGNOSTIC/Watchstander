# PASSDOWN — Grounding Retrieval Harness

Session-by-session log, newest entry on top. Answers "what's done, what's
next, what was decided but not built" so this can be picked back up cold.

---

## Session 1 — 2026-08-04 — Phase 0 scaffold

**Status:** Phase 0 complete. Nothing before this session; this is the
project's first working session in Claude Code (prior session, elsewhere,
produced the placement/tooling decisions this session executed against —
see below).

**What happened:**
- Confirmed with Donnie: proceed with Phase 0 now, using the
  aose-project-scaffold methodology (already decided pre-session, per the
  passdown this session started from).
- Inspected the existing Watchstander repo before scaffolding anything: it
  already has its own root-level MIGRATION.md/ARCHITECTURE.md/PASSDOWN.md/
  AOSE.md tracking the deconfliction agent project itself (currently Phase
  6, "Lock it in", in progress) — decided to give this sub-project its own
  scoped doc set inside `retrieval/` rather than injecting new phases into
  the root docs, per the scaffold skill's own guidance to split by
  component when a doc set would otherwise balloon or conflate two
  projects.
- Found and flagged a real architectural tension while writing the decision
  log: `agent_core/retrieval.py` explicitly rejected ChromaDB +
  sentence-transformers for the live graph because Watchstander is
  documented edge-first / zero-network. This project's Phase 1 plan is
  exactly that stack. Resolved for now (ADR-003, `retrieval/ARCHITECTURE.md`)
  as: fine as long as this stays a standalone harness never imported by
  `agent_core`; must be explicitly revisited if that ever changes. Not a
  blocker for Phase 0 or Phase 1, but worth knowing before Phase 1 starts,
  not after.
- Built the five Phase 0 modules (`chunker.py`, `embedder.py`,
  `vector_store.py`, `retriever.py`, `citation_formatter.py`) — real
  dataclasses for every data model, every function/method body a
  `NotImplementedError` pointing at Phase 1.
- Added `tests/test_retrieval_*.py` (five files) — assert the data models
  are real and the boundaries exist/raise as documented. Deliberately not
  vacuous: each test either constructs a real dataclass and checks its
  fields, or asserts the documented `NotImplementedError`.
- Fixed `pyproject.toml` `packages.find` to include `retrieval*` proactively
  — the repo's own history (root MIGRATION.md Phase 6) shows exactly this
  omission happening with `eval/` and going undetected locally while CI
  stayed red. No reason to repeat that here.
- Wrote `retrieval/README.md`, `MIGRATION.md`, `ARCHITECTURE.md` (this
  file's sibling), and this file.
- Added a short pointer section to the repo-root `README.md` so the
  sub-project doesn't go undiscoverable.

**What's decided but not built:** Everything in MIGRATION.md Phase 1 onward
— corpus ingestion, real chunking, sentence-transformers embedding, Chroma
storage, real retrieval, real citation formatting, hybrid retrieval,
SageMaker exposure, Databricks exposure, certs.

**Open questions for next session:**
- NAVSEA 8010 source text: chunk from the already-structured
  `case_data/navsea_8010_psns_v2014.json`, or pull the manual's original
  text fresh? (ARCHITECTURE.md §5)
- `pyproject.toml`'s `retrieval` optional-dependency group
  (`sentence-transformers`, `chromadb`) still needs adding — deliberately
  not added this session since nothing uses them yet.

---

## Session 2 — 2026-08-04 — Phase 0 AOSE round

**Status:** Phase 0 AOSE Round 1 complete (see `AOSE.md`). Phase 0 fully
closed as of this session — this entry was never added at the time, which
left this file's "Next up" line stale (still describing the AOSE round as a
future step) even though `AOSE.md` itself was current. Backfilled 2026-08-08
alongside Session 3 below, once the staleness was caught.

**What happened:** Ran Round 1 of the adversarial-review loop against the
Phase 0 skeleton — packaging (verified the `packages.find` fix under a
fresh install + CI-equivalent bare `pytest` invocation, not just locally),
the `retrieval`/`agent_core.retrieval` naming collision (grepped for and
ruled out any existing bare `import retrieval`), and a general pass over
every stubbed function/dataclass for anything that could be wrong at a
skeleton stage. One real fix made (`Retriever.__init__` gained a type hint
on `vector_store`); one risk logged as accepted, not fixed (a *future* bare
`import retrieval` inside `agent_core` would silently resolve to the wrong
package — low severity, fails loud). Full writeup in `AOSE.md`.

**Next up:** Phase 1 — local RAG proof.

---

## Session 3 — 2026-08-08 — Independent re-verification of the Phase 0 AOSE round, doc staleness fixed

**Status:** Phase 0 confirmed still closed. No new code changes — this
session was a documentation-integrity check, not a build session.

**What happened:** Before starting Phase 1, re-ran Round 1's three testable
claims independently rather than trusting the write-up at face value (same
principle root `AOSE.md` already states: re-reading a prior finding isn't
verification, re-running it is). All three held with no drift: 78/78 tests
pass from a genuinely fresh venv + editable install + bare `pytest`
console-script invocation; no bare `import retrieval` exists anywhere in the
repo and `retrieval`/`agent_core.retrieval` still resolve to two distinct
files; `Retriever.__init__`'s type hint from Round 1's fix is still present.
Logged as its own dated entry in `AOSE.md` rather than silently folded into
Round 1.

While doing this, caught and fixed the actual bug this check surfaced: this
file's "Next up" line (previously at the end of Session 1) still described
the Phase 0 AOSE round as a future step, even though `AOSE.md` showed it
completed four days earlier. Backfilled the missing Session 2 entry above
so the record matches what actually happened, and moved "Next up" here,
where it's current.

**Next up:** Phase 1 — local RAG proof (see MIGRATION.md for scope: corpus
ingestion, real chunking, sentence-transformers embedding, Chroma storage,
real retrieval, real citation formatting). Open questions from Session 1
(NAVSEA 8010 source text choice; `retrieval` optional-dependency group)
still need a decision before or during Phase 1 — neither resolved by this
session.

---

## Session 4 — 2026-08-08 — NAVSEA 8010 source decision

**Status:** One of Session 1's two open questions resolved. The
`retrieval` optional-dependency group (`sentence-transformers`, `chromadb`)
remains open — deliberately, still not needed until Phase 1 actually starts
wiring code against them.

**What happened:** Donnie decided the NAVSEA 8010 chunking source: pull the
original manual text (Chapters 4 and 11) fresh, rather than chunk the
already-extracted `case_data/navsea_8010_psns_v2014.json` summaries. Framed
explicitly as choosing the harder path on purpose — the extraction-and-
wiring work is itself the point of this sub-project, and doing it now, on a
small corpus, while the stakes are low, beats deferring it. Logged as
ADR-005 in `ARCHITECTURE.md` §4, with the reasoning and scope (Chapters 4
and 11 specifically, not the full manual) captured there rather than just in
chat. `MIGRATION.md`'s Phase 1 checklist and `ARCHITECTURE.md` §1's corpus
description updated to match. No code written this session — Chapters 4/11
still need to actually be sourced/extracted from the PDF before Phase 1's
ingestion step can start.

**Next up:** Phase 1 — local RAG proof. Immediate next action, before any
chunking/embedding code: source and extract the actual text of NAVSEA 8010
Chapters 4 and 11 from the primary PDF (confirmed public domain, NAVSEA's
own FOIA reading room — see ADR-005 for the citation). The `retrieval`
optional-dependency group still needs adding to `pyproject.toml` once
`sentence-transformers`/`chromadb` are actually used.
