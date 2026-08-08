"""
Phase 1: real vector storage, wired to Chroma.

Thin wrapper around a Chroma collection -- upsert and similarity-search
only. Kept separate from retriever.py so retriever.py stays the place that
owns *retrieval strategy* (top-k, filtering, hybrid search in Phase 2),
while this module only owns *storage*.

With no `persist_directory`, this uses an in-memory ephemeral Chroma
client -- what the test suite uses, so tests never touch disk or depend on
run order. Passing a `persist_directory` (see retrieval/ingest.py) gets a
real on-disk collection that survives across processes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from retrieval.chunker import Chunk
    from retrieval.embedder import Embedding


@dataclass(frozen=True)
class VectorStoreResult:
    chunk_id: str
    text: str
    source_id: str
    score: float
    section: str | None = None


class VectorStore:
    """Phase 1 -- backed by a real Chroma collection."""

    def __init__(self, collection_name: str = "watchstander_corpus", persist_directory: str | None = None) -> None:
        import chromadb

        self.collection_name = collection_name
        self.persist_directory = persist_directory
        client = (
            chromadb.PersistentClient(path=persist_directory)
            if persist_directory
            else chromadb.Client()
        )
        # Cosine distance so `score = 1 - distance` reads naturally as a
        # similarity (1.0 = identical direction), matching the normalized
        # embeddings embedder.py produces.
        self._collection = client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, chunks: list["Chunk"], embeddings: list["Embedding"]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) must be the same length"
            )
        if not chunks:
            return
        self._collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=[e.vector for e in embeddings],
            documents=[c.text for c in chunks],
            metadatas=[
                {"source_id": c.source_id, "section": c.section or ""} for c in chunks
            ],
        )

    def query(self, query_embedding: list[float], top_k: int = 5) -> list[VectorStoreResult]:
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
        )
        out: list[VectorStoreResult] = []
        for chunk_id, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            out.append(
                VectorStoreResult(
                    chunk_id=chunk_id,
                    text=text,
                    source_id=metadata.get("source_id", ""),
                    score=1.0 - distance,
                    section=metadata.get("section") or None,
                )
            )
        return out

    def get_all(self) -> list[dict]:
        """Return every stored chunk as {"chunk_id", "text", "source_id",
        "section"}. Added for Phase 2's BM25Index.from_vector_store() --
        Chroma is the one place chunk data actually lives, so the keyword
        index is built from a snapshot of it rather than a second copy of
        the corpus living in retrieval/ingest.py or anywhere else."""
        if self._collection.count() == 0:
            return []
        result = self._collection.get()
        return [
            {
                "chunk_id": chunk_id,
                "text": text,
                "source_id": metadata.get("source_id", ""),
                "section": metadata.get("section") or None,
            }
            for chunk_id, text, metadata in zip(result["ids"], result["documents"], result["metadatas"])
        ]
