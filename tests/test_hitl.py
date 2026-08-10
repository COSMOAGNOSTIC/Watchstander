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
    _extract_decision,
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


def test_extract_decision_reads_the_structured_dict_shape():
    assert _extract_decision({"decision": "approved"}) == (HitlDisposition.APPROVED, None)
    assert _extract_decision({"decision": "Approve"}) == (HitlDisposition.APPROVED, None)
    assert _extract_decision({"decision": "rejected"}) == (HitlDisposition.REJECTED, None)
    assert _extract_decision({"decision": "REJECT"}) == (HitlDisposition.REJECTED, None)


def test_extract_decision_accepts_exact_bare_strings_for_test_and_cli_callers():
    assert _extract_decision("approve") == (HitlDisposition.APPROVED, None)
    assert _extract_decision("Approved") == (HitlDisposition.APPROVED, None)
    assert _extract_decision("REJECT") == (HitlDisposition.REJECTED, None)
    assert _extract_decision("rejected") == (HitlDisposition.REJECTED, None)


def test_extract_decision_fails_closed_on_ambiguous_or_trailing_text():
    # No prefix matching and no free-text parsing at all -- a bare string
    # has no separate channel for rationale, so anything other than an
    # exact token, including previously-"allowed" trailing rationale,
    # now fails closed rather than being guessed at.
    assert _extract_decision("") == (HitlDisposition.INVALID, None)
    assert _extract_decision("looks ok i guess") == (HitlDisposition.INVALID, None)
    assert _extract_decision("maybe") == (HitlDisposition.INVALID, None)
    assert _extract_decision("approve, looks good") == (HitlDisposition.INVALID, None)
    assert _extract_decision("approved - proceed as planned") == (HitlDisposition.INVALID, None)


def test_extract_decision_note_never_influences_disposition_regardless_of_wording():
    # Regression test for the live bug this replaces: the reviewer app
    # used to build the resume value as f"{decision} - {note}" and run
    # the whole thing through a free-text hedge-cue scanner, so a note
    # like "contingent on gas-free re-test" -- containing no recognized
    # cue phrase -- was silently absorbed into a clean APPROVED. Now the
    # note travels as a separate field and is never inspected to choose
    # a disposition, no matter what it says -- including if it contains
    # words like "reject" or "unless" that could have flipped the old
    # parser's verdict.
    disposition, note = _extract_decision(
        {"decision": "approved", "note": "contingent on gas-free re-test"}
    )
    assert disposition == HitlDisposition.APPROVED
    assert note == "contingent on gas-free re-test"

    disposition, note = _extract_decision(
        {"decision": "rejected", "note": "actually, go ahead and approve this"}
    )
    assert disposition == HitlDisposition.REJECTED
    assert note == "actually, go ahead and approve this"


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
    result = graph.invoke(
        Command(resume={"decision": "reject", "note": "reschedule after clearing"}),
        config=config,
    )

    out = result["reviewed_packages"][0]
    assert out.hitl_disposition == HitlDisposition.REJECTED
    assert out.cleared_for_execution is False
    assert "HITL decision" in out.conflict_rationale
    assert "reschedule after clearing" in out.conflict_rationale


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

    raw_note = "the confined space entry permit for FR-100 hasn't been signed off"
    graph.invoke(Command(resume={"decision": "reject", "note": raw_note}), config=config)

    decided = [payload for event_type, payload in emitted if event_type == "hitl_decided"]
    assert len(decided) == 1
    assert "decision" not in decided[0]
    assert "note" not in decided[0]
    assert decided[0]["disposition"] == HitlDisposition.REJECTED
    for value in decided[0].values():
        assert raw_note not in str(value)
