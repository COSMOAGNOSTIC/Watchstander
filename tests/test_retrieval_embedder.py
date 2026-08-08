from retrieval.chunker import Chunk
from retrieval.embedder import DEFAULT_MODEL_NAME, Embedding, embed_chunks, embed_text


def test_embedding_is_a_real_dataclass_with_expected_fields():
    e = Embedding(vector=[0.1, 0.2], model_name="stub")
    assert e.vector == [0.1, 0.2]
    assert e.model_name == "stub"


def test_embed_text_uses_the_real_model_and_returns_a_normalized_vector(monkeypatch):
    """
    Real sentence-transformers model downloads require live network access
    on first use -- not something this test suite depends on (see
    embedder.py's module docstring). This patches _load_model with a fake
    that has the same .encode() interface real SentenceTransformer models
    expose, so embed_text's own logic (not the model itself) is what's
    under test here.
    """
    calls = []

    class FakeModel:
        def encode(self, text, normalize_embeddings=True):
            calls.append((text, normalize_embeddings))
            if isinstance(text, str):
                return _FakeVector([1.0, 0.0, 0.0])
            return [_FakeVector([1.0, 0.0, 0.0]) for _ in text]

    class _FakeVector(list):
        def tolist(self):
            return list(self)

    monkeypatch.setattr("retrieval.embedder._load_model", lambda model_name: FakeModel())

    result = embed_text("hello world")

    assert result.vector == [1.0, 0.0, 0.0]
    assert result.model_name == DEFAULT_MODEL_NAME
    assert calls == [("hello world", True)]


def test_embed_chunks_batches_in_one_call(monkeypatch):
    class _FakeVector(list):
        def tolist(self):
            return list(self)

    class FakeModel:
        def __init__(self):
            self.call_count = 0

        def encode(self, texts, normalize_embeddings=True):
            self.call_count += 1
            return [_FakeVector([float(len(t)), 0.0]) for t in texts]

    fake_model = FakeModel()
    monkeypatch.setattr("retrieval.embedder._load_model", lambda model_name: fake_model)

    chunks = [
        Chunk(text="ab", source_id="s", chunk_id="s#000", start_char=0, end_char=2),
        Chunk(text="abcd", source_id="s", chunk_id="s#001", start_char=2, end_char=6),
    ]
    result = embed_chunks(chunks)

    assert [e.vector[0] for e in result] == [2.0, 4.0]
    assert fake_model.call_count == 1  # one batch call, not one per chunk


def test_embed_chunks_of_empty_list_returns_empty_list():
    assert embed_chunks([]) == []
