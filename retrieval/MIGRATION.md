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

- [ ] Ingest the Watchstander corpus: NAVSEA 8010 Manual — original manual
      text, Chapters 4 ("Hot Work and Fire Watch") and 11 ("Fire and Smoke
      Boundaries"), pulled fresh from the source PDF, not the pre-extracted
      `case_data/navsea_8010_psns_v2014.json` summaries (decided 2026-08-08,
      see ARCHITECTURE.md ADR-005) — plus OSHA CFR 1915 excerpts and
      `case_data/cases_v1.json`.
- [ ] `chunker.py`: real sentence/paragraph-aware chunking (not a blind
      character-count cut).
- [ ] `embedder.py`: wire to `sentence-transformers` (e.g.
      `all-MiniLM-L6-v2`).
- [ ] `vector_store.py`: wire to Chroma (local, persistent collection).
- [ ] `retriever.py`: real `retrieve()` — embed query, hit the vector store,
      return top-k `RetrievalResult`s.
- [ ] `citation_formatter.py`: real `format_citation()` — resolve chunk
      provenance to a human-readable citation (document title +
      section/chapter, not just a raw chunk_id).
- [ ] Add `retrieval` optional-dependency group to `pyproject.toml`
      (`sentence-transformers`, `chromadb`) once these are actually used —
      don't add unused deps in Phase 0.
- [ ] Tests replace the Phase 0 `NotImplementedError` assertions with real
      behavior assertions.
- [ ] `pytest -v` still green.

**Definition of done:** A real query against the ingested corpus returns the
correct chunk and an accurate, human-readable citation — verified by a test,
not just eyeballed once.

---

## Phase 2 — Hybrid retrieval

- [ ] BM25 keyword search alongside the existing vector search.
- [ ] Reranking step over the combined candidate set.
- [ ] Context compression before results are returned.
- [ ] Small eval set (a handful of known query -> expected-chunk pairs, in
      the same checked-in-baseline spirit as `eval/` at the repo root).

**Definition of done:** Hybrid retrieval measurably beats vector-only on the
eval set.

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
