"""Analyst Agent - LangGraph definition.

The Analyst Agent is responsible for:
1. Analyzing backtest results in depth
2. Identifying issues and root causes
3. Making evolution decisions (approve, modify, archive)
4. Generating specific modification suggestions

Decisions:
- READY_FOR_LIVE: Strategy meets all criteria for live trading
- NEEDS_MODIFICATION: Strategy has potential but needs changes
- ARCHIVE: Strategy should be discarded
"""

from typing import Any, Literal

from langgraph.graph import END, StateGraph

import structlog

from ...core.state import AnalystState
from ...schemas.diagnosis import DiagnosisStatus
from .nodes import (
    compute_metrics_node,
    analyze_trades_node,
    generate_diagnosis_node,
    submit_decision_node,
)

logger = structlog.get_logger(__name__)


def route_decision(state: AnalystState) -> Literal["approve", "modify", "archive"]:
    """Route to appropriate submission based on decision.

    Args:
        state: Current agent state

    Returns:
        Route key based on decision
    """
    decision = state["decision"]

    if decision == DiagnosisStatus.READY_FOR_LIVE.value:
        return "approve"
    elif decision == DiagnosisStatus.NEEDS_MODIFICATION.value:
        return "modify"
    else:
        return "archive"


def create_analyst_agent() -> StateGraph:
    """Create the Analyst Agent LangGraph.

    The Analyst Agent workflow:
    1. compute_metrics: Calculate advanced performance metrics
    2. analyze_trades: Analyze winning and losing trades
    3. generate_diagnosis: Use LLM to diagnose issues and make decision
    4. submit_decision: Publish appropriate event based on decision

    Returns:
        Compiled LangGraph
    """
    workflow = StateGraph(AnalystState)

    # Add nodes
    workflow.add_node("compute_metrics", compute_metrics_node)
    workflow.add_node("analyze_trades", analyze_trades_node)
    workflow.add_node("generate_diagnosis", generate_diagnosis_node)
    workflow.add_node("submit_decision", submit_decision_node)

    # Entry point
    workflow.set_entry_point("compute_metrics")

    # Linear flow
    workflow.add_edge("compute_metrics", "analyze_trades")
    workflow.add_edge("analyze_trades", "generate_diagnosis")
    workflow.add_edge("generate_diagnosis", "submit_decision")
    workflow.add_edge("submit_decision", END)

    return workflow.compile()


async def run_analyst(
    backtest_result: dict[str, Any],
    strategy_code: str | None = None,
) -> dict[str, Any]:
    """Run the Analyst Agent to analyze a backtest result.

    Args:
        backtest_result: Backtest result data from Go backend
        strategy_code: Optional strategy code for deeper analysis

    Returns:
        Final state with diagnosis and decision
    """
    logger.info(
        "Starting Analyst Agent",
        job_id=backtest_result.get("job_id"),
        strategy=backtest_result.get("strategy_name"),
    )

    agent = create_analyst_agent()

    # Initialize state
    initial_state: AnalystState = {
        "messages": [],
        "job_id": backtest_result.get("job_id", ""),
        "strategy_id": backtest_result.get("strategy_id", ""),
        "backtest_result": backtest_result,
        "metrics": {},
        "winning_trades": [],
        "losing_trades": [],
        "trade_context": "",
        "issues": [],
        "root_causes": [],
        "decision": "",
        "confidence": 0.0,
        "suggestion_type": None,
        "suggestion_description": None,
        "target_metrics": [],
    }

    # Add strategy code if provided
    if strategy_code:
        initial_state["backtest_result"]["strategy_code"] = strategy_code

    # Run the agent
    final_state = await agent.ainvoke(initial_state)

    logger.info(
        "Analyst Agent completed",
        strategy=backtest_result.get("strategy_name"),
        decision=final_state["decision"],
        confidence=final_state["confidence"],
    )

    return final_state
