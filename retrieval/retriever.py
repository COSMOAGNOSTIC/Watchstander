"""
Phase 0: skeleton.

Owns retrieval strategy: given a query, returns the top-k most relevant
chunks. Phase 1 is vector-only (via VectorStore). Phase 2 adds BM25 hybrid
search + reranking + context compression on top of this same interface, so
callers (citation_formatter, and anything that consumes this later)
shouldn't need to change shape when that lands.
"""

from __future__ import annotations

from dataclasses import dataclass

from retrieval.vector_store import VectorStore


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    text: str
    source_id: str
    score: float


class Retriever:
    """Phase 0 skeleton -- Phase 1 wires this to embedder + vector_store."""

    def __init__(self, vector_store: VectorStore | None = None) -> None:
        self.vector_store = vector_store

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        """Phase 0 skeleton -- Phase 1 wires this to embedder + vector_store."""
        raise NotImplementedError("Retriever.retrieve: real logic lands in Phase 1 -- see MIGRATION.md")
