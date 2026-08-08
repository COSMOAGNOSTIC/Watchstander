"""
Phase 1: real retrieval. Phase 2: hybrid (vector + BM25) retrieval with
reciprocal-rank-fusion reranking and context compression.

Owns retrieval strategy: given a query, returns the top-k most relevant
chunks. Vector-only mode (no `bm25_index` passed) is exactly Phase 1's
behavior, unchanged -- every Phase 1 test still exercises that path as-is.
Passing a `bm25_index` opts into Phase 2 hybrid mode: vector search and
BM25 keyword search both run, their rankings are fused via reciprocal rank
fusion (RRF) -- a real reranking step over the combined candidate set, not
a synonym for "concatenate and dedupe" -- and each surviving result's text
is compressed to its most query-relevant sentence(s) (retrieval/compression.py)
before being returned. This keeps Phase 1's interface and behavior fully
backward compatible while Phase 2 is additive on top of it.

`embed_fn` is injected (defaulting to embedder.embed_text) rather than
hardcoded so tests can supply a deterministic, network-free embedding
function without monkeypatching module internals -- see
tests/test_retrieval_integration.py. `bm25_index` needs no such seam:
BM25Index has no network dependency to fake in the first place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from retrieval.compression import compress
from retrieval.embedder import Embedding, embed_text
from retrieval.vector_store import VectorStore

if TYPE_CHECKING:
    from retrieval.bm25_index import BM25Index

# Standard RRF damping constant (Cormack et al.) -- large enough that a
# single top-1 hit on one ranker doesn't completely dominate a candidate
# that both rankers rate merely "pretty good," which is the whole point of
# fusing two independent rankings instead of trusting either alone.
_RRF_K = 60


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    text: str
    source_id: str
    score: float
    section: str | None = None


def _reciprocal_rank_fusion(*rankings: list, top_k: int) -> list[tuple[object, float]]:
    """Fuse any number of ranked result lists (each already sorted
    best-first) into one ranking. A candidate's fused score is the sum of
    1/(_RRF_K + rank) across every list it appears in (rank is 0-based) --
    appearing, and appearing high, in more than one independent ranking is
    what RRF rewards; it needs neither ranking's raw scores to be on a
    comparable scale, which vector cosine-similarity and BM25 term-weight
    scores are not."""
    fused_scores: dict[str, float] = {}
    first_seen: dict[str, object] = {}
    for ranking in rankings:
        for rank, result in enumerate(ranking):
            fused_scores[result.chunk_id] = fused_scores.get(result.chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
            first_seen.setdefault(result.chunk_id, result)
    ranked_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)[:top_k]
    return [(first_seen[cid], fused_scores[cid]) for cid in ranked_ids]


class Retriever:
    """Phase 1 -- wired to embedder + vector_store. Phase 2 -- optionally
    adds BM25 hybrid search + RRF reranking + context compression on top."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embed_fn: Callable[[str], Embedding] = embed_text,
        bm25_index: "BM25Index | None" = None,
    ) -> None:
        self.vector_store = vector_store if vector_store is not None else VectorStore()
        self._embed_fn = embed_fn
        self._bm25_index = bm25_index

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        if not query or not query.strip():
            return []

        if self._bm25_index is None:
            # Phase 1 path, unchanged: no fusion, no compression.
            embedding = self._embed_fn(query)
            results = self.vector_store.query(embedding.vector, top_k=top_k)
            return [
                RetrievalResult(
                    chunk_id=r.chunk_id, text=r.text, source_id=r.source_id, score=r.score, section=r.section
                )
                for r in results
            ]

        # Phase 2 hybrid path: pull a wider candidate pool from each
        # ranker than top_k (fusion can promote a candidate that ranked,
        # say, 4th on both lists over one that ranked 1st on only one),
        # fuse via RRF, then compress each surviving result's text.
        #
        # The multiplier alone isn't enough at small top_k: top_k*3 gives a
        # pool_size of 3 when top_k=1, which is narrow enough that a
        # candidate BM25 ranks #1 but vector search doesn't surface at all
        # (or vice versa) can miss the *other* ranker's pool entirely. When
        # that happens, RRF scores both candidates as if they were tied
        # (each gets exactly 1/(_RRF_K+1) from the one ranking it appears
        # in), and the tie gets broken by dict/sort insertion order --
        # which always favors vector_results, since it's fused first in the
        # call below -- not by genuine relevance. A floor of 20 keeps the
        # pool wide enough that both rankers' real top candidates actually
        # get to compete in the fusion step instead of one silently
        # defaulting to a phantom tie-win.
        pool_size = max(top_k * 3, 20)
        embedding = self._embed_fn(query)
        vector_results = self.vector_store.query(embedding.vector, top_k=pool_size)
        bm25_results = self._bm25_index.query(query, top_k=pool_size)
        fused = _reciprocal_rank_fusion(vector_results, bm25_results, top_k=top_k)
        return [
            RetrievalResult(
                chunk_id=r.chunk_id,
                text=compress(r.text, query),
                source_id=r.source_id,
                score=score,
                section=r.section,
            )
            for r, score in fused
        ]
