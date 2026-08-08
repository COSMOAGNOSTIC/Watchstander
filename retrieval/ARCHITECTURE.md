# ARCHITECTURE — Grounding Retrieval Harness

Living, present-tense description of what `retrieval/` *is* right now. If
this doc and the code ever disagree, the doc is the bug.

## 1. What this is

A RAG (retrieval-augmented generation) skills-building project: a retrieval
harness that applies semantic search + citation grounding to the
Watchstander regulatory corpus (NAVSEA 8010 Manual — original manual text,
Chapters 4 and 11, not the pre-extracted `case_data/navsea_8010_psns_v2014.json`
summaries, see ADR-005 — plus OSHA CFR 1915 excerpts and `case_data/`). It
exists to close specific platform gaps — RAG mechanics, vector databases,
AWS SageMaker, Databricks — surfaced by a real job posting. See PASSDOWN.md
for the full origin story.

## 2. Current structure (Phase 1)

```
retrieval/
  __init__.py            package docstring, disambiguation note
  chunker.py               Chunk dataclass, chunk_text() -- real sentence-boundary
                            chunking, carries a NAVSEA-style section number forward
                            across continuation chunks (see ADR-006)
  embedder.py               Embedding dataclass, embed_text()/embed_chunks() --
                            real sentence-transformers wiring (all-MiniLM-L6-v2)
  vector_store.py           VectorStoreResult dataclass, VectorStore class --
                            real Chroma wiring (in-memory ephemeral by default,
                            persistent when given a directory)
  retriever.py               RetrievalResult dataclass, Retriever class -- real
                            retrieve(), embed_fn injectable for testing
  citation_formatter.py      format_citation() -- real, SOURCE_TITLES registry
  ingest.py                  corpus ingestion: chunk + embed + upsert real
                            source documents into a persistent collection
  sources/
    navsea_8010_ch4.txt      original manual text, Chapter 4 (see ADR-005)
    navsea_8010_ch11.txt     original manual text, Chapter 11
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
  test_retrieval_ingest.py
  test_retrieval_integration.py   full pipeline against real 8010 source text
```

Corpus as of Phase 1: NAVSEA 8010 Manual Chapters 4 and 11 (original text,
per ADR-005) and `case_data/cases_v1.json` (one chunk per sourced case, not
sentence-chunked -- see `ingest.py`). OSHA CFR 1915 excerpts are still not
sourced -- open item, not stubbed in with placeholder text (MIGRATION.md).

Data flow (live now, not just planned): raw corpus text -> `chunker.chunk_text()`
-> `Chunk`s -> `embedder.embed_chunks()` -> `Embedding`s ->
`vector_store.VectorStore.upsert()` (`ingest.py` wires this end-to-end).
Query time: query string -> `embedder.embed_text()` (or an injected `embed_fn`)
-> `vector_store.VectorStore.query()` -> `retriever.Retriever.retrieve()` (owns
strategy: top-k now, hybrid+rerank in Phase 2) -> `RetrievalResult`s ->
`citation_formatter.format_citation()` for display.

No real embedding model or corpus index is exercised by the test suite --
`embedder._load_model()` requires live network on first use to download
`all-MiniLM-L6-v2`, which this repo's tests never depend on (same
philosophy as `agent_core/reasoning.py`'s `ANTHROPIC_API_KEY`-gated
deterministic fallback). Tests inject a deterministic, network-free
embedding function instead -- see `test_retrieval_integration.py`'s
hashed-bag-of-words fake, which is word-overlap-sensitive enough to prove
the pipeline's wiring is actually correct, not just that it doesn't crash.
The real model path exists and works (verified by hand outside CI/tests, and
via `python -m retrieval.ingest`) but running it for real is a manual step,
not an automatic one.

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

**ADR-005 — NAVSEA 8010 chunking source: pull the original manual text
fresh, not the already-extracted `case_data/navsea_8010_psns_v2014.json`.**
(2026-08-08, decided by Donnie) The alternative — chunking the existing
ruleset JSON — was faster (no new sourcing/extraction pass needed) but a
poor fit for what this project actually exists to prove: that JSON is a
handful of short structured summaries per section, already flagged
`verified: false` because it was never confirmed against the primary PDF
text, and chunking short summaries doesn't meaningfully exercise
sentence-aware chunking, embedding, or retrieval the way real document prose
does. Phase 1's own Definition of Done — "a real query against the ingested
corpus returns the correct chunk and an accurate, human-readable citation"
— is better served by ingesting actual regulatory prose. Chosen deliberately
over the faster path: this project's stated purpose is closing real RAG
skill gaps, and doing the extraction-and-wiring work now, on a small
corpus, while the stakes are low, is itself the point — not overhead to be
minimized. Source confirmed public domain (NAVSEA S0570-AC-CCM-010/8010,
Distribution Statement A, hosted at NAVSEA's own FOIA reading room — same
source `case_data/navsea_8010_psns_v2014.json` was originally extracted
from), so there's no access blocker either way; this was purely a
which-text-to-chunk decision. Scoped to Chapters 4 ("Hot Work and Fire
Watch") and 11 ("Fire and Smoke Boundaries") — the sections already
identified as relevant in `claude/watchstander-adept-reconciliation-plan.md`
— not the full manual. Does not affect `agent_core/procedural_lookup.py`,
which keeps using the compact JSON summaries as-is; that module is a
separate, deliberately conservative consumer of the same source document,
not something this decision touches. This resolves the open question below
for 8010 specifically; OSHA CFR 1915 excerpts and `case_data/cases_v1.json`
(Phase 1's other two planned corpus inputs) don't have the same
already-extracted-JSON-vs-original-text fork, since no pre-extracted
structured summary exists for OSHA CFR 1915 the way it does for 8010, and
`cases_v1.json`'s case summaries are closer to prose than 8010's ruleset
entries are — so no general policy call was needed here, just this one.

**ADR-006 — Section citation carries forward across continuation chunks;
CI installs the `retrieval` extra.** (2026-08-08) Two real findings from
Phase 1's own test suite, both fixed the same pass rather than left open:

1. `chunker.chunk_text()` originally tagged a chunk's `section` by
   searching only that chunk's own text for a NAVSEA-style header (e.g.
   "4.4.3"). A chunk that continues a section — falls after the header
   sentence, so contains no header text of its own — came back with
   `section: None`, silently losing its citation even though it's just as
   much a part of that section as the chunk before it.
   `test_retrieval_integration.py`'s real-Chapter-4 query caught this: the
   retrieved chunk was the right one (contains "No more than four hot
   workers"), but its citation would have been wrong. Fixed by carrying the
   most recently seen section number forward across chunks within a
   document, updating only when a new header actually appears —
   `test_chunk_text_carries_section_forward_into_continuation_chunks`
   guards this permanently.
2. `pyproject.toml` gained a `retrieval` optional-dependency group
   (`sentence-transformers`, `chromadb`) for this phase, but
   `.github/workflows/tests.yml` still only installed `.[dev]`. This is the
   exact failure mode this file's own AOSE.md already documents happening
   once with `eval/` (local runs used `python -m pytest`, which masks
   missing-package installs that CI's bare `pytest` doesn't) — caught here
   by actually installing into a fresh venv and running bare `pytest`
   before pushing, not by trusting that "tests pass locally" meant
   anything about CI. Fixed by adding `retrieval` to the CI install step.

## 5. Known debt / open questions

- No corpus size/scale assumptions have been tested yet; Phase 1's DoD is
  "returns the correct chunk," not "performs well at scale" — that's
  implicitly Phase 2's hybrid-retrieval eval-set territory.
- `chunker.py`'s overlap between consecutive chunks is opportunistic, not
  guaranteed: when a chunk consists of a single sentence with no earlier
  sentence of its own to back into, the next chunk starts immediately after
  it with no overlap (see `test_chunk_text_covers_the_whole_document_without_gaps`).
  No text is ever lost — chunks still abut exactly — this only means the
  "same fact findable from either side of a chunk boundary" property Phase 1
  overlap exists for doesn't hold at every boundary, just most of them.
  Lower severity: hasn't caused an incorrect retrieval yet, and fixing it
  properly means letting overlap reach back into a *previous* chunk's
  sentences rather than just the current one, which needs a real design
  pass, not a quick patch.
- OSHA CFR 1915 excerpts (the third planned Phase 1 corpus source) are not
  sourced yet — same PDF-extraction effort ADR-005 describes for NAVSEA
  8010 hasn't been run against 29 CFR 1915. Not blocking Phase 1's DoD
  (already met against the 8010 + cases_v1 corpus), but the corpus is
  smaller than originally planned until this lands.
