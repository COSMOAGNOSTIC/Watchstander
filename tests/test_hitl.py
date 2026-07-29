"""
Tests for the HITL gate's disposition enforcement. Before this fix,
the gate genuinely paused execution (real, not simulated), but the
human reviewer's decision was recorded only as a string appended to
`conflict_rationale` -- "approve" and "reject" produced identical
downstream state. These tests exercise the actual `interrupt()`/resume
flow through a real compiled LangGraph graph, not just the parsing helper,
so a regression here would be caught the same way a real caller would hit
it.

Updated for the Send()-based restructure: the single `hitl_gate_node`
became `hitl_prepare_node` (partitions passthrough vs. needs-review) +
`hitl_route` (fans out Send() per package needing review) +
`hitl_gate_single_node` (one interrupt() per package). The gate-only
fixture below wires those three together the same way the real graph
does, and results are read from `reviewed_packages`, not
`work_packages` -- see agent_core/hitl.py and agent_core/graph.py
docstrings for why.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from agent_core import events
from agent_core.hitl import (
    _parse_decision,
    hitl_gate_single_node,
    hitl_prepare_node,
    hitl_route,
)
from agent_core.state import HitlDisposition, RiskLevel, WorkPackageState


class _GateOnlyState(TypedDict):
    work_packages: list
    reviewed_packages: Annotated[list, operator.add]


def _build_gate_only_graph():
    graph = StateGraph(_GateOnlyState)
    graph.add_node("hitl_prepare", hitl_prepare_node)
    graph.add_node("hitl_gate_single", hitl_gate_single_node)
    graph.set_entry_point("hitl_prepare")
    graph.add_conditional_edges("hitl_prepare", hitl_route, ["hitl_gate_single", END])
    graph.add_edge("hitl_gate_single", END)
    return graph.compile(checkpointer=MemorySaver())


def test_parse_decision_is_case_insensitive_and_prefix_matched():
    assert _parse_decision("approve") == HitlDisposition.APPROVED
    assert _parse_decision("Approved, looks fine") == HitlDisposition.APPROVED
    assert _parse_decision("REJECT") == HitlDisposition.REJECTED
    assert _parse_decision("rejected - reschedule") == HitlDisposition.REJECTED


def test_parse_decision_fails_closed_on_ambiguous_input():
    assert _parse_decision("") == HitlDisposition.INVALID
    assert _parse_decision("looks ok i guess") == HitlDisposition.INVALID
    assert _parse_decision("maybe") == HitlDisposition.INVALID


def test_parse_decision_fails_closed_on_conditional_or_negated_approve_text():
    assert _parse_decision("approve only if the marine chemist re-certifies") == HitlDisposition.INVALID
    assert _parse_decision("approve?? absolutely not") == HitlDisposition.INVALID
    assert _parse_decision("approve unless the permit lapses") == HitlDisposition.INVALID
    assert _parse_decision("wouldn't approve this as written") == HitlDisposition.INVALID


def test_parse_decision_still_allows_trailing_rationale_after_a_clean_verdict():
    assert _parse_decision("approve, looks good") == HitlDisposition.APPROVED
    assert _parse_decision("approved - proceed as planned") == HitlDisposition.APPROVED
    assert _parse_decision("reject - reschedule after clearing") == HitlDisposition.REJECTED


def test_approve_sets_disposition_and_clears_for_execution():
    graph = _build_gate_only_graph()
    wp = WorkPackageState(work_package_id="A", description="x", requires_hitl_review=True)
    config = {"configurable": {"thread_id": "approve-1"}}

    paused = graph.invoke({"work_packages": [wp], "reviewed_packages": []}, config=config)
    assert "__interrupt__" in paused  # graph genuinely paused

    result = graph.invoke(Command(resume="approve"), config=config)
    out = result["reviewed_packages"][0]
    assert out.hitl_disposition == HitlDisposition.APPROVED
    assert out.cleared_for_execution is True


def test_reject_blocks_the_package_structurally_not_just_in_prose():
    graph = _build_gate_only_graph()
    wp = WorkPackageState(work_package_id="B", description="x", requires_hitl_review=True)
    config = {"configurable": {"thread_id": "reject-1"}}

    graph.invoke({"work_packages": [wp], "reviewed_packages": []}, config=config)
    result = graph.invoke(Command(resume="reject - reschedule after clearing"), config=config)

    out = result["reviewed_packages"][0]
    assert out.hitl_disposition == HitlDisposition.REJECTED
    assert out.cleared_for_execution is False
    assert "HITL decision" in out.conflict_rationale


def test_unparseable_decision_fails_closed():
    graph = _build_gate_only_graph()
    wp = WorkPackageState(work_package_id="C", description="x", requires_hitl_review=True)
    config = {"configurable": {"thread_id": "invalid-1"}}

    graph.invoke({"work_packages": [wp], "reviewed_packages": []}, config=config)
    result = graph.invoke(Command(resume="uhh not sure, ask someone else"), config=config)

    out = result["reviewed_packages"][0]
    assert out.hitl_disposition == HitlDisposition.INVALID
    assert out.cleared_for_execution is False


def test_package_not_requiring_review_is_cleared_by_default_and_never_paused():
    graph = _build_gate_only_graph()
    wp = WorkPackageState(work_package_id="D", description="clean package")
    config = {"configurable": {"thread_id": "clean-1"}}

    result = graph.invoke({"work_packages": [wp], "reviewed_packages": []}, config=config)
    assert "__interrupt__" not in result  # never paused - no review was needed

    out = result["reviewed_packages"][0]
    assert out.hitl_disposition is None
    assert out.cleared_for_execution is True


def test_critical_risk_forces_review_even_without_a_flagged_conflict():
    graph = _build_gate_only_graph()
    wp = WorkPackageState(
        work_package_id="E", description="x", risk_level=RiskLevel.CRITICAL
    )
    config = {"configurable": {"thread_id": "critical-1"}}

    paused = graph.invoke({"work_packages": [wp], "reviewed_packages": []}, config=config)
    assert "__interrupt__" in paused

    result = graph.invoke(Command(resume="reject"), config=config)
    out = result["reviewed_packages"][0]
    assert out.cleared_for_execution is False


def test_hitl_decided_event_never_broadcasts_the_raw_reviewer_text(monkeypatch):
    graph = _build_gate_only_graph()
    wp = WorkPackageState(work_package_id="F", description="x", requires_hitl_review=True)
    config = {"configurable": {"thread_id": "no-leak-1"}}

    graph.invoke({"work_packages": [wp], "reviewed_packages": []}, config=config)

    emitted = []
    monkeypatch.setattr(events, "emit", lambda event_type, **payload: emitted.append((event_type, payload)))

    raw_text = "reject - the confined space entry permit for FR-100 hasn't been signed off"
    graph.invoke(Command(resume=raw_text), config=config)

    decided = [payload for event_type, payload in emitted if event_type == "hitl_decided"]
    assert len(decided) == 1
    assert "decision" not in decided[0]
    assert decided[0]["disposition"] == HitlDisposition.REJECTED
    for value in decided[0].values():
        assert raw_text not in str(value)
