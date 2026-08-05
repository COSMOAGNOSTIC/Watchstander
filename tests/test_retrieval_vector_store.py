import pytest

from retrieval.vector_store import VectorStore, VectorStoreResult


def test_vector_store_result_is_a_real_dataclass_with_expected_fields():
    r = VectorStoreResult(chunk_id="c1", text="hi", source_id="s1", score=0.9)
    assert r.chunk_id == "c1"
    assert r.text == "hi"
    assert r.source_id == "s1"
    assert r.score == 0.9


def test_vector_store_upsert_not_yet_implemented():
    store = VectorStore()
    with pytest.raises(NotImplementedError):
        store.upsert([], [])


def test_vector_store_query_not_yet_implemented():
    store = VectorStore()
    with pytest.raises(NotImplementedError):
        store.query(query_embedding=[0.1], top_k=3)
