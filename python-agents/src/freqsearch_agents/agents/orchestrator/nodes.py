"""Orchestrator Agent node implementations."""

import asyncio
from typing import Any

import structlog

from ...core.state import OrchestratorState
from ...core.messaging import publish_event, Events
from ...agents.engineer.agent import run_engineer
from ...agents.analyst.agent import run_analyst
from ...schemas.diagnosis import DiagnosisStatus

logger = structlog.get_logger(__name__)


async def initialize_run_node(
    state: OrchestratorState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Initialize optimization run and load configuration.

    Sets up initial state for the optimization loop.

    Args:
        state: Current orchestrator state
        config: Optional configuration containing optimization parameters

    Returns:
        State update with initialized values
    """
    run_id = state["optimization_run_id"]
    base_strategy_id = state["base_strategy_id"]

    logger.info(
        "Initializing optimization run",
        run_id=run_id,
        base_strategy=base_strategy_id,
        max_iterations=state["max_iterations"],
    )

    # Publish initialization event
    await publish_event(
        "optimization.iteration.started",
        {
            "optimization_run_id": run_id,
            "base_strategy_id": base_strategy_id,
            "iteration": 0,
            "max_iterations": state["max_iterations"],
        },
    )

    return {
        "current_iteration": 0,
        "best_sharpe": float("-inf"),
        "errors": [],
        "terminated": False,
    }


async def invoke_engineer_node(
    state: OrchestratorState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke Engineer Agent to generate or evolve strategy code.

    Calls the Engineer Agent with current context:
    - First iteration: process base strategy
    - Subsequent iterations: evolve based on analyst feedback

    Args:
        state: Current orchestrator state
        config: Optional configuration

    Returns:
        State update with engineer results
    """
    iteration = state["current_iteration"]
    run_id = state["optimization_run_id"]

    logger.info(
        "Invoking Engineer Agent",
        run_id=run_id,
        iteration=iteration,
    )

    try:
        # Prepare engineer input
        if iteration == 0:
            # First iteration: process base strategy
            # In real implementation, fetch strategy data from backend
            engineer_input = {
                "id": state["base_strategy_id"],
                "name": f"strategy_{state['base_strategy_id']}",
                "code": "# Base strategy code from backend",
            }
            mode = "new"
        else:
            # Subsequent iterations: evolve based on feedback
            if state["analyst_feedback"] is None:
                logger.error("No analyst feedback for evolution", iteration=iteration)
                return {
                    "errors": state["errors"] + ["No analyst feedback for evolution"],
                    "terminated": True,
                    "termination_reason": "missing_feedback",
                }

            engineer_input = {
                "id": state["current_strategy_id"],
                "name": f"strategy_{state['current_strategy_id']}_v{iteration}",
                "code": state["current_result"].get("strategy_code", ""),
                "diagnosis": state["analyst_feedback"],
            }
            mode = "evolve"

        # Run Engineer Agent
        engineer_result = await run_engineer(
            input_data=engineer_input,
            mode=mode,
            thread_id=f"{run_id}-engineer-{iteration}",
        )

        # Check if engineer succeeded
        if not engineer_result.get("validation_passed", False):
            logger.error(
                "Engineer failed to generate valid code",
                iteration=iteration,
                errors=engineer_result.get("validation_errors", []),
            )
            return {
                "errors": state["errors"] + engineer_result.get("validation_errors", []),
                "terminated": True,
                "termination_reason": "engineer_validation_failed",
            }

        # Extract generated strategy ID (would come from submit_node in real implementation)
        generated_strategy_id = f"strategy_{run_id}_i{iteration}"

        logger.info(
            "Engineer completed successfully",
            iteration=iteration,
            strategy_id=generated_strategy_id,
        )

        return {
            "current_strategy_id": generated_strategy_id,
            "messages": state["messages"] + [engineer_result],
        }

    except Exception as e:
        logger.exception("Engineer node failed", iteration=iteration, error=str(e))
        return {
            "errors": state["errors"] + [f"Engineer error: {str(e)}"],
            "terminated": True,
            "termination_reason": "engineer_exception",
        }


async def submit_backtest_node(
    state: OrchestratorState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Submit backtest to Go backend via gRPC.

    Sends the current strategy for backtesting.

    Args:
        state: Current orchestrator state
        config: Optional configuration containing gRPC settings

    Returns:
        State update with backtest job ID
    """
    strategy_id = state["current_strategy_id"]
    iteration = state["current_iteration"]
    run_id = state["optimization_run_id"]

    logger.info(
        "Submitting backtest",
        strategy=strategy_id,
        iteration=iteration,
    )

    try:
        # NOTE: This is a placeholder for actual gRPC client implementation
        # In real implementation, would use:
        # from ...grpc_client import FreqSearchClient
        # client = FreqSearchClient("localhost:50051")
        # job = await client.submit_backtest(strategy_id, backtest_config)

        # For now, simulate job submission
        job_id = f"job_{run_id}_i{iteration}_{strategy_id}"

        logger.info(
            "Backtest submitted",
            job_id=job_id,
            strategy=strategy_id,
        )

        # Publish backtest submitted event
        await publish_event(
            Events.BACKTEST_SUBMITTED,
            {
                "job_id": job_id,
                "strategy_id": strategy_id,
                "optimization_run_id": run_id,
                "iteration": iteration,
            },
        )

        return {
            "current_backtest_job_id": job_id,
        }

    except Exception as e:
        logger.exception("Failed to submit backtest", strategy=strategy_id, error=str(e))
        return {
            "errors": state["errors"] + [f"Backtest submission error: {str(e)}"],
            "terminated": True,
            "termination_reason": "backtest_submission_failed",
        }


async def wait_for_result_node(
    state: OrchestratorState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Poll/wait for backtest to complete.

    Waits for the backtest job to reach COMPLETED or FAILED status.

    Args:
        state: Current orchestrator state
        config: Optional configuration with polling parameters

    Returns:
        State update with backtest result
    """
    job_id = state["current_backtest_job_id"]
    if not job_id:
        logger.error("No backtest job ID to wait for")
        return {
            "errors": state["errors"] + ["No backtest job ID"],
            "terminated": True,
            "termination_reason": "missing_job_id",
        }

    logger.info("Waiting for backtest to complete", job_id=job_id)

    # Configuration
    poll_interval = config.get("poll_interval", 5.0) if config else 5.0
    max_wait_time = config.get("max_wait_time", 3600.0) if config else 3600.0
    elapsed = 0.0

    try:
        # NOTE: This is a placeholder for actual gRPC polling
        # In real implementation, would use:
        # from ...grpc_client import FreqSearchClient
        # client = FreqSearchClient("localhost:50051")
        # while elapsed < max_wait_time:
        #     job = await client.get_backtest_job(job_id)
        #     if job.status in ["COMPLETED", "FAILED"]:
        #         break
        #     await asyncio.sleep(poll_interval)
        #     elapsed += poll_interval

        # Simulate polling
        while elapsed < max_wait_time:
            # In real implementation, check job status
            # For now, simulate completion after short wait
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            # Simulate completion after first poll
            if elapsed >= poll_interval:
                break

        # Simulate fetching result
        # In real implementation, this would be the actual backtest result from gRPC
        result = {
            "job_id": job_id,
            "strategy_id": state["current_strategy_id"],
            "status": "COMPLETED",
            "total_trades": 150,
            "profit_pct": 12.5,
            "win_rate": 0.58,
            "max_drawdown_pct": 8.3,
            "sharpe_ratio": 1.85,
            "strategy_code": "# Generated strategy code",
            "trades": [],  # Full trade list would be here
        }

        logger.info(
            "Backtest completed",
            job_id=job_id,
            sharpe=result.get("sharpe_ratio"),
            profit_pct=result.get("profit_pct"),
        )

        # Publish completion event
        await publish_event(
            Events.BACKTEST_COMPLETED,
            {
                "job_id": job_id,
                "strategy_id": state["current_strategy_id"],
                "success": True,
                "total_trades": result.get("total_trades"),
                "profit_pct": result.get("profit_pct"),
                "sharpe_ratio": result.get("sharpe_ratio"),
            },
        )

        return {
            "current_result": result,
        }

    except Exception as e:
        logger.exception("Failed to get backtest result", job_id=job_id, error=str(e))
        return {
            "errors": state["errors"] + [f"Backtest wait error: {str(e)}"],
            "terminated": True,
            "termination_reason": "backtest_wait_failed",
        }


async def invoke_analyst_node(
    state: OrchestratorState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke Analyst Agent to analyze backtest result.

    Calls the Analyst Agent to make a decision about the strategy.

    Args:
        state: Current orchestrator state
        config: Optional configuration

    Returns:
        State update with analyst decision and feedback
    """
    result = state["current_result"]
    if not result:
        logger.error("No backtest result to analyze")
        return {
            "errors": state["errors"] + ["No backtest result"],
            "terminated": True,
            "termination_reason": "missing_result",
        }

    logger.info(
        "Invoking Analyst Agent",
        job_id=result.get("job_id"),
        iteration=state["current_iteration"],
    )

    try:
        # Enhance backtest result with optimization context
        enhanced_result = {
            **result,
            "optimization_run_id": state["optimization_run_id"],
            "current_iteration": state["current_iteration"],
            "max_iterations": state["max_iterations"],
        }

        # Run Analyst Agent
        analyst_result = await run_analyst(
            backtest_result=enhanced_result,
            strategy_code=result.get("strategy_code"),
        )

        decision = analyst_result.get("decision", "")
        confidence = analyst_result.get("confidence", 0.0)

        logger.info(
            "Analyst completed",
            decision=decision,
            confidence=confidence,
            iteration=state["current_iteration"],
        )

        # Prepare feedback for next iteration if needed
        feedback = None
        if decision == DiagnosisStatus.NEEDS_MODIFICATION.value:
            feedback = {
                "suggestion_type": analyst_result.get("suggestion_type"),
                "suggestion_description": analyst_result.get("suggestion_description"),
                "target_metrics": analyst_result.get("target_metrics", []),
                "current_metrics": analyst_result.get("metrics", {}),
                "issues": analyst_result.get("issues", []),
                "root_causes": analyst_result.get("root_causes", []),
            }

        return {
            "analyst_decision": decision,
            "analyst_feedback": feedback,
            "messages": state["messages"] + [analyst_result],
        }

    except Exception as e:
        logger.exception("Analyst node failed", error=str(e))
        return {
            "errors": state["errors"] + [f"Analyst error: {str(e)}"],
            "terminated": True,
            "termination_reason": "analyst_exception",
        }


async def process_decision_node(
    state: OrchestratorState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Process analyst decision and update best result if improved.

    Determines the next action based on analyst decision and iteration count.

    Args:
        state: Current orchestrator state
        config: Optional configuration

    Returns:
        State update with decision processing results
    """
    decision = state["analyst_decision"]
    current_result = state["current_result"]
    iteration = state["current_iteration"]
    max_iterations = state["max_iterations"]

    if not current_result:
        logger.error("No current result to process")
        return {"errors": state["errors"] + ["No current result"]}

    current_sharpe = current_result.get("sharpe_ratio", float("-inf"))

    logger.info(
        "Processing decision",
        decision=decision,
        iteration=iteration,
        current_sharpe=current_sharpe,
        best_sharpe=state["best_sharpe"],
    )

    # Update best result if current is better
    updates = {}
    if current_sharpe > state["best_sharpe"]:
        logger.info(
            "New best strategy found",
            sharpe=current_sharpe,
            previous_best=state["best_sharpe"],
        )
        updates.update({
            "best_strategy_id": state["current_strategy_id"],
            "best_result": current_result,
            "best_sharpe": current_sharpe,
        })

        # Publish new best event
        await publish_event(
            "optimization.new_best",
            {
                "optimization_run_id": state["optimization_run_id"],
                "iteration": iteration,
                "strategy_id": state["current_strategy_id"],
                "sharpe_ratio": current_sharpe,
                "profit_pct": current_result.get("profit_pct"),
            },
        )

    # Check if we should terminate
    if decision == DiagnosisStatus.READY_FOR_LIVE.value:
        logger.info("Strategy approved for live trading", iteration=iteration)
        updates["terminated"] = True
        updates["termination_reason"] = "approved"

    elif iteration >= max_iterations - 1:
        logger.info(
            "Maximum iterations reached",
            iteration=iteration,
            max_iterations=max_iterations,
        )
        updates["terminated"] = True
        updates["termination_reason"] = "max_iterations_reached"

    elif decision == DiagnosisStatus.ARCHIVE.value:
        logger.info("Strategy archived by analyst", iteration=iteration)
        # Could implement alternative strategy logic here
        # For now, treat as termination
        updates["terminated"] = True
        updates["termination_reason"] = "archived"

    # Publish iteration completed event
    await publish_event(
        "optimization.iteration.completed",
        {
            "optimization_run_id": state["optimization_run_id"],
            "iteration": iteration,
            "decision": decision,
            "sharpe_ratio": current_sharpe,
            "is_best": current_sharpe > state.get("best_sharpe", float("-inf")),
        },
    )

    return updates


async def increment_iteration_node(
    state: OrchestratorState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Increment iteration counter for next loop.

    Args:
        state: Current orchestrator state
        config: Optional configuration

    Returns:
        State update with incremented iteration
    """
    next_iteration = state["current_iteration"] + 1

    logger.info(
        "Incrementing iteration",
        current=state["current_iteration"],
        next=next_iteration,
    )

    return {
        "current_iteration": next_iteration,
        "current_backtest_job_id": None,
        "current_result": None,
        "analyst_decision": None,
    }


async def complete_optimization_node(
    state: OrchestratorState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark optimization as complete and publish final results.

    Args:
        state: Current orchestrator state
        config: Optional configuration

    Returns:
        State update with completion status
    """
    run_id = state["optimization_run_id"]
    termination_reason = state.get("termination_reason", "unknown")

    logger.info(
        "Completing optimization run",
        run_id=run_id,
        reason=termination_reason,
        iterations=state["current_iteration"] + 1,
        best_sharpe=state["best_sharpe"],
    )

    # Prepare final summary
    summary = {
        "optimization_run_id": run_id,
        "base_strategy_id": state["base_strategy_id"],
        "total_iterations": state["current_iteration"] + 1,
        "termination_reason": termination_reason,
        "best_strategy_id": state["best_strategy_id"],
        "best_sharpe": state["best_sharpe"],
    }

    if state["best_result"]:
        summary.update({
            "best_profit_pct": state["best_result"].get("profit_pct"),
            "best_win_rate": state["best_result"].get("win_rate"),
            "best_max_drawdown": state["best_result"].get("max_drawdown_pct"),
        })

    # Publish completion event
    await publish_event(
        "optimization.completed",
        summary,
    )

    # In real implementation, would call gRPC to mark optimization complete:
    # from ...grpc_client import FreqSearchClient
    # client = FreqSearchClient("localhost:50051")
    # await client.control_optimization(run_id, "complete")

    logger.info("Optimization completed successfully", **summary)

    return {"terminated": True}


async def handle_failure_node(
    state: OrchestratorState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Handle optimization failure and publish failure event.

    Args:
        state: Current orchestrator state
        config: Optional configuration

    Returns:
        State update with failure status
    """
    run_id = state["optimization_run_id"]
    errors = state.get("errors", [])
    termination_reason = state.get("termination_reason", "unknown_error")

    logger.error(
        "Optimization failed",
        run_id=run_id,
        reason=termination_reason,
        errors=errors,
    )

    # Publish failure event
    await publish_event(
        "optimization.failed",
        {
            "optimization_run_id": run_id,
            "base_strategy_id": state["base_strategy_id"],
            "iteration": state["current_iteration"],
            "reason": termination_reason,
            "errors": errors,
        },
    )

    return {"terminated": True}
