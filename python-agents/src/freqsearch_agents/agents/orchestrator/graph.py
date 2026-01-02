"""Single-iteration LangGraph for optimization.

This module creates a LINEAR graph (no loops) that handles exactly
one optimization iteration. The external runner manages iteration looping.

Graph flow:
    validate_and_engineer → submit_backtest → wait_for_result → invoke_analyst → decide_next → END
"""

from langgraph.graph import END, StateGraph

import structlog

from ...core.state import SingleIterationState
from .iteration_nodes import (
    validate_and_engineer_node,
    submit_backtest_node,
    wait_for_result_node,
    invoke_analyst_node,
    decide_next_node,
)

logger = structlog.get_logger(__name__)


def create_single_iteration_graph() -> StateGraph:
    """Create a LINEAR graph for a single optimization iteration.

    This graph has NO internal loops. Each invocation handles exactly
    one iteration cycle:
    1. validate_and_engineer: Generate/evolve code with internal validation retry
    2. submit_backtest: Submit to backend for backtesting
    3. wait_for_result: Poll until backtest completes
    4. invoke_analyst: Analyze results and make decision
    5. decide_next: Determine termination and best tracking

    Returns:
        Compiled StateGraph (no checkpointer needed - state managed externally)
    """
    workflow = StateGraph(SingleIterationState)

    # Add nodes
    workflow.add_node("validate_and_engineer", validate_and_engineer_node)
    workflow.add_node("submit_backtest", submit_backtest_node)
    workflow.add_node("wait_for_result", wait_for_result_node)
    workflow.add_node("invoke_analyst", invoke_analyst_node)
    workflow.add_node("decide_next", decide_next_node)

    # Linear flow - NO LOOPS
    workflow.set_entry_point("validate_and_engineer")
    workflow.add_edge("validate_and_engineer", "submit_backtest")
    workflow.add_edge("submit_backtest", "wait_for_result")
    workflow.add_edge("wait_for_result", "invoke_analyst")
    workflow.add_edge("invoke_analyst", "decide_next")
    workflow.add_edge("decide_next", END)

    # No checkpointer - state is managed externally by the runner
    return workflow.compile()
