"""
Covers ingest.py's own logic (chapter source_id separation, case-file
chunking) with an injected fake embedder -- never the real
sentence-transformers model, same reasoning as test_retrieval_integration.py.
"""

from __future__ import annotations

import json

from retrieval import ingest
from retrieval.embedder import Embedding
from retrieval.vector_store import VectorStore


def _fake_embed_chunks(chunks):
    return [Embedding(vector=[float(len(c.text)), 0.0], model_name="fake") for c in chunks]


def test_ingest_text_source_returns_zero_for_empty_text(monkeypatch):
    monkeypatch.setattr(ingest, "embed_chunks", _fake_embed_chunks)
    store = VectorStore(collection_name="test_ingest_empty")
    assert ingest.ingest_text_source("", "navsea_8010_ch4", store) == 0


def test_ingest_text_source_chunks_and_upserts(monkeypatch):
    monkeypatch.setattr(ingest, "embed_chunks", _fake_embed_chunks)
    store = VectorStore(collection_name="test_ingest_text")
    count = ingest.ingest_text_source(
        "4.4.3 Limitations. No more than four hot workers shall be attended by a single fire watch.",
        "navsea_8010_ch4",
        store,
        chunk_size=1000,
    )
    assert count == 1
    results = store.query(query_embedding=[float(count), 0.0], top_k=1)
    assert results[0].source_id == "navsea_8010_ch4"
    assert results[0].section == "4.4.3"


def test_ingest_cases_produces_one_chunk_per_case(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest, "embed_chunks", _fake_embed_chunks)
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "CS-TEST-1",
                        "shipyard": "Test Yard",
                        "date": "2024-01-01",
                        "summary": "A test incident.",
                        "root_cause": "A test cause.",
                    },
                    {
                        "case_id": "CS-TEST-2",
                        "shipyard": "Test Yard 2",
                        "date": "2024-02-02",
                        "summary": "Another test incident.",
                        "root_cause": "Another test cause.",
                    },
                ]
            }
        )
    )
    store = VectorStore(collection_name="test_ingest_cases")

    count = ingest.ingest_cases(cases_path, store)

    assert count == 2
    results = store.query(query_embedding=[1.0, 0.0], top_k=5)
    ids = {r.chunk_id for r in results}
    assert ids == {"cases_v1#000", "cases_v1#001"}
    sections = {r.section for r in results}
    assert sections == {"CS-TEST-1", "CS-TEST-2"}


def test_ingest_cases_returns_zero_for_no_cases(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest, "embed_chunks", _fake_embed_chunks)
    cases_path = tmp_path / "empty_cases.json"
    cases_path.write_text(json.dumps({"cases": []}))
    store = VectorStore(collection_name="test_ingest_no_cases")

    assert ingest.ingest_cases(cases_path, store) == 0


_OSHA_FIXTURE = """=== SECTION 1915.11 ===
Scope, application and definitions applicable to this subpart.

1915.11(a)

Scope and application. This subpart applies to work in confined and enclosed spaces.

=== SECTION 1915.14 ===
Hot Work.

1915.14(a)

Hot work requiring testing by a Marine Chemist or Coast Guard authorized person. The employer shall ensure hot work is tested first.
"""


def test_parse_osha_sections_splits_on_markers():
    sections = ingest.parse_osha_sections(_OSHA_FIXTURE)
    assert set(sections) == {"1915.11", "1915.14"}
    assert "Scope and application" in sections["1915.11"]
    assert "Hot work requiring testing" in sections["1915.14"]


def test_parse_osha_sections_returns_empty_dict_for_text_with_no_markers():
    assert ingest.parse_osha_sections("just plain text, no section markers here") == {}


def test_ingest_osha_subpart_tags_every_chunk_with_its_cfr_section(monkeypatch):
    monkeypatch.setattr(ingest, "embed_chunks", _fake_embed_chunks)
    store = VectorStore(collection_name="test_ingest_osha")

    count = ingest.ingest_osha_subpart(_OSHA_FIXTURE, "osha_1915_subpart_b", store, chunk_size=1000)

    assert count == 2  # one chunk per section at this chunk_size
    results = store.query(query_embedding=[1.0, 0.0], top_k=5)
    sections = {r.section for r in results}
    assert sections == {"1915.11", "1915.14"}
    for r in results:
        assert r.source_id == "osha_1915_subpart_b"
        assert r.chunk_id.startswith(f"osha_1915_subpart_b#{r.section}-")


def test_ingest_osha_subpart_returns_zero_for_text_with_no_sections():
    store = VectorStore(collection_name="test_ingest_osha_empty")
    assert ingest.ingest_osha_subpart("no markers at all", "osha_1915_subpart_b", store) == 0
