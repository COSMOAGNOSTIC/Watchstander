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


def test_psns_hot_work_returns_citation_without_unverified_caveat():
    """
    All seven entries in navsea_8010_psns_v2014.json were verified against
    the primary-source PDF text on 2026-08-08 (see the file's own
    verification_note and ARCHITECTURE.md ADR-023) -- the citation for a
    verified entry must not carry the UNVERIFIED caveat. This test is
    coupled to the current, real state of that file on purpose: if a
    future entry gets added and reverts this to verified=false, this test
    should fail loudly rather than silently keep asserting the old state.
    """
    citation = cite_governing_procedure("PSNS", [HazardCategory.HOT_WORK])
    assert citation is not None
    assert "PSNS" in citation
    assert "UNVERIFIED" not in citation


def test_cite_governing_procedure_surfaces_unverified_caveat_when_entry_says_so(monkeypatch):
    """
    Regression coverage for the caveat mechanism itself, decoupled from
    whatever navsea_8010_psns_v2014.json's real verification state happens
    to be right now (that file went from all-unverified to all-verified in
    one session -- a test asserting real-file content would have silently
    lost coverage of the UNVERIFIED path the moment that happened, without
    anyone noticing until a genuinely-unverified entry got added again and
    the caveat failed to appear). Injects a synthetic unverified entry
    directly instead.
    """
    fake_entry = {
        "procedure_id": "FAKE-1",
        "section": "Fake Section",
        "summary": "fake summary",
        "verified": False,
    }
    monkeypatch.setattr(
        "agent_core.procedural_lookup.procedures_for_hazard",
        lambda installation, hazard: [fake_entry],
    )
    citation = cite_governing_procedure("PSNS", [HazardCategory.HOT_WORK])
    assert citation is not None
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
