from retrieval.bm25_index import BM25Index
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


# --- Phase 2: hybrid mode (bm25_index passed) -------------------------------


def _flat_embed(_text: str) -> Embedding:
    """Every chunk and every query embeds to the same vector -- deliberately
    useless for ranking on its own, so any correct ranking in the hybrid
    tests below is coming from BM25 + RRF fusion, not the vector leg."""
    return Embedding(vector=[1.0, 0.0], model_name="flat-fake")


def test_hybrid_retrieve_on_blank_query_returns_empty_list_without_querying_either_ranker():
    store = VectorStore(collection_name="test_hybrid_blank")
    bm25 = BM25Index([])
    retriever = Retriever(vector_store=store, embed_fn=_flat_embed, bm25_index=bm25)

    assert retriever.retrieve("   ") == []


def _filler_chunks() -> list[Chunk]:
    """BM25's IDF is mathematically degenerate on corpora this small (a
    term in 1 of 2 docs gets idf = log(1) = 0 exactly -- see
    test_retrieval_bm25.py's fuller explanation). These two filler chunks
    keep every hybrid-mode fixture below at 3+ documents so BM25 actually
    differentiates, the same floor any real corpus clears trivially."""
    return [
        Chunk(text="a filler chunk about something else entirely", source_id="s", chunk_id="filler#000", start_char=0, end_char=10),
        Chunk(text="another filler chunk covering unrelated shipyard topics", source_id="s", chunk_id="filler#001", start_char=0, end_char=10),
    ]


def test_hybrid_retrieve_surfaces_a_chunk_the_vector_leg_alone_cant_distinguish():
    """
    The actual point of Phase 2: with a vector embedder that can't tell any
    of these chunks apart (see _flat_embed), BM25's real keyword scoring is
    what makes the right chunk come back first once fused.
    """
    store = VectorStore(collection_name="test_hybrid_real")
    chunks = [
        Chunk(
            text="No more than four hot workers shall be attended by a single fire watch.",
            source_id="navsea_8010_ch4",
            chunk_id="navsea_8010_ch4#000",
            start_char=0,
            end_char=10,
            section="4.4.3",
        ),
        Chunk(
            text="Fans shall have non-sparking blades for ventilation equipment.",
            source_id="osha_1915_subpart_b",
            chunk_id="osha_1915_subpart_b#1915.13-000",
            start_char=0,
            end_char=10,
            section="1915.13",
        ),
        *_filler_chunks(),
    ]
    store.upsert(chunks, [Embedding(vector=[1.0, 0.0], model_name="flat-fake")] * len(chunks))
    bm25 = BM25Index.from_vector_store(store)
    retriever = Retriever(vector_store=store, embed_fn=_flat_embed, bm25_index=bm25)

    results = retriever.retrieve("how many hot workers can a fire watch attend", top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "navsea_8010_ch4#000"
    assert results[0].section == "4.4.3"


def test_hybrid_retrieve_compresses_result_text():
    store = VectorStore(collection_name="test_hybrid_compress")
    chunks = [
        Chunk(
            text=(
                "The fire watch must maintain an unobstructed view of all hot work. "
                "No more than four hot workers shall be attended by a single fire watch. "
                "The fire watch cannot rove between compartments during hot work."
            ),
            source_id="navsea_8010_ch4",
            chunk_id="navsea_8010_ch4#000",
            start_char=0,
            end_char=10,
            section="4.4.3",
        ),
        *_filler_chunks(),
    ]
    store.upsert(chunks, [Embedding(vector=[1.0, 0.0], model_name="flat-fake")] * len(chunks))
    bm25 = BM25Index.from_vector_store(store)
    retriever = Retriever(vector_store=store, embed_fn=_flat_embed, bm25_index=bm25)

    results = retriever.retrieve("how many hot workers per fire watch", top_k=1)

    assert len(results) == 1
    compressed = results[0].text
    # compressed down from the full 3-sentence chunk -- shorter, still
    # contains the actually-relevant fact, drops the two sentences that
    # don't answer "how many"
    assert compressed != chunks[0].text
    assert "No more than four hot workers" in compressed
    assert "cannot rove between compartments" not in compressed


def test_vector_only_mode_is_unaffected_by_hybrid_mode_existing():
    """
    Regression guard: Retriever with no bm25_index passed must behave
    exactly like Phase 1 -- no fusion, no compression -- regardless of
    hybrid mode existing elsewhere in the module.
    """
    store = VectorStore(collection_name="test_vector_only_unaffected")
    long_text = (
        "The fire watch must maintain an unobstructed view of all hot work. "
        "No more than four hot workers shall be attended by a single fire watch. "
        "The fire watch cannot rove between compartments during hot work."
    )
    chunks = [Chunk(text=long_text, source_id="s", chunk_id="s#000", start_char=0, end_char=10, section="4.4.3")]
    store.upsert(chunks, [Embedding(vector=[1.0, 0.0], model_name="fake")])
    retriever = Retriever(vector_store=store, embed_fn=_fake_embed)  # no bm25_index

    results = retriever.retrieve("fire watch", top_k=1)

    assert results[0].text == long_text  # uncompressed, full chunk text
