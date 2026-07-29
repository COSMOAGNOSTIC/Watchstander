"""
Smoke tests for the assembled graph. Updated for the Send()-based HITL
restructure: the gate's result now lives on `reviewed_packages`, not
`work_packages` -- `work_packages` stays the untouched canonical input
list throughout the run. See agent_core/hitl.py and agent_core/graph.py
docstrings for why.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent_core.graph import build_graph
from agent_core.state import HitlDisposition, RiskLevel, WorkPackageState


def test_graph_module_imports_and_builds():
    graph = build_graph(checkpointer=MemorySaver())
    assert graph is not None


def test_graph_runs_end_to_end_through_deconfliction_reasoning_and_hitl():
    graph = build_graph(checkpointer=MemorySaver())
    critical = WorkPackageState(
        work_package_id="CRIT-1", description="high-risk task", risk_level=RiskLevel.CRITICAL
    )
    clean = WorkPackageState(work_package_id="CLEAN-1", description="routine task")
    config = {"configurable": {"thread_id": "e2e-1"}}

    paused = graph.invoke(
        {"work_packages": [critical, clean], "reviewed_packages": []}, config=config
    )
    assert "__interrupt__" in paused

    final = graph.invoke(Command(resume="approve"), config=config)
    packages = {wp.work_package_id: wp for wp in final["reviewed_packages"]}

    assert packages["CRIT-1"].hitl_disposition == HitlDisposition.APPROVED
    assert packages["CRIT-1"].cleared_for_execution is True
    assert packages["CLEAN-1"].hitl_disposition is None
    assert packages["CLEAN-1"].cleared_for_execution is True


def test_graph_end_to_end_rejection_is_structurally_recorded():
    graph = build_graph(checkpointer=MemorySaver())
    critical = WorkPackageState(
        work_package_id="CRIT-2", description="high-risk task", risk_level=RiskLevel.CRITICAL
    )
    config = {"configurable": {"thread_id": "e2e-2"}}

    graph.invoke({"work_packages": [critical], "reviewed_packages": []}, config=config)
    final = graph.invoke(Command(resume="reject - unsafe as scheduled"), config=config)

    out = final["reviewed_packages"][0]
    assert out.hitl_disposition == HitlDisposition.REJECTED
    assert out.cleared_for_execution is False


def test_graph_reviews_two_packages_independently():
    graph = build_graph(checkpointer=MemorySaver())
    a = WorkPackageState(
        work_package_id="CRIT-A", description="task a", risk_level=RiskLevel.CRITICAL
    )
    b = WorkPackageState(
        work_package_id="CRIT-B", description="task b", risk_level=RiskLevel.CRITICAL
    )
    config = {"configurable": {"thread_id": "parallel-1"}}

    paused = graph.invoke(
        {"work_packages": [a, b], "reviewed_packages": []}, config=config
    )
    interrupts = paused["__interrupt__"]
    assert len(interrupts) == 2

    resume_map = {
        i.id: ("approve" if i.value["work_package_id"] == "CRIT-A" else "reject - schedule conflict")
        for i in interrupts
    }

    final = graph.invoke(Command(resume=resume_map), config=config)
    reviewed = {wp.work_package_id: wp for wp in final["reviewed_packages"]}

    assert reviewed["CRIT-A"].hitl_disposition == HitlDisposition.APPROVED
    assert reviewed["CRIT-A"].cleared_for_execution is True
    assert reviewed["CRIT-B"].hitl_disposition == HitlDisposition.REJECTED
    assert reviewed["CRIT-B"].cleared_for_execution is False
