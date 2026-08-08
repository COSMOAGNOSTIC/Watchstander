from retrieval.chunker import Chunk
from retrieval.embedder import Embedding
from retrieval.retriever import RetrievalResult, Retriever
from retrieval.vector_store import VectorStore


def test_retrieval_result_is_a_real_dataclass_with_expected_fields():
    r = RetrievalResult(chunk_id="c1", text="hi", source_id="s1", score=0.9)
    assert r.chunk_id == "c1"
    assert r.text == "hi"
    assert r.source_id == "s1"
    assert r.score == 0.9
    assert r.section is None


def _fake_embed(text: str) -> Embedding:
    """Deterministic, network-free stand-in for embedder.embed_text --
    injected via Retriever's embed_fn parameter, exactly the seam it exists
    for."""
    return Embedding(vector=[1.0, 0.0] if "fire watch" in text else [0.0, 1.0], model_name="fake")


def test_retriever_retrieve_on_empty_store_returns_empty_list():
    retriever = Retriever(vector_store=VectorStore(collection_name="test_retriever_empty"), embed_fn=_fake_embed)
    assert retriever.retrieve("fire watch capacity") == []


def test_retriever_retrieve_returns_the_right_chunk_for_the_query():
    store = VectorStore(collection_name="test_retriever_real")
    chunks = [
        Chunk(text="4.4.3 says four hot workers max.", source_id="navsea_8010_ch4", chunk_id="navsea_8010_ch4#000", start_char=0, end_char=10, section="4.4.3"),
        Chunk(text="unrelated bulkhead paint spec.", source_id="navsea_8010_ch4", chunk_id="navsea_8010_ch4#001", start_char=10, end_char=20),
    ]
    store.upsert(
        chunks,
        [
            Embedding(vector=[1.0, 0.0], model_name="fake"),
            Embedding(vector=[0.0, 1.0], model_name="fake"),
        ],
    )
    retriever = Retriever(vector_store=store, embed_fn=_fake_embed)

    results = retriever.retrieve("what is the fire watch capacity limit?", top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "navsea_8010_ch4#000"
    assert results[0].section == "4.4.3"


def test_retriever_retrieve_on_blank_query_returns_empty_list_without_embedding():
    calls = []

    def tracking_embed(text):
        calls.append(text)
        return Embedding(vector=[1.0, 0.0], model_name="fake")

    retriever = Retriever(vector_store=VectorStore(collection_name="test_retriever_blank"), embed_fn=tracking_embed)

    assert retriever.retrieve("   ") == []
    assert calls == []
