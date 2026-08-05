import pytest

from retrieval.chunker import Chunk, chunk_text


def test_chunk_is_a_real_dataclass_with_expected_fields():
    c = Chunk(text="hello", source_id="navsea_8010", chunk_id="navsea_8010#000", start_char=0, end_char=5)
    assert c.text == "hello"
    assert c.source_id == "navsea_8010"
    assert c.chunk_id == "navsea_8010#000"
    assert c.start_char == 0
    assert c.end_char == 5


def test_chunk_text_not_yet_implemented():
    """Phase 0: the function boundary exists; real logic lands in Phase 1."""
    with pytest.raises(NotImplementedError):
        chunk_text("some text", source_id="navsea_8010")
