"""
Watchstander agent graph assembly.

    entry -> deconfliction_node -> hitl_gate_node -> END

The graph is intentionally small at v1: geometry-based deconfliction
feeding a mandatory human review gate. RAG-grounded rationale
generation (citing case data / OSHA subparts) is a planned addition
that sits between deconfliction and the HITL gate, not a replacement
for either.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from agent_core.deconfliction import deconfliction_node
from agent_core.hitl import hitl_gate_node
from agent_core.state import WorkPackageState


class GraphState(TypedDict):
    work_packages: list[WorkPackageState]
    requires_hitl_review: bool


def build_graph(checkpointer: SqliteSaver | None = None):
    graph = StateGraph(GraphState)

    graph.add_node("deconfliction", deconfliction_node)
    graph.add_node("hitl_gate", hitl_gate_node)

    graph.set_entry_point("deconfliction")
    graph.add_edge("deconfliction", "hitl_gate")
    graph.add_edge("hitl_gate", END)

    return graph.compile(checkpointer=checkpointer)
