"""
Watchstander agent graph assembly.

    entry -> deconfliction_node -> reasoning_node -> hitl_prepare
             -> [hitl_gate_single x N, fanned out via Send()] -> END

Phase change (see agent_core/hitl.py docstring): the HITL gate used to be
a single node looping over every work package needing review, calling
interrupt() once per package inside that loop. hitl_prepare now
partitions packages that don't need review (written straight to
reviewed_packages) from packages that do (fanned out as independent
Send() branches to hitl_gate_single, one interrupt() each, checkpointed
and reviewable independently).

Consumers: the final result now lives on `reviewed_packages`, not
`work_packages` -- `work_packages` stays untouched as the canonical
input list throughout the run.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from agent_core.deconfliction import deconfliction_node
from agent_core.hitl import hitl_gate_single_node, hitl_prepare_node, hitl_route
from agent_core.reasoning import reasoning_node
from agent_core.state import WorkPackageState


class GraphState(TypedDict):
    work_packages: list[WorkPackageState]
    reviewed_packages: Annotated[list[WorkPackageState], operator.add]
    requires_hitl_review: bool


def build_graph(checkpointer: SqliteSaver | None = None):
    graph = StateGraph(GraphState)

    graph.add_node("deconfliction", deconfliction_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("hitl_prepare", hitl_prepare_node)
    graph.add_node("hitl_gate_single", hitl_gate_single_node)

    graph.set_entry_point("deconfliction")
    graph.add_edge("deconfliction", "reasoning")
    graph.add_edge("reasoning", "hitl_prepare")
    graph.add_conditional_edges(
        "hitl_prepare",
        hitl_route,
        ["hitl_gate_single", END],
    )
    graph.add_edge("hitl_gate_single", END)

    return graph.compile(checkpointer=checkpointer)
