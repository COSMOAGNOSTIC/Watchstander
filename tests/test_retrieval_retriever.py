import pytest

from retrieval.retriever import RetrievalResult, Retriever


def test_retrieval_result_is_a_real_dataclass_with_expected_fields():
    r = RetrievalResult(chunk_id="c1", text="hi", source_id="s1", score=0.9)
    assert r.chunk_id == "c1"
    assert r.text == "hi"
    assert r.source_id == "s1"
    assert r.score == 0.9


def test_retriever_retrieve_not_yet_implemented():
    retriever = Retriever()
    with pytest.raises(NotImplementedError):
        retriever.retrieve("what is the fire watch capacity rule?")
