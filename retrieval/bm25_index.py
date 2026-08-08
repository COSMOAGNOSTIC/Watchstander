"""
Phase 2: BM25 keyword index, run alongside vector search for hybrid
retrieval.

Pure-Python term-frequency scoring (`rank_bm25`'s Okapi BM25) -- no model
download, no network, at index-build time or query time. That makes it
directly, honestly testable, unlike embedder.py's real model path (which
this repo's tests deliberately never exercise -- see that module's
docstring): there's no fake/injected substitute here because none is
needed.

Built from whatever's already in a VectorStore (`from_vector_store`) rather
than keeping a second copy of the corpus anywhere -- Chroma is the one
place source-of-truth chunk data lives; this index is a derived view of it,
rebuilt on demand, not a second store to keep in sync.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from retrieval.vector_store import VectorStore

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class BM25Result:
    chunk_id: str
    text: str
    source_id: str
    score: float
    section: str | None = None


class BM25Index:
    """In-memory BM25 index over a fixed snapshot of chunks. No incremental
    upsert -- rebuild via `from_vector_store` after ingestion changes; fine
    at this corpus's size (Known Debt if that stops being true)."""

    def __init__(self, chunks: list[dict]) -> None:
        from rank_bm25 import BM25Okapi

        self._chunks = list(chunks)
        tokenized = [_tokenize(c["text"]) for c in self._chunks]
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    @classmethod
    def from_vector_store(cls, vector_store: "VectorStore") -> "BM25Index":
        return cls(vector_store.get_all())

    def query(self, query: str, top_k: int = 5) -> list[BM25Result]:
        if self._bm25 is None or not query or not query.strip():
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for i in ranked:
            if scores[i] <= 0:
                break  # rest of `ranked` only gets worse; nothing left is a real match
            chunk = self._chunks[i]
            results.append(
                BM25Result(
                    chunk_id=chunk["chunk_id"],
                    text=chunk["text"],
                    source_id=chunk["source_id"],
                    score=float(scores[i]),
                    section=chunk["section"],
                )
            )
            if len(results) >= top_k:
                break
        return results
