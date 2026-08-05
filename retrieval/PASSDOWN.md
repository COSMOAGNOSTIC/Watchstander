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

**Next up:** Phase 1 — local RAG proof. Do the Phase 0 AOSE round first (see
AOSE.md) before calling Phase 0 fully closed, then start Phase 1.
