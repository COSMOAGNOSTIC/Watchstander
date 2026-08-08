"""
Phase 1: real retrieval.

Owns retrieval strategy: given a query, returns the top-k most relevant
chunks. Phase 1 is vector-only (via VectorStore). Phase 2 adds BM25 hybrid
search + reranking + context compression on top of this same interface, so
callers (citation_formatter, and anything that consumes this later)
shouldn't need to change shape when that lands.

`embed_fn` is injected (defaulting to embedder.embed_text) rather than
hardcoded so tests can supply a deterministic, network-free embedding
function without monkeypatching module internals -- see
tests/test_retrieval_integration.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from retrieval.embedder import Embedding, embed_text
from retrieval.vector_store import VectorStore


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    text: str
    source_id: str
    score: float
    section: str | None = None


class Retriever:
    """Phase 1 -- wired to embedder + vector_store."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embed_fn: Callable[[str], Embedding] = embed_text,
    ) -> None:
        self.vector_store = vector_store if vector_store is not None else VectorStore()
        self._embed_fn = embed_fn

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        if not query or not query.strip():
            return []
        embedding = self._embed_fn(query)
        results = self.vector_store.query(embedding.vector, top_k=top_k)
        return [
            RetrievalResult(
                chunk_id=r.chunk_id,
                text=r.text,
                source_id=r.source_id,
                score=r.score,
                section=r.section,
            )
            for r in results
        ]
