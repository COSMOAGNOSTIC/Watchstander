"""
Phase 0: skeleton.

Thin wrapper around the vector database (Chroma, Phase 1) -- upsert and
similarity-search only. Kept separate from retriever.py so retriever.py
stays the place that owns *retrieval strategy* (top-k, filtering, hybrid
search in Phase 2), while this module only owns *storage*.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VectorStoreResult:
    chunk_id: str
    text: str
    source_id: str
    score: float


class VectorStore:
    """Phase 0 skeleton -- Phase 1 backs this with Chroma."""

    def __init__(self, collection_name: str = "watchstander_corpus") -> None:
        self.collection_name = collection_name

    def upsert(self, chunks: list, embeddings: list) -> None:
        """Phase 0 skeleton -- Phase 1 wires this to a Chroma collection."""
        raise NotImplementedError("VectorStore.upsert: real logic lands in Phase 1 -- see MIGRATION.md")

    def query(self, query_embedding: list[float], top_k: int = 5) -> list[VectorStoreResult]:
        """Phase 0 skeleton -- Phase 1 wires this to a Chroma collection."""
        raise NotImplementedError("VectorStore.query: real logic lands in Phase 1 -- see MIGRATION.md")
