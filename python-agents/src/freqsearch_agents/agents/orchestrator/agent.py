"""Orchestrator Agent - LangGraph definition.

The Orchestrator Agent coordinates the full optimization loop:
1. initialize_run: Set up optimization run state
2. invoke_engineer: Generate/evolve strategy code
3. submit_backtest: Send to Go backend via gRPC
4. wait_for_result: Poll until backtest completes
5. invoke_analyst: Analyze results and make decision
6. process_decision: Update best result, determine next action
7. Route based on decision:
   - iterate: Increment iteration and loop back to engineer
   - complete: Mark optimization complete and end
   - fail: Handle failure and end

The loop continues until:
- Analyst approves strategy (READY_FOR_LIVE)
- Maximum iterations reached
- Strategy archived
- Error occurs
"""

from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

import structlog

from ...core.state import OrchestratorState
from ...schemas.diagnosis import DiagnosisStatus
from .nodes import (
    initialize_run_node,
    invoke_engineer_node,
    submit_backtest_node,
    wait_for_result_node,
    invoke_analyst_node,
    process_decision_node,
    increment_iteration_node,
    complete_optimization_node,
    handle_failure_node,
)

logger = structlog.get_logger(__name__)


def should_continue(
    state: OrchestratorState,
) -> Literal["continue", "complete", "fail"]:
    """Determine if optimization should continue, complete, or fail.

    Args:
        state: Current orchestrator state

    Returns:
        "continue" to proceed with next iteration
        "complete" to finalize optimization
        "fail" to handle failure
    """
    # Check for errors first
    if state.get("errors") and len(state["errors"]) > 0:
        return "fail"

    # Check termination flag
    if state.get("terminated", False):
        termination_reason = state.get("termination_reason", "unknown")

        # Determine if this is a success or failure termination
        if termination_reason in ["approved", "max_iterations_reached"]:
            return "complete"
        else:
            return "fail"

    return "continue"


def route_after_decision(
    state: OrchestratorState,
) -> Literal["iterate", "complete", "archive", "fail"]:
    """Route based on analyst decision and iteration status.

    Args:
        state: Current orchestrator state

    Returns:
        Route key for next step
    """
    # Check for errors
    if state.get("errors") and len(state["errors"]) > 0:
        return "fail"

    decision = state.get("analyst_decision")
    iteration = state["current_iteration"]
    max_iterations = state["max_iterations"]

    # Strategy approved for live trading
    if decision == DiagnosisStatus.READY_FOR_LIVE.value:
        logger.info("Strategy approved - completing optimization")
        return "complete"

    # Maximum iterations reached
    if iteration >= max_iterations - 1:
        logger.info("Maximum iterations reached - completing optimization")
        return "complete"

    # Strategy should be archived
    if decision == DiagnosisStatus.ARCHIVE.value:
        logger.info("Strategy archived by analyst")
        return "archive"

    # Strategy needs modification - iterate
    if decision == DiagnosisStatus.NEEDS_MODIFICATION.value:
        if state.get("analyst_feedback") is None:
            logger.error("No feedback for modification - failing")
            return "fail"
        logger.info("Strategy needs modification - iterating")
        return "iterate"

    # Unknown decision
    logger.warning("Unknown analyst decision", decision=decision)
    return "fail"


def create_orchestrator_agent() -> StateGraph:
    """Create the Orchestrator Agent LangGraph.

    The Orchestrator workflow:
    1. initialize_run: Load config and set up initial state
    2. invoke_engineer: Call Engineer Agent to generate/evolve code
    3. submit_backtest: Submit to Go backend via gRPC
    4. wait_for_result: Poll until backtest completes
    5. invoke_analyst: Call Analyst Agent to analyze result
    6. process_decision: Update best result, determine next action
    7. Route based on decision:
       - iterate: increment_iteration → invoke_engineer (loop)
       - complete: complete_optimization → END
       - archive: complete_optimization → END (could implement alternatives)
       - fail: handle_failure → END

    Returns:
        Compiled LangGraph with memory checkpointing
    """
    workflow = StateGraph(OrchestratorState)

    # Add nodes
    workflow.add_node("initialize", initialize_run_node)
    workflow.add_node("invoke_engineer", invoke_engineer_node)
    workflow.add_node("submit_backtest", submit_backtest_node)
    workflow.add_node("wait_for_result", wait_for_result_node)
    workflow.add_node("invoke_analyst", invoke_analyst_node)
    workflow.add_node("process_decision", process_decision_node)
    workflow.add_node("increment_iteration", increment_iteration_node)
    workflow.add_node("complete", complete_optimization_node)
    workflow.add_node("handle_failure", handle_failure_node)

    # Entry point
    workflow.set_entry_point("initialize")

    # Linear flow from initialization through first iteration
    workflow.add_edge("initialize", "invoke_engineer")
    workflow.add_edge("invoke_engineer", "submit_backtest")
    workflow.add_edge("submit_backtest", "wait_for_result")
    workflow.add_edge("wait_for_result", "invoke_analyst")
    workflow.add_edge("invoke_analyst", "process_decision")

    # Conditional routing after decision processing
    workflow.add_conditional_edges(
        "process_decision",
        route_after_decision,
        {
            "iterate": "increment_iteration",
            "complete": "complete",
            "archive": "complete",  # Could route to alternative strategy logic
            "fail": "handle_failure",
        },
    )

    # Iteration loop: increment → engineer
    workflow.add_edge("increment_iteration", "invoke_engineer")

    # Terminal nodes
    workflow.add_edge("complete", END)
    workflow.add_edge("handle_failure", END)

    # Use memory checkpointer for state persistence across iterations
    return workflow.compile(checkpointer=MemorySaver())


async def run_orchestrator(
    optimization_run_id: str,
    base_strategy_id: str,
    max_iterations: int = 10,
    thread_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the Orchestrator Agent to execute an optimization loop.

    Args:
        optimization_run_id: Unique ID for this optimization run
        base_strategy_id: Strategy to optimize
        max_iterations: Maximum optimization iterations (default: 10)
        thread_id: Optional thread ID for checkpointing
        config: Optional configuration containing backtest parameters, etc.

    Returns:
        Final state with best strategy and results

    Example:
        ```python
        result = await run_orchestrator(
            optimization_run_id="opt_abc123",
            base_strategy_id="strategy_xyz",
            max_iterations=10,
        )

        if result["terminated"] and result["termination_reason"] == "approved":
            print(f"Best strategy: {result['best_strategy_id']}")
            print(f"Sharpe ratio: {result['best_sharpe']}")
        ```
    """
    logger.info(
        "Starting Orchestrator Agent",
        run_id=optimization_run_id,
        base_strategy=base_strategy_id,
        max_iterations=max_iterations,
    )

    agent = create_orchestrator_agent()

    # Initialize state
    initial_state: OrchestratorState = {
        "messages": [],
        "optimization_run_id": optimization_run_id,
        "base_strategy_id": base_strategy_id,
        "current_strategy_id": base_strategy_id,
        "current_iteration": 0,
        "max_iterations": max_iterations,
        "best_strategy_id": None,
        "best_result": None,
        "best_sharpe": float("-inf"),
        "current_backtest_job_id": None,
        "current_result": None,
        "analyst_decision": None,
        "analyst_feedback": None,
        "terminated": False,
        "termination_reason": None,
        "errors": [],
    }

    # Configuration for LangGraph
    graph_config = {
        "configurable": {
            "thread_id": thread_id or f"orchestrator-{optimization_run_id}",
        }
    }

    # Merge with custom config if provided
    if config:
        graph_config.update(config)

    # Run the orchestrator
    try:
        final_state = await agent.ainvoke(initial_state, config=graph_config)

        logger.info(
            "Orchestrator completed",
            run_id=optimization_run_id,
            iterations=final_state["current_iteration"] + 1,
            best_sharpe=final_state["best_sharpe"],
            termination_reason=final_state.get("termination_reason"),
        )

        return final_state

    except Exception as e:
        logger.exception(
            "Orchestrator failed with exception",
            run_id=optimization_run_id,
            error=str(e),
        )

        # Return failure state
        return {
            **initial_state,
            "terminated": True,
            "termination_reason": "orchestrator_exception",
            "errors": [f"Orchestrator exception: {str(e)}"],
        }


async def run_orchestrator_streaming(
    optimization_run_id: str,
    base_strategy_id: str,
    max_iterations: int = 10,
    thread_id: str | None = None,
    config: dict[str, Any] | None = None,
):
    """Run orchestrator with streaming updates for real-time monitoring.

    Yields state updates after each node execution.

    Args:
        optimization_run_id: Unique ID for this optimization run
        base_strategy_id: Strategy to optimize
        max_iterations: Maximum optimization iterations
        thread_id: Optional thread ID for checkpointing
        config: Optional configuration

    Yields:
        State updates after each node execution

    Example:
        ```python
        async for update in run_orchestrator_streaming(
            optimization_run_id="opt_abc123",
            base_strategy_id="strategy_xyz",
        ):
            print(f"Node: {update['node']}")
            print(f"Iteration: {update['state']['current_iteration']}")
            print(f"Best Sharpe: {update['state']['best_sharpe']}")
        ```
    """
    logger.info(
        "Starting Orchestrator Agent (streaming)",
        run_id=optimization_run_id,
        base_strategy=base_strategy_id,
        max_iterations=max_iterations,
    )

    agent = create_orchestrator_agent()

    # Initialize state
    initial_state: OrchestratorState = {
        "messages": [],
        "optimization_run_id": optimization_run_id,
        "base_strategy_id": base_strategy_id,
        "current_strategy_id": base_strategy_id,
        "current_iteration": 0,
        "max_iterations": max_iterations,
        "best_strategy_id": None,
        "best_result": None,
        "best_sharpe": float("-inf"),
        "current_backtest_job_id": None,
        "current_result": None,
        "analyst_decision": None,
        "analyst_feedback": None,
        "terminated": False,
        "termination_reason": None,
        "errors": [],
    }

    # Configuration
    graph_config = {
        "configurable": {
            "thread_id": thread_id or f"orchestrator-{optimization_run_id}",
        }
    }

    if config:
        graph_config.update(config)

    # Stream execution
    try:
        async for update in agent.astream(initial_state, config=graph_config):
            yield update

        logger.info(
            "Orchestrator streaming completed",
            run_id=optimization_run_id,
        )

    except Exception as e:
        logger.exception(
            "Orchestrator streaming failed",
            run_id=optimization_run_id,
            error=str(e),
        )
        raise
