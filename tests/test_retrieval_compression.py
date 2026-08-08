from retrieval.compression import compress


def test_compress_returns_full_text_unchanged_when_already_short():
    text = "One sentence only."
    assert compress(text, "query", max_sentences=2) == text


def test_compress_returns_full_text_unchanged_for_blank_query():
    text = "First sentence here. Second sentence here. Third sentence here."
    assert compress(text, "   ", max_sentences=1) == text


def test_compress_returns_full_text_unchanged_when_no_sentence_matches_query():
    text = "Alpha bravo charlie. Delta echo foxtrot. Golf hotel india."
    assert compress(text, "unrelated vocabulary entirely", max_sentences=1) == text


def test_compress_prefers_the_relevant_sentence_over_the_first_one():
    """
    The whole point of real compression over a blind head-truncation: the
    most query-relevant sentence isn't always first.
    """
    text = (
        "The fire watch must maintain an unobstructed view of all hot work. "
        "No more than four hot workers shall be attended by a single fire watch. "
        "The fire watch cannot rove between compartments during hot work."
    )
    result = compress(text, "how many hot workers per fire watch", max_sentences=1)
    assert result == "No more than four hot workers shall be attended by a single fire watch."


def test_compress_preserves_original_sentence_order_when_keeping_multiple():
    text = (
        "Sentence one about oxygen content requirements. "
        "Sentence two about something unrelated entirely. "
        "Sentence three also about oxygen content and testing."
    )
    result = compress(text, "oxygen content", max_sentences=2)
    assert result.index("Sentence one") < result.index("Sentence three")
    assert "Sentence two" not in result
