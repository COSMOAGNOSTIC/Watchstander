"""
No injected/faked embedder needed here -- rank_bm25's scoring is pure
term-frequency math, no model download, no network. Real logic tested
directly, same as chunker.py and citation_formatter.py.
"""

from retrieval.bm25_index import BM25Index
from retrieval.vector_store import VectorStore


def _chunk(chunk_id, text, source_id="s", section=None):
    return {"chunk_id": chunk_id, "text": text, "source_id": source_id, "section": section}


def test_bm25_result_is_a_real_dataclass_with_expected_fields():
    from retrieval.bm25_index import BM25Result

    r = BM25Result(chunk_id="c1", text="hi", source_id="s1", score=1.5)
    assert r.chunk_id == "c1"
    assert r.text == "hi"
    assert r.source_id == "s1"
    assert r.score == 1.5
    assert r.section is None


def test_query_on_empty_index_returns_empty_list():
    index = BM25Index([])
    assert index.query("anything", top_k=3) == []


def test_query_on_blank_string_returns_empty_list():
    index = BM25Index([_chunk("c1", "fire watch capacity rule text")])
    assert index.query("   ", top_k=3) == []


# BM25's IDF term is mathematically degenerate on tiny corpora: for a term
# appearing in exactly 1 of only 2 documents, idf = log((2-1+0.5)/(1+0.5)) =
# log(1) = 0 exactly, and with 1 document total it goes negative. This isn't
# a bm25_index.py bug -- it's a real property of the classic Okapi BM25
# formula that only shows up because unit-test fixtures are far smaller than
# any real corpus (Phase 2's real corpus is 100+ chunks; this never comes up
# there). Every fixture below uses at least 3 documents so IDF behaves
# meaningfully, the same size floor a real (if small) corpus provides.
_FILLER_DOCS = [
    _chunk("filler-1", "a third filler document about something else entirely different"),
    _chunk("filler-2", "yet another filler document covering unrelated shipyard topics"),
]


def test_query_finds_the_chunk_with_matching_keywords():
    index = BM25Index(
        [
            _chunk("c1", "no more than four hot workers shall be attended by a single fire watch", section="4.4.3"),
            _chunk("c2", "completely unrelated bulkhead paint specification text"),
            *_FILLER_DOCS,
        ]
    )

    results = index.query("four hot workers fire watch", top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "c1"
    assert results[0].section == "4.4.3"
    assert results[0].score > 0


def test_query_excludes_chunks_with_zero_keyword_overlap():
    index = BM25Index(
        [
            _chunk("c1", "oxygen content testing before entering confined spaces"),
            _chunk("c2", "completely different vocabulary about ship painting schedules"),
            *_FILLER_DOCS,
        ]
    )

    results = index.query("oxygen content confined spaces", top_k=5)

    ids = {r.chunk_id for r in results}
    assert "c1" in ids
    assert "c2" not in ids


def test_bm25_finds_an_exact_section_number_that_a_word_overlap_query_wouldnt():
    """
    A real advantage keyword search has over even a decent vector search:
    exact-token matches like a regulation number. Literal "1915.12" in the
    query should surface the chunk containing that literal token.
    """
    index = BM25Index(
        [
            _chunk("c1", "see section 1915.12 for oxygen content precautions", section="1915.12"),
            _chunk("c2", "see section 1915.14 for hot work precautions", section="1915.14"),
            *_FILLER_DOCS,
        ]
    )

    results = index.query("requirements under 1915.12", top_k=1)

    assert results[0].chunk_id == "c1"


def test_from_vector_store_builds_an_index_from_stored_chunks():
    from retrieval.embedder import Embedding

    store = VectorStore(collection_name="test_bm25_from_store")
    from retrieval.chunker import Chunk

    def _fake_chunk(chunk_id, text):
        return Chunk(text=text, source_id="s", chunk_id=chunk_id, start_char=0, end_char=len(text))

    chunks = [
        Chunk(text="fire watch capacity limit is four", source_id="s", chunk_id="s#000", start_char=0, end_char=10, section="4.4.3"),
        _fake_chunk("s#001", "a third filler document about something else entirely different"),
        _fake_chunk("s#002", "yet another filler document covering unrelated shipyard topics"),
    ]
    store.upsert(chunks, [Embedding(vector=[1.0, 0.0], model_name="fake")] * len(chunks))

    index = BM25Index.from_vector_store(store)
    results = index.query("fire watch capacity limit", top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "s#000"
    assert results[0].section == "4.4.3"


def test_from_vector_store_on_empty_store_builds_an_empty_index():
    store = VectorStore(collection_name="test_bm25_from_empty_store")
    index = BM25Index.from_vector_store(store)
    assert index.query("anything", top_k=3) == []
