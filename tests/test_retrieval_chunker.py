from retrieval.chunker import Chunk, chunk_text


def test_chunk_is_a_real_dataclass_with_expected_fields():
    c = Chunk(text="hello", source_id="navsea_8010", chunk_id="navsea_8010#000", start_char=0, end_char=5)
    assert c.text == "hello"
    assert c.source_id == "navsea_8010"
    assert c.chunk_id == "navsea_8010#000"
    assert c.start_char == 0
    assert c.end_char == 5
    assert c.section is None


def test_chunk_text_returns_empty_list_for_empty_input():
    assert chunk_text("", source_id="navsea_8010") == []
    assert chunk_text("   \n  ", source_id="navsea_8010") == []


def test_chunk_text_never_splits_a_sentence_across_chunks():
    text = "First sentence here. Second sentence here. Third sentence here. Fourth one too."
    chunks = chunk_text(text, source_id="s", chunk_size=40, overlap=5)
    assert len(chunks) > 1
    for c in chunks:
        assert c.text.strip().endswith((".", "!", "?"))
        # every chunk boundary lands exactly on a sentence boundary in the
        # source text, not mid-word
        assert text[c.start_char:c.end_char].strip() == c.text


def test_chunk_text_covers_the_whole_document_without_gaps():
    """
    Consecutive chunks either overlap or abut with nothing lost between them
    (the only non-overlap gap allowed is the single whitespace character
    the sentence splitter consumes and includes in neither span). Overlap
    itself is opportunistic, not guaranteed for every boundary: when a
    chunk is a single sentence with no earlier sentence of its own to back
    into, there's nothing to overlap with without duplicating that whole
    sentence forever -- see chunker.py's back-off loop. What must always
    hold is that no text goes missing between chunks.
    """
    text = "First sentence here. Second sentence here. Third sentence here. Fourth one too."
    chunks = chunk_text(text, source_id="s", chunk_size=40, overlap=15)
    for a, b in zip(chunks, chunks[1:]):
        assert b.start_char - a.end_char <= 1


def test_chunk_text_ids_are_sequential_and_stable():
    text = "One. Two. Three. Four. Five."
    chunks = chunk_text(text, source_id="navsea_8010", chunk_size=10, overlap=2)
    ids = [c.chunk_id for c in chunks]
    assert ids == [f"navsea_8010#{i:03d}" for i in range(len(chunks))]


def test_chunk_text_never_drops_an_oversized_sentence():
    """A single sentence longer than chunk_size still becomes its own chunk
    rather than being truncated or dropped."""
    long_sentence = "This is a single very long sentence that on its own exceeds the configured chunk size limit by quite a lot."
    text = f"Short one. {long_sentence} Another short one."
    chunks = chunk_text(text, source_id="s", chunk_size=20, overlap=5)
    assert any(long_sentence in c.text for c in chunks)


def test_chunk_text_tags_navsea_style_section_numbers():
    # Real source text (retrieval/sources/navsea_8010_ch4.txt) always puts a
    # numbered heading at the start of its own line -- the section regex
    # requires that same start-of-line anchor, so headers joined by a plain
    # space mid-paragraph (not how the real corpus is formatted) wouldn't
    # match, and shouldn't: it'd risk false-positiving on stray numbers
    # elsewhere in running prose (e.g. "29 CFR Part 1915").
    text = (
        "4.4.2 Additional Duties During Hot Work. The fire watch shall not accomplish other duties.\n"
        "4.4.3 Limitations to Single Fire Watch with Multiple Hot Workers. "
        "No more than four hot workers shall be attended by a single fire watch."
    )
    chunks = chunk_text(text, source_id="navsea_8010", chunk_size=1000, overlap=0)
    assert len(chunks) == 1
    # the last (most recently in-force) section header inside the chunk is
    # what carries -- 4.4.3 governs the chunk's final sentence, not 4.4.2
    assert chunks[0].section == "4.4.3"


def test_chunk_text_leaves_section_none_for_unnumbered_prose():
    chunks = chunk_text("Just some plain prose with no section headers at all.", source_id="cases_v1")
    assert all(c.section is None for c in chunks)


def test_chunk_text_carries_section_forward_into_continuation_chunks():
    """
    Regression test for a real bug found via test_retrieval_integration.py:
    a chunk that continues a section (comes after the header sentence, so
    contains no header text of its own) must still inherit that section
    number, not silently lose its citation. Small chunk_size forces the
    header and its continuation into separate chunks.
    """
    text = (
        "4.4.3 Limitations to Single Fire Watch with Multiple Hot Workers. "
        "A single fire watch may provide protection where several hot workers are performing hot work. "
        "No more than four hot workers shall be attended by a single fire watch. "
        "The fire watch cannot rove from one compartment to another."
    )
    chunks = chunk_text(text, source_id="navsea_8010", chunk_size=60, overlap=0)
    assert len(chunks) > 1
    assert all(c.section == "4.4.3" for c in chunks)
