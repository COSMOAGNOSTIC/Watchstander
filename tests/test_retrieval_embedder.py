import pytest

from retrieval.embedder import Embedding, embed_chunks, embed_text


def test_embedding_is_a_real_dataclass_with_expected_fields():
    e = Embedding(vector=[0.1, 0.2], model_name="stub")
    assert e.vector == [0.1, 0.2]
    assert e.model_name == "stub"


def test_embed_text_not_yet_implemented():
    with pytest.raises(NotImplementedError):
        embed_text("some text")


def test_embed_chunks_not_yet_implemented():
    with pytest.raises(NotImplementedError):
        embed_chunks([])
