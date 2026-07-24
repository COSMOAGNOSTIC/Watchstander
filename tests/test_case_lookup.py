from agent_core.case_lookup import cite_best_case, cite_case, cases_for_hazard
from agent_core.state import HazardCategory


def test_cases_for_hazard_returns_sourced_cases():
    matches = cases_for_hazard(HazardCategory.CONFINED_SPACE)
    assert len(matches) >= 1
    assert any(c["case_id"] == "CS-2023-STJOHNS" for c in matches)


def test_cases_for_hazard_accepts_plain_string():
    """
    hazard_categories on a validated WorkPackageState come back as
    plain strings (Pydantic use_enum_values=True), not enum members --
    the lookup has to handle both.
    """
    matches = cases_for_hazard("hot_work")
    assert any(c["case_id"] == "HW-FIRSTMARINE" for c in matches)


def test_cite_case_returns_none_for_uncovered_hazard():
    """
    over_the_side has no dedicated case yet (MIGRATION.md Phase 4) --
    lookup should fail quietly, not raise.
    """
    assert cite_case(HazardCategory.OVER_THE_SIDE) is None


def test_cite_best_case_falls_through_to_covered_hazard():
    citation = cite_best_case([HazardCategory.OVER_THE_SIDE, HazardCategory.FALL_PROTECTION])
    assert citation is not None
    assert "FALL-DETYENS-2024" in citation