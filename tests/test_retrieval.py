from agent_core.retrieval import cite_best_matching_case, retrieve_best_case_for_hazards
from agent_core.state import HazardCategory


def test_returns_none_when_no_case_for_hazard():
    assert retrieve_best_case_for_hazards("anything", [HazardCategory.OVER_THE_SIDE]) is None


def test_single_candidate_category_returns_that_case_regardless_of_query():
    """
    confined_space only has one sourced case on file -- CS-2023-STJOHNS --
    so it should always come back for that category, whatever the query
    says. (hot_work moved to two cases in the Phase 4 data pass --
    see test_ranks_within_hot_work_category_by_relevance below for its
    multi-candidate coverage.)
    """
    case = retrieve_best_case_for_hazards(
        "completely unrelated query text about nothing in particular",
        [HazardCategory.CONFINED_SPACE],
    )
    assert case is not None
    assert case["case_id"] == "CS-2023-STJOHNS"


def test_ranks_within_hot_work_category_by_relevance():
    """
    hot_work now has two sourced cases (Phase 4 data pass): HW-FIRSTMARINE
    (explosion from an untested flammable atmosphere during cutting/
    welding) and HW-ASHTABULA-2024 (fire from welding/paint-removal in a
    cargo hold). A query specifically describing the explosive-atmosphere
    pattern should rank HW-FIRSTMARINE first; a query describing the
    paint-removal/cargo-hold pattern should rank HW-ASHTABULA-2024 first.
    """
    explosion_query = retrieve_best_case_for_hazards(
        "explosion flammable gases atmosphere towboat contractors cited",
        [HazardCategory.HOT_WORK],
    )
    assert explosion_query["case_id"] == "HW-FIRSTMARINE"

    paint_removal_query = retrieve_best_case_for_hazards(
        "paint removal cargo hold Cuyahoga crewmembers lunch break Ashtabula",
        [HazardCategory.HOT_WORK],
    )
    assert paint_removal_query["case_id"] == "HW-ASHTABULA-2024"


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
