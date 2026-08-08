from retrieval.citation_formatter import format_citation


def test_format_citation_with_section_cites_document_and_section():
    citation = format_citation(source_id="navsea_8010_ch4", chunk_id="navsea_8010_ch4#003", section="4.4.3")
    assert citation == "NAVSEA 8010 Manual (S0570-AC-CCM-010/8010), Sec. 4.4.3"


def test_format_citation_without_section_falls_back_to_chunk_id():
    citation = format_citation(source_id="cases_v1", chunk_id="cases_v1#000")
    assert citation == "Watchstander Sourced Case File (cases_v1#000)"


def test_format_citation_both_navsea_chapter_source_ids_cite_the_same_document_title():
    ch4 = format_citation(source_id="navsea_8010_ch4", chunk_id="navsea_8010_ch4#000", section="4.4.3")
    ch11 = format_citation(source_id="navsea_8010_ch11", chunk_id="navsea_8010_ch11#000", section="11.1.7")
    assert ch4.startswith("NAVSEA 8010 Manual (S0570-AC-CCM-010/8010)")
    assert ch11.startswith("NAVSEA 8010 Manual (S0570-AC-CCM-010/8010)")


def test_format_citation_unknown_source_id_falls_back_to_raw_id_not_a_guess():
    """An unregistered source_id must never silently get a plausible-looking
    but fabricated title -- it should surface the raw id so the gap is
    obvious, not hidden."""
    citation = format_citation(source_id="some_new_unregistered_source", chunk_id="some_new_unregistered_source#000")
    assert "some_new_unregistered_source" in citation
