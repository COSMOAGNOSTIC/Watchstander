import pytest

from retrieval.citation_formatter import format_citation


def test_format_citation_not_yet_implemented():
    with pytest.raises(NotImplementedError):
        format_citation(source_id="navsea_8010", chunk_id="navsea_8010#003")
