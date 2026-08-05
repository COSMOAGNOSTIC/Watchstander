# ARCHITECTURE — Grounding Retrieval Harness

Living, present-tense description of what `retrieval/` *is* right now. If
this doc and the code ever disagree, the doc is the bug.

## 1. What this is

A RAG (retrieval-augmented generation) skills-building project: a retrieval
harness that applies semantic search + citation grounding to the
Watchstander regulatory corpus (NAVSEA 8010 Manual, OSHA CFR 1915 excerpts,
`case_data/`). It exists to close specific platform gaps — RAG mechanics,
vector databases, AWS SageMaker, Databricks — surfaced by a real job
posting. See PASSDOWN.md for the full origin story.

## 2. Current structure (Phase 0)

```
retrieval/
  __init__.py            package docstring, disambiguation note
  chunker.py              Chunk dataclass, chunk_text() [Phase 1 stub]
  embedder.py              Embedding dataclass, embed_text()/embed_chunks() [Phase 1 stubs]
  vector_store.py          VectorStoreResult dataclass, VectorStore class [Phase 1 stubs]
  retriever.py              RetrievalResult dataclass, Retriever class [Phase 1 stub]
  citation_formatter.py     format_citation() [Phase 1 stub]
  README.md
  MIGRATION.md
  ARCHITECTURE.md          (this file)
  PASSDOWN.md
  AOSE.md

tests/
  test_retrieval_chunker.py
  test_retrieval_embedder.py
  test_retrieval_vector_store.py
  test_retrieval_retriever.py
  test_retrieval_citation_formatter.py
```

Data flow (target shape, once Phase 1 lands): raw corpus text ->
`chunker.chunk_text()` -> `Chunk`s -> `embedder.embed_chunks()` ->
`Embedding`s -> `vector_store.VectorStore.upsert()`. Query time: query string
-> `embedder.embed_text()` -> `vector_store.VectorStore.query()` ->
`retriever.Retriever.retrieve()` (owns strategy: top-k now, hybrid+rerank in
Phase 2) -> `RetrievalResult`s -> `citation_formatter.format_citation()` for
display.

Phase 0 implements every data model for real but leaves every function/method
body as `raise NotImplementedError(...)` pointing at Phase 1 — the interface
boundary is deliberately locked in before any real logic, so Phase 1 fills in
behavior against an already-agreed shape rather than discovering the shape
and the behavior at the same time.

## 3. Relationship to the rest of the repo

- **Not wired into `agent_core`'s live graph.** This package is a standalone
  teaching harness. Nothing in `agent_core/graph.py` imports from
  `retrieval/`, and nothing here should assume it will be, without a new ADR
  reconsidering §4 below.
- **Not the same thing as `agent_core/retrieval.py`.** That module is a
  small, pure-Python TF-IDF ranker used by the live safety agent to pick
  which sourced OSHA/DOL case to cite for a flagged conflict. It predates
  this package, is unrelated to it, and this package does not use, wrap, or
  modify it. The name collision (`retrieval.py` vs. `retrieval/`) is
  historical, not a design choice made here — see ADR-002 for why the
  directory is still named `retrieval/` anyway.
- **Own doc set, not the root one.** `MIGRATION.md` / `ARCHITECTURE.md` /
  `PASSDOWN.md` / `AOSE.md` exist at both the repo root (tracking the
  Watchstander deconfliction agent itself, currently Phase 6) and here
  (tracking this sub-project). They're intentionally separate — this is a
  distinct effort with its own phases and its own DoD, not an extension of
  the root project's phase list.

## 4. Decision Log

**ADR-001 — Placement: `Watchstander/retrieval/`, not `cosmo_core`.**
(2026-08-04) `cosmo_core` is private, family-agent-only (Phoebe/Gwen/Magnus),
currently idle, and explicitly out of scope for this project — no RAG work
for any existing bot, no cross-pollination. Watchstander is the only real
consumer right now: it's public, active, and it's the artifact the target
audience (Neil, and by extension Google) is already looking at. Building a
shared/reusable abstraction before a second real consumer exists would be
premature abstraction. If a second real consumer shows up later, extract
then, not now.

**ADR-002 — Five separate modules, not one script.** (2026-08-04)
`chunker.py` / `embedder.py` / `vector_store.py` / `retriever.py` /
`citation_formatter.py` are split along the same lines a real RAG pipeline
splits along (chunk -> embed -> store -> retrieve -> present), not merged
into one file. This isn't premature abstraction — no shared interface is
being designed for a second consumer that doesn't exist — it's just not
writing spaghetti. It keeps a future extraction (if one is ever warranted)
cheap without doing any design-for-reuse work now.

**ADR-003 — Not wired into `agent_core`; edge-first constraint doesn't apply
here (yet).** (2026-08-04) `agent_core/retrieval.py` explicitly rejected
ChromaDB + a sentence-transformer embedding model in favor of hand-rolled
TF-IDF, on the record, because Watchstander's live graph is edge-first and
must keep running with zero network access — a runtime model download is
exactly the dependency that constraint rules out. This project's Phase 1
plan is `sentence-transformers` + Chroma, which is precisely that dependency.
That's fine as long as `retrieval/` stays a standalone harness never imported
by `agent_core`. It stops being fine the moment anyone wires this into the
live deconfliction graph — at that point the edge-first constraint has to be
either satisfied (e.g. a pre-downloaded/bundled model, no runtime fetch) or
explicitly re-litigated, not silently ignored. Flagging this now, at Phase 0,
so it can't be discovered the hard way at integration time.

**ADR-004 — `pyproject.toml` `packages.find` includes `retrieval*` from
Phase 0, not added reactively.** (2026-08-04) The repo's own MIGRATION.md
(root, Phase 6) documents CI going red on every push because `eval/` wasn't
in `packages.find` — it worked locally only because local runs happened to
use `python -m pytest` (which prepends cwd to `sys.path`), while CI's
`pytest` console script doesn't. Same failure mode would hit `retrieval/`
identically. Fixed proactively in the same commit as the Phase 0 skeleton
rather than waiting for CI to prove it.

## 5. Known debt / open questions

- Whether the NAVSEA 8010 source text for chunking should be re-derived from
  `case_data/navsea_8010_psns_v2014.json` (already-extracted ruleset JSON,
  possibly too structured/lossy for chunking) or pulled fresh from the
  original manual — undecided, punted to Phase 1.
- No corpus size/scale assumptions have been tested yet; Phase 1's DoD is
  "returns the correct chunk," not "performs well at scale" — that's
  implicitly Phase 2's hybrid-retrieval eval-set territory.
