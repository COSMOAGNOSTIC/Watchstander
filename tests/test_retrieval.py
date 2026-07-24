from agent_core.retrieval import cite_best_matching_case, retrieve_best_case_for_hazards
from agent_core.state import HazardCategory


def test_returns_none_when_no_case_for_hazard():
    assert retrieve_best_case_for_hazards("anything", [HazardCategory.OVER_THE_SIDE]) is None


def test_single_candidate_category_returns_that_case_regardless_of_query():
    """
    hot_work only has one sourced case -- HW-FIRSTMARINE -- so it should
    always come back for that category, whatever the query says.
    """
    case = retrieve_best_case_for_hazards(
        "completely unrelated query text about nothing in particular",
        [HazardCategory.HOT_WORK],
    )
    assert case is not None
    assert case["case_id"] == "HW-FIRSTMARINE"


def test_empty_query_falls_back_to_first_case_deterministically():
    """
    With no query signal, ranking can't do anything useful -- fall back
    to the first sourced case for the category, same as Phase 1's
    case_lookup.cite_case(), so behavior stays deterministic.
    """
    case = retrieve_best_case_for_hazards("", [HazardCategory.FALL_PROTECTION])
    assert case is not None
    assert case["case_id"] == "FALL-DETYENS-2024"


def test_ranks_multi_case_category_by_relevance_not_just_first_in_file():
    """
    fall_protection has three sourced cases. A query describing the
    struck-by-shackle-during-a-lift pattern should surface
    STRUCK-DETYENS-2020, not just FALL-DETYENS-2024 (the first one in
    cases_v1.json) -- this is the actual Phase 3 improvement over
    Phase 1's flat lookup.
    """
    case = retrieve_best_case_for_hazards(
        "shackle struck lifting operation rudder shaft caught-between hazard",
        [HazardCategory.FALL_PROTECTION],
    )
    assert case is not None
    assert case["case_id"] == "STRUCK-DETYENS-2020"


def test_cite_best_matching_case_formats_like_phase1_citation():
    citation = cite_best_matching_case(
        "welder entered a space without atmospheric testing",
        [HazardCategory.CONFINED_SPACE],
    )
    assert citation is not None
    assert "CS-2023-STJOHNS" in citation
    assert "Root cause:" in citation


def test_cite_best_matching_case_returns_none_for_uncovered_hazard():
    assert cite_best_matching_case("anything", [HazardCategory.OVER_THE_SIDE]) is None
