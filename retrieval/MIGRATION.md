# MIGRATION — Grounding Retrieval Harness

Phased build plan for `retrieval/`. One phase per sitting where practical;
don't start a phase whose predecessor's DoD isn't met. This is the road, not
the destination — see ARCHITECTURE.md for what the system *is* right now.

---

## Phase 0 — Skeleton

- [x] `retrieval/__init__.py` — package docstring, disambiguates this
      package from the unrelated `agent_core/retrieval.py`.
- [x] `retrieval/chunker.py` — `Chunk` dataclass + `chunk_text()` boundary.
- [x] `retrieval/embedder.py` — `Embedding` dataclass + `embed_text()` /
      `embed_chunks()` boundaries.
- [x] `retrieval/vector_store.py` — `VectorStoreResult` dataclass +
      `VectorStore` class (`upsert()` / `query()` boundaries).
- [x] `retrieval/retriever.py` — `RetrievalResult` dataclass + `Retriever`
      class (`retrieve()` boundary).
- [x] `retrieval/citation_formatter.py` — `format_citation()` boundary.
- [x] Tests for every module above (`tests/test_retrieval_*.py`) — assert
      the data models are real and the function/method boundaries exist and
      raise `NotImplementedError` with a Phase 1 pointer, not that they do
      anything real yet.
- [x] `pyproject.toml` `packages.find` updated to include `retrieval*`, so
      the package resolves under CI's install path from day one (see
      ARCHITECTURE.md ADR-004 — this repo already hit the un-included-package
      failure mode once, with `eval/`, and there's no reason to repeat it).
- [x] `pytest -v` green, `import retrieval` (and every submodule) clean.
- [x] Four-doc scaffold in place (this file, ARCHITECTURE.md, PASSDOWN.md,
      AOSE.md) plus `retrieval/README.md`.

**Definition of done:** All five modules exist with real data models and a
defined function/method boundary per Phase 1 responsibility; no real
retrieval logic yet (by design — that's Phase 1); tests exist and pass;
imports cleanly, including under a CI-style install.

---

## Phase 1 — Local RAG proof

- [x] Ingest the Watchstander corpus: NAVSEA 8010 Manual — original manual
      text, Chapters 4 ("Hot Work and Fire Watch") and 11 ("Fire and Smoke
      Boundaries"), pulled fresh from the source PDF (see ARCHITECTURE.md
      ADR-005); 29 CFR 1915 Subpart B — original CFR text, sections
      1915.11–1915.16, pulled live via browser extraction from OSHA.gov
      (ARCHITECTURE.md ADR-007); plus `case_data/cases_v1.json` (one chunk
      per sourced case). Other 1915 subparts (D, E, F, G, H) not yet
      sourced — open item, not blocking (ARCHITECTURE.md §5).
- [x] `chunker.py`: real sentence-boundary chunking (never splits a
      sentence across chunks; never drops an oversized sentence), tags
      each chunk with the NAVSEA-style section number in force, carried
      forward across continuation chunks that don't repeat the header
      (ADR-006 — a real bug the integration test caught and fixed this
      pass).
- [x] `embedder.py`: wired to `sentence-transformers`
      (`all-MiniLM-L6-v2`), lazy-loaded and cached. Real model download
      needs live network on first use — not exercised by the test suite,
      which injects a deterministic offline `embed_fn` instead.
- [x] `vector_store.py`: wired to Chroma — in-memory ephemeral by default
      (what tests use), persistent when given a directory
      (`retrieval/ingest.py`'s default: `retrieval/.chroma_store/`,
      gitignored).
- [x] `retriever.py`: real `retrieve()` — embeds the query (via an
      injectable `embed_fn`, defaulting to `embedder.embed_text`), queries
      the vector store, returns top-k `RetrievalResult`s.
- [x] `citation_formatter.py`: real `format_citation()` — `SOURCE_TITLES`
      registry resolves `source_id` to a document title; combined with
      `section` when present ("NAVSEA 8010 Manual ..., Sec. 4.4.3"), falls
      back to `(chunk_id)` when it isn't (e.g. non-numbered sources),
      falls back to the raw `source_id` for anything unregistered rather
      than guessing a title.
- [x] `retrieval` optional-dependency group added to `pyproject.toml`
      (`sentence-transformers`, `chromadb`). CI's install step
      (`.github/workflows/tests.yml`) updated to include it — verified by
      installing into a genuinely fresh venv and running bare `pytest`
      (not `python -m pytest`) before pushing, the same discipline root
      AOSE.md already argues for after the `eval/` package gap.
- [x] Tests replace the Phase 0 `NotImplementedError` assertions with real
      behavior assertions (`test_retrieval_chunker.py`,
      `test_retrieval_embedder.py`, `test_retrieval_vector_store.py`,
      `test_retrieval_retriever.py`, `test_retrieval_citation_formatter.py`),
      plus two new files: `test_retrieval_ingest.py` (ingest.py's own
      chunking/upsert logic) and `test_retrieval_integration.py` (the full
      pipeline against real Chapter 4/11 source text — this is what
      satisfies the Definition of Done below).
- [x] `pytest -v` green — 106/106 (101 after the initial Phase 1 build,
      +5 for OSHA Subpart B's ingestion/parsing tests and integration
      proof, ADR-007), including under a fresh-venv CI-equivalent bare
      `pytest` invocation with `.[dev,retrieval]` installed.

**Definition of done:** A real query against the ingested corpus returns the
correct chunk and an accurate, human-readable citation — verified by a test,
not just eyeballed once. Met: `test_retrieval_integration.py` chunks the real
Chapter 4 source text, retrieves against the query "how many hot workers can
a single fire watch attend," gets back the chunk containing "No more than
four hot workers shall be attended by a single fire watch," tagged
`section == "4.4.3"`, and formats it as "NAVSEA 8010 Manual
(S0570-AC-CCM-010/8010), Sec. 4.4.3."

---

## Phase 2 — Hybrid retrieval

- [x] BM25 keyword search alongside the existing vector search.
      `retrieval/bm25_index.py` — `BM25Index`, pure-Python `rank_bm25`
      (`BM25Okapi`), built via `BM25Index.from_vector_store()` from
      `VectorStore.get_all()` (new method). See ARCHITECTURE.md ADR-008.
- [x] Reranking step over the combined candidate set. Reciprocal rank
      fusion (RRF, `k=60`) in `retriever.py`'s hybrid path — genuine
      fusion of two independently-scaled rankings, not concatenate-and-dedupe.
- [x] Context compression before results are returned. `retrieval/compression.py`
      — sentence-level term-overlap extraction (`compress()`), not LLM
      summarization (edge-first per ADR-003).
- [x] Small eval set (a handful of known query -> expected-chunk pairs, in
      the same checked-in-baseline spirit as `eval/` at the repo root).
      `retrieval/eval/` — 11 hand-verified scenarios across all three
      corpus sources, `run_eval.py`, checked-in `baseline.json`,
      `tests/test_retrieval_eval_harness.py` regression guard.

**Definition of done:** Hybrid retrieval measurably beats vector-only on the
eval set. **Met** — 82% vs. 73% top-1 accuracy (9/11 vs. 8/11 of 11
scenarios). Required fixing a real RRF pool-size bug first (initial result
was a 73%/73% tie, not a win — see ARCHITECTURE.md ADR-008 for the full
root-cause). Two scenarios still fail in both arms for an unrelated,
pre-existing chunking-granularity reason (documented as known debt in
ARCHITECTURE.md §5, not blocking this DoD since it affects both arms
identically).

---

## Phase 3 — AWS SageMaker Studio Lab exposure

- [ ] Port the embedding step to run inside SageMaker Studio Lab (free
      tier).
- [ ] Document the port (what changed, what didn't, what SageMaker-specific
      concepts came up) in ARCHITECTURE.md.

**Definition of done:** One full pipeline pass through SageMaker, documented.

---

## Phase 4 — Databricks Community Edition exposure

- [ ] Corpus into a Delta Lake table on Databricks Community Edition.
- [ ] Round-trip: corpus in, chunks/embeddings out, usable by the rest of
      the pipeline.
- [ ] Governance concepts encountered (access control, lineage, etc.) noted
      in ARCHITECTURE.md — this phase is explicitly about the concepts, not
      just getting a pipeline to run.

**Definition of done:** Round-trip complete, governance concepts documented.

---

## Phase 5 — Certs

- [ ] AWS Certified AI Practitioner
- [ ] AWS Certified Machine Learning Engineer – Associate
- [ ] Stretch: AWS Certified Generative AI Developer – Professional (best
      match to this actual work; the old ML-Specialty cert is retired, last
      exam was March 31 2026)

**Definition of done:** Certs scheduled/passed as far as time allows — this
phase is explicitly opportunistic, not blocking anything downstream.

---

## Phase status

| Phase | Status | Date done |
|---|---|---|
| 0 — Skeleton | ✅ | 2026-08-04 |
| 1 — Local RAG proof | ⬜ | |
| 2 — Hybrid retrieval | ⬜ | |
| 3 — AWS SageMaker exposure | ⬜ | |
| 4 — Databricks exposure | ⬜ | |
| 5 — Certs | ⬜ | |
