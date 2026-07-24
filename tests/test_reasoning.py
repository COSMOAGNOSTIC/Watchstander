from agent_core.deconfliction import find_all_conflicts
from agent_core.reasoning import generate_safety_brief, provenance_tag, reasoning_node
from agent_core.state import HazardCategory, SpatialCoordinates, WorkPackageState


def make_wp(**overrides) -> WorkPackageState:
    defaults = dict(
        work_package_id="WP-001",
        description="test package",
    )
    defaults.update(overrides)
    return WorkPackageState(**defaults)


def _flagged_pair():
    """
    Hot work / confined space overlap -- mirrors the First Marine LLC
    pattern, which has a sourced case in case_data/cases_v1.json.
    """
    a = make_wp(
        work_package_id="WP-HOTWORK",
        hazard_categories=[HazardCategory.HOT_WORK],
        spatial=SpatialCoordinates(frame_start=40, frame_end=48, compartment_id="FR-44-TANK"),
    )
    b = make_wp(
        work_package_id="WP-CONFINED",
        hazard_categories=[HazardCategory.CONFINED_SPACE],
        spatial=SpatialCoordinates(frame_start=42, frame_end=50, compartment_id="FR-44-TANK"),
    )
    find_all_conflicts([a, b])
    return a, b


def test_generate_safety_brief_uses_deterministic_fallback_without_api_key(monkeypatch):
    """
    No ANTHROPIC_API_KEY is set in CI, so this must never attempt a
    network call -- it should silently use the deterministic fallback.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    wp, _ = _flagged_pair()

    brief = generate_safety_brief(wp)

    assert brief.source == "deterministic-fallback"


def test_safety_brief_is_grounded_in_real_conflict_rationale(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    wp, _ = _flagged_pair()

    brief = generate_safety_brief(wp)

    assert wp.work_package_id in brief.executive_summary
    assert wp.conflict_rationale in brief.executive_summary


def test_safety_brief_cites_real_sourced_case_not_a_hallucination(monkeypatch):
    """
    hot_work has two sourced cases on file as of the Phase 4 data pass
    (HW-FIRSTMARINE, HW-ASHTABULA-2024) -- the brief's precedent_context
    must cite one of them verbatim, whichever ranks higher for this
    conflict's text, never an invented case_id.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    wp, _ = _flagged_pair()

    brief = generate_safety_brief(wp)

    assert any(
        real_case_id in brief.precedent_context
        for real_case_id in ("HW-FIRSTMARINE", "HW-ASHTABULA-2024")
    )


def test_safety_brief_notes_missing_case_instead_of_inventing_one(monkeypatch):
    """
    over_the_side has no sourced case yet (MIGRATION.md Phase 4) -- the
    brief must say so explicitly rather than fabricate a citation.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    a = make_wp(
        work_package_id="WP-OVERSIDE",
        hazard_categories=[HazardCategory.OVER_THE_SIDE],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="X"),
    )
    b = make_wp(
        work_package_id="WP-OTHER",
        hazard_categories=[HazardCategory.OVER_THE_SIDE],
        spatial=SpatialCoordinates(frame_start=1, frame_end=5, compartment_id="X"),
    )
    # Force a conflict without relying on INCOMPATIBLE_HAZARD_PAIRS coverage.
    a.conflicts.append(b.work_package_id)
    a.conflict_rationale = "Manually flagged for this test."

    brief = generate_safety_brief(a)

    assert "No sourced case on file" in brief.precedent_context


def test_provenance_tag_maps_known_sources():
    assert provenance_tag("llm") == "[SOURCE: LLM SYNTHESIS]"
    assert provenance_tag("deterministic-fallback") == "[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]"


def test_fallback_brief_is_visibly_tagged_as_deterministic(monkeypatch):
    """
    Per architecture review: a Safety Officer reading the brief must be
    able to tell at a glance whether an LLM actually reasoned about this
    or a template filled it in because no model was reachable. The tag
    has to be in the reviewer-facing text itself, not just the `source`
    field on the model.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    wp, _ = _flagged_pair()

    brief = generate_safety_brief(wp)

    assert brief.executive_summary.startswith("[SOURCE: DETERMINISTIC FALLBACK - LLM OFFLINE]")


def test_reasoning_node_only_briefs_flagged_packages(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    flagged, also_flagged = _flagged_pair()
    clean = make_wp(
        work_package_id="WP-CLEAN",
        spatial=SpatialCoordinates(frame_start=200, frame_end=210),
    )

    result = reasoning_node({"work_packages": [flagged, also_flagged, clean]})

    packages_by_id = {wp.work_package_id: wp for wp in result["work_packages"]}
    assert packages_by_id["WP-HOTWORK"].safety_brief is not None
    assert packages_by_id["WP-CONFINED"].safety_brief is not None
    assert packages_by_id["WP-CLEAN"].safety_brief is None
