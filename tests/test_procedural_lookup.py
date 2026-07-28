from agent_core.procedural_lookup import cite_governing_procedure, procedures_for_hazard
from agent_core.state import HazardCategory


def test_no_installation_returns_none():
    """
    Unset governing_installation must produce no citation at all, not a
    silently-assumed default site's rules.
    """
    assert cite_governing_procedure(None, [HazardCategory.HOT_WORK]) is None


def test_unknown_installation_returns_none():
    assert cite_governing_procedure("NASNI", [HazardCategory.HOT_WORK]) is None


def test_psns_hot_work_returns_citation_with_unverified_caveat():
    """
    Every entry in navsea_8010_psns_v2014.json is currently verified=false
    (structural extraction only, not confirmed against primary-source
    text) -- the citation must surface that caveat, not hide it.
    """
    citation = cite_governing_procedure("PSNS", [HazardCategory.HOT_WORK])
    assert citation is not None
    assert "PSNS" in citation
    assert "UNVERIFIED" in citation


def test_psns_has_no_entries_for_hazards_the_manual_does_not_cover():
    """
    The 8010 Manual is entirely about fire/hot work -- it does not
    address confined_space, working_aloft, fall_protection, or
    over_the_side. Regression test: no entries should ever silently
    appear for those categories under this ruleset.
    """
    for hazard in (
        HazardCategory.CONFINED_SPACE,
        HazardCategory.WORKING_ALOFT,
        HazardCategory.FALL_PROTECTION,
        HazardCategory.OVER_THE_SIDE,
    ):
        assert procedures_for_hazard("PSNS", hazard) == []
        assert cite_governing_procedure("PSNS", [hazard]) is None


def test_cite_governing_procedure_checks_all_given_hazards():
    """
    A package can carry multiple hazard categories -- the lookup should
    find a match on any of them, not just the first.
    """
    citation = cite_governing_procedure(
        "PSNS", [HazardCategory.CONFINED_SPACE, HazardCategory.HOT_WORK]
    )
    assert citation is not None
