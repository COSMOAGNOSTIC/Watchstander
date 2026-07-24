"""
Watchstander agent graph assembly.

    entry -> deconfliction_node -> reasoning_node -> hitl_gate_node -> END

The deterministic deconfliction engine decides whether a conflict exists.
The reasoning node (Phase 2) never re-decides that -- it only synthesizes
the flagged conflict plus its grounded case citation into a plain-language
brief for the human reviewer. The HITL gate remains the only place
execution actually pauses for a human decision.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from agent_core.deconfliction import deconfliction_node
from agent_core.hitl import hitl_gate_node
from agent_core.reasoning import reasoning_node
from agent_core.state import WorkPackageState


class GraphState(TypedDict):
    work_packages: list[WorkPackageState]
    requires_hitl_review: bool


def build_graph(checkpointer: SqliteSaver | None = None):
    graph = StateGraph(GraphState)

    graph.add_node("deconfliction", deconfliction_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("hitl_gate", hitl_gate_node)

    graph.set_entry_point("deconfliction")
    graph.add_edge("deconfliction", "reasoning")
    graph.add_edge("reasoning", "hitl_gate")
    graph.add_edge("hitl_gate", END)

    return graph.compile(checkpointer=checkpointer)
