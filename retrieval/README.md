# Grounding Retrieval Harness

A RAG (retrieval-augmented generation) skills-building sub-project inside
the [Watchstander](../README.md) repo. Applies semantic search + citation
grounding to the Watchstander regulatory corpus (NAVSEA 8010 Manual, OSHA
CFR 1915 excerpts, `case_data/`).

Not to be confused with `agent_core/retrieval.py`, an unrelated, pre-existing
TF-IDF case-lookup module used by the live safety agent — see
[ARCHITECTURE.md](ARCHITECTURE.md) §3 for the disambiguation and why the name
collision isn't a runtime problem.

This package is a standalone teaching harness. It is **not** wired into
Watchstander's live deconfliction graph — see ARCHITECTURE.md ADR-003 for
why that matters (Watchstander's live graph is edge-first/zero-network;
this harness's planned stack, `sentence-transformers` + Chroma, is not).

## Status

Phase 0 (skeleton) complete. See [MIGRATION.md](MIGRATION.md) for the full
phased plan and current status table.

## Project Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — component map, design principles,
  decision log
- [MIGRATION.md](MIGRATION.md) — phased build plan with a definition of done
  per phase
- [PASSDOWN.md](PASSDOWN.md) — session-to-session continuity notes
- [AOSE.md](AOSE.md) — adversarial review rounds run against this
  sub-project

## Structure

```
retrieval/
  chunker.py               source text -> overlapping Chunks
  embedder.py               Chunk / query text -> vector Embedding
  vector_store.py           Embedding storage + similarity search
  retriever.py               retrieval strategy (top-k now, hybrid in Phase 2)
  citation_formatter.py     chunk provenance -> human-readable citation
```

## Testing

From the repo root:

```bash
pytest tests/test_retrieval_*.py -v
```
