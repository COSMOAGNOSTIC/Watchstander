"""Session 8a: overhead detection reads label OR flag; WS-JF-006 routes unlocated overhead
work to the Safety Officer; SafetyBrief.recommended_action is always deterministic (rule 7).

All data is notional.
"""

from datetime import datetime as dt

import pytest

from agent_core import judgment, named_rules, reasoning
from agent_core.deconfliction import check_conflict, conflict_rule_ids, find_all_conflicts, is_overhead
from agent_core.judgment import judgment_flags
from agent_core.reasoning import generate_safety_brief
from agent_core.state import HazardCategory as H, SpatialCoordinates as SC, WorkPackageState as W

T0, T1 = dt(2027, 1, 12, 7), dt(2027, 1, 12, 15)


def wp(pid, hz=(), **sp):
    return W(work_package_id=pid, description=f"notional {pid}", hazard_categories=list(hz),
             spatial=SC(**sp), scheduled_start=T0, scheduled_end=T1)


# --- detection: overhead = spatial flag OR overhead hazard label ---------


@pytest.mark.parametrize("hz", [H.WORKING_ALOFT, H.OVER_THE_SIDE])
def test_hazard_labelled_overhead_over_other_work_is_a_conflict(hz):
    a = wp("ALOFT", [hz], frame_start=40, frame_end=44)
    b = wp("BELOW", [], frame_start=40, frame_end=44)
    assert check_conflict(a, b) is not None
    assert conflict_rule_ids(a, b) == ["WS-OH-001"]


def test_rationale_names_the_labelled_overhead_party_whichever_order():
    a = wp("BELOW", [], frame_start=40, frame_end=44)
    b = wp("ALOFT", [H.WORKING_ALOFT], frame_start=40, frame_end=44)
    assert "Overhead work (ALOFT)" in check_conflict(a, b)
    assert "Overhead work (ALOFT)" in check_conflict(b, a)


def test_two_overhead_packages_are_not_stacked_on_each_other():
    # Same rule as before for flags: both overhead -> not "overhead above other work".
    a = wp("A", [H.WORKING_ALOFT], frame_start=40, frame_end=44)
    b = wp("B", [], frame_start=40, frame_end=44, is_aloft=True)
    assert "WS-OH-001" not in conflict_rule_ids(a, b)


def test_labelled_overhead_with_disjoint_frames_is_not_a_conflict():
    assert check_conflict(wp("A", [H.WORKING_ALOFT], frame_start=40, frame_end=44),
                          wp("B", [], frame_start=90, frame_end=95)) is None


def test_is_overhead_is_the_single_shared_definition():
    from agent_core import shift_suggester
    assert shift_suggester._is_overhead is is_overhead
    assert is_overhead(wp("A", [H.WORKING_ALOFT])) and is_overhead(wp("B", [], is_over_side=True))
    assert not is_overhead(wp("C", [H.HOT_WORK]))


# --- WS-JF-006: overhead work with no frame range -> Safety Officer ------


@pytest.mark.parametrize("make", [
    lambda: wp("A", [H.WORKING_ALOFT]),
    lambda: wp("A", [], is_aloft=True),
    lambda: wp("A", [H.OVER_THE_SIDE], compartment_id="HULL-P"),  # compartment only: no frames
])
def test_overhead_work_without_frames_raises_ws_jf_006_to_the_safety_officer(make):
    [f] = [f for f in judgment_flags([make()]) if f.rule_id == "WS-JF-006"]
    assert f.routed_to.role == "Safety Officer" and f.routed_to.notional
    assert f.escalation_role is None or f.escalation_role != "Safety Officer"


def test_overhead_work_with_frames_raises_no_ws_jf_006():
    assert "WS-JF-006" not in {f.rule_id for f in judgment_flags([wp("A", [H.WORKING_ALOFT], frame_start=1, frame_end=3)])}


def test_ws_jf_006_is_catalogued_and_implemented():
    r = named_rules.get_rule("WS-JF-006")
    assert r.category == named_rules.RuleCategory.JUDGMENT and r.contact_role == "Safety Officer"
    assert "WS-JF-006" in judgment.IMPLEMENTED_TRIGGERS


# --- rule 7: recommended_action is always deterministic -----------------


def _flagged_pair():
    a = wp("A", [H.HOT_WORK], compartment_id="TANK-4")
    b = wp("B", [H.CONFINED_SPACE], compartment_id="TANK-4")
    find_all_conflicts([a, b])
    return a


def test_llm_recommendation_is_never_used(monkeypatch):
    monkeypatch.setattr(reasoning, "_call_llm", lambda ctx: {
        "executive_summary": "Model summary.", "precedent_context": "Model precedent.",
        "recommended_action": "MODEL SAYS: just proceed."})
    b = generate_safety_brief(_flagged_pair())
    assert b.source == "llm"
    assert "MODEL SAYS" not in b.recommended_action
    assert b.recommended_action == reasoning._deterministic_fallback(reasoning._grounding_context(_flagged_pair()))["recommended_action"]


def test_llm_may_still_phrase_the_summary(monkeypatch):
    monkeypatch.setattr(reasoning, "_call_llm", lambda ctx: {
        "executive_summary": "Model summary.", "precedent_context": "Model precedent."})
    b = generate_safety_brief(_flagged_pair())
    assert "Model summary." in b.executive_summary and b.source == "llm"


def test_llm_is_not_asked_for_a_recommendation():
    assert "recommended_action" not in reasoning._REQUIRED_LLM_KEYS
    assert "recommended_action" not in reasoning._SYSTEM_PROMPT
