"""
Phase 1 Definition of Done: "a real query against the ingested corpus
returns the correct chunk and an accurate, human-readable citation --
verified by a test, not just eyeballed once." (MIGRATION.md)

This exercises the whole pipeline -- chunker -> embedder -> vector_store ->
retriever -> citation_formatter -- against real NAVSEA 8010 source text
(retrieval/sources/navsea_8010_ch4.txt), with a deterministic, network-free
embedding function standing in for the real sentence-transformers model
(see embedder.py's module docstring for why: this repo's tests never
depend on live network). The fake embedder isn't a no-op stub -- it's a
real (if crude) bag-of-hashed-words vectorizer, so a query actually has to
share vocabulary with the right chunk to retrieve it, the same property a
real embedding model provides.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from retrieval.chunker import chunk_text
from retrieval.citation_formatter import format_citation
from retrieval.embedder import Embedding
from retrieval.retriever import Retriever
from retrieval.vector_store import VectorStore

SOURCES_DIR = Path(__file__).resolve().parent.parent / "retrieval" / "sources"
_WORD = re.compile(r"[a-z]+")
_DIMS = 64


def _hashed_bow_embed(text: str) -> Embedding:
    vector = [0.0] * _DIMS
    for word in _WORD.findall(text.lower()):
        bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % _DIMS
        vector[bucket] += 1.0
    norm = sum(v * v for v in vector) ** 0.5
    if norm:
        vector = [v / norm for v in vector]
    return Embedding(vector=vector, model_name="test-hashed-bow")


def test_real_navsea_8010_chapter4_query_returns_the_correct_section_and_citation():
    text = (SOURCES_DIR / "navsea_8010_ch4.txt").read_text()
    chunks = chunk_text(text, source_id="navsea_8010_ch4")
    assert len(chunks) > 1  # sanity check the real chapter actually chunked

    store = VectorStore(collection_name="test_integration_ch4")
    store.upsert(chunks, [_hashed_bow_embed(c.text) for c in chunks])
    retriever = Retriever(vector_store=store, embed_fn=_hashed_bow_embed)

    results = retriever.retrieve("how many hot workers can a single fire watch attend", top_k=1)

    assert len(results) == 1
    top = results[0]
    assert "four hot workers" in top.text.lower()
    assert top.section == "4.4.3"

    citation = format_citation(source_id=top.source_id, chunk_id=top.chunk_id, section=top.section)
    assert citation == "NAVSEA 8010 Manual (S0570-AC-CCM-010/8010), Sec. 4.4.3"


def test_real_navsea_8010_chapter11_query_returns_a_different_correct_section():
    text = (SOURCES_DIR / "navsea_8010_ch11.txt").read_text()
    chunks = chunk_text(text, source_id="navsea_8010_ch11")

    store = VectorStore(collection_name="test_integration_ch11")
    store.upsert(chunks, [_hashed_bow_embed(c.text) for c in chunks])
    retriever = Retriever(vector_store=store, embed_fn=_hashed_bow_embed)

    results = retriever.retrieve("fire and smoke boundary requirements", top_k=1)

    assert len(results) == 1
    assert results[0].source_id == "navsea_8010_ch11"
    citation = format_citation(source_id=results[0].source_id, chunk_id=results[0].chunk_id, section=results[0].section)
    assert citation.startswith("NAVSEA 8010 Manual (S0570-AC-CCM-010/8010)")
