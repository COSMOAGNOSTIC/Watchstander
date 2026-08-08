from retrieval.chunker import Chunk
from retrieval.embedder import Embedding
from retrieval.vector_store import VectorStore, VectorStoreResult


def test_vector_store_result_is_a_real_dataclass_with_expected_fields():
    r = VectorStoreResult(chunk_id="c1", text="hi", source_id="s1", score=0.9)
    assert r.chunk_id == "c1"
    assert r.text == "hi"
    assert r.source_id == "s1"
    assert r.score == 0.9
    assert r.section is None


def _chunk(chunk_id, text, section=None):
    return Chunk(text=text, source_id="s", chunk_id=chunk_id, start_char=0, end_char=len(text), section=section)


def test_query_on_empty_store_returns_empty_list():
    store = VectorStore(collection_name="test_empty")
    assert store.query(query_embedding=[1.0, 0.0], top_k=3) == []


def test_upsert_then_query_finds_the_closest_match():
    """In-memory ephemeral store (no persist_directory) -- never touches
    disk, so this is safe to run in any order alongside other tests."""
    store = VectorStore(collection_name="test_closest")
    chunks = [
        _chunk("s#000", "fire watch capacity rule", section="4.4.3"),
        _chunk("s#001", "completely unrelated bulkhead paint spec"),
    ]
    embeddings = [
        Embedding(vector=[1.0, 0.0], model_name="fake"),
        Embedding(vector=[0.0, 1.0], model_name="fake"),
    ]
    store.upsert(chunks, embeddings)

    results = store.query(query_embedding=[1.0, 0.0], top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "s#000"
    assert results[0].source_id == "s"
    assert results[0].section == "4.4.3"
    assert results[0].score > 0.9  # cosine similarity to an identical vector


def test_upsert_mismatched_lengths_raises():
    store = VectorStore(collection_name="test_mismatch")
    try:
        store.upsert([_chunk("s#000", "x")], [])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_upsert_is_idempotent_on_repeated_calls_with_same_ids():
    """Re-ingesting the same chunk_id overwrites rather than duplicating."""
    store = VectorStore(collection_name="test_idempotent")
    chunk = _chunk("s#000", "original text")
    embedding = Embedding(vector=[1.0, 0.0], model_name="fake")
    store.upsert([chunk], [embedding])
    updated_chunk = _chunk("s#000", "updated text")
    store.upsert([updated_chunk], [embedding])

    results = store.query(query_embedding=[1.0, 0.0], top_k=5)

    assert len(results) == 1
    assert results[0].text == "updated text"


def test_get_all_on_empty_store_returns_empty_list():
    store = VectorStore(collection_name="test_get_all_empty")
    assert store.get_all() == []


def test_get_all_returns_every_stored_chunk_as_plain_dicts():
    store = VectorStore(collection_name="test_get_all")
    chunks = [
        _chunk("s#000", "fire watch capacity rule", section="4.4.3"),
        _chunk("s#001", "completely unrelated bulkhead paint spec"),
    ]
    embeddings = [
        Embedding(vector=[1.0, 0.0], model_name="fake"),
        Embedding(vector=[0.0, 1.0], model_name="fake"),
    ]
    store.upsert(chunks, embeddings)

    all_chunks = store.get_all()

    assert len(all_chunks) == 2
    by_id = {c["chunk_id"]: c for c in all_chunks}
    assert by_id["s#000"]["text"] == "fire watch capacity rule"
    assert by_id["s#000"]["source_id"] == "s"
    assert by_id["s#000"]["section"] == "4.4.3"
    assert by_id["s#001"]["section"] is None
