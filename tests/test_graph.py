"""
Smoke tests for the assembled graph. Before this file existed, nothing in
the test suite ever imported `agent_core.graph` or `agent_core.hitl` -
CI was green while `graph.py`'s `from langgraph.checkpoint.sqlite import
SqliteSaver` failed on a clean install (that package isn't in
pyproject.toml's dependencies without the fix alongside this test). A
green badge was masking a broken build of the flagship component. These
tests exist so that can't happen silently again.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent_core.graph import build_graph
from agent_core.state import HitlDisposition, RiskLevel, WorkPackageState


def test_graph_module_imports_and_builds():
    """
    The literal regression test: agent_core.graph must import cleanly and
    build_graph() must return a compiled graph. This alone would have
    caught the missing langgraph-checkpoint-sqlite dependency.
    """
    graph = build_graph(checkpointer=MemorySaver())
    assert graph is not None


def test_graph_runs_end_to_end_through_deconfliction_reasoning_and_hitl():
    """
    Drives a real invocation through all three nodes - deconfliction flags
    nothing new here (single package, no conflict), but a CRITICAL risk
    level forces the HITL gate to pause regardless, exercising the full
    entry -> deconfliction -> reasoning -> hitl_gate -> END path with a
    genuine interrupt/resume cycle, not a mock.
    """
    graph = build_graph(checkpointer=MemorySaver())
    critical = WorkPackageState(
        work_package_id="CRIT-1", description="high-risk task", risk_level=RiskLevel.CRITICAL
    )
    clean = WorkPackageState(work_package_id="CLEAN-1", description="routine task")
    config = {"configurable": {"thread_id": "e2e-1"}}

    paused = graph.invoke({"work_packages": [critical, clean]}, config=config)
    assert "__interrupt__" in paused  # graph genuinely paused for the critical package

    final = graph.invoke(Command(resume="approve"), config=config)
    packages = {wp.work_package_id: wp for wp in final["work_packages"]}

    assert packages["CRIT-1"].hitl_disposition == HitlDisposition.APPROVED
    assert packages["CRIT-1"].cleared_for_execution is True
    # The clean package never needed review and was never paused on.
    assert packages["CLEAN-1"].hitl_disposition is None
    assert packages["CLEAN-1"].cleared_for_execution is True


def test_graph_end_to_end_rejection_is_structurally_recorded():
    graph = build_graph(checkpointer=MemorySaver())
    critical = WorkPackageState(
        work_package_id="CRIT-2", description="high-risk task", risk_level=RiskLevel.CRITICAL
    )
    config = {"configurable": {"thread_id": "e2e-2"}}

    graph.invoke({"work_packages": [critical]}, config=config)
    final = graph.invoke(Command(resume="reject - unsafe as scheduled"), config=config)

    out = final["work_packages"][0]
    assert out.hitl_disposition == HitlDisposition.REJECTED
    assert out.cleared_for_execution is False
