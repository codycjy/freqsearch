"""Orchestrator Agent node implementations."""

import asyncio
from typing import Any

import structlog

from ...agents.analyst.agent import run_analyst
from ...agents.engineer.agent import run_engineer
from ...core.messaging import Events, publish_event
from ...core.state import OrchestratorState
from ...grpc_client.client import BacktestConfig, FreqSearchClient
from ...grpc_client.client import ConnectionError as GrpcConnectionError
from ...schemas.diagnosis import DiagnosisStatus

logger = structlog.get_logger(__name__)


async def initialize_run_node(
    state: OrchestratorState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Initialize optimization run and load configuration.

    Sets up initial state for the optimization loop.
    Fetches base strategy code from backend.

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

    # Get gRPC config - check state first, then config, then default
    opt_config = state.get("optimization_config", {})
    grpc_address = opt_config.get("grpc_address", "localhost:50051")
    if config and "grpc_address" in config:
        grpc_address = config["grpc_address"]

    # Set optimization status to RUNNING
    try:
        async with FreqSearchClient(grpc_address) as client:
            await client.control_optimization(run_id, "resume")
            logger.info("Set optimization status to RUNNING", run_id=run_id)
    except Exception as e:
        logger.warning("Failed to set optimization status to RUNNING", run_id=run_id, error=str(e))

    # Publish initialization event
    await publish_event(
        Events.OPTIMIZATION_ITERATION_STARTED,
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
    - First iteration: process base strategy (fetches real code from backend)
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
        # Get gRPC configuration
        grpc_address = config.get("grpc_address", "localhost:50051") if config else "localhost:50051"

        # Prepare engineer input
        if iteration == 0:
            # First iteration: fetch and process base strategy from backend
            logger.debug("Fetching base strategy from backend", strategy_id=state["base_strategy_id"])

            async with FreqSearchClient(grpc_address) as client:
                try:
                    strategy_response = await client.get_strategy(state["base_strategy_id"])
                    strategy_data = strategy_response.get("strategy", {})
                    base_strategy_code = strategy_data.get("code", "")
                    base_strategy_name = strategy_data.get("name", f"strategy_{state['base_strategy_id']}")

                    logger.info(
                        "Base strategy fetched successfully",
                        strategy_id=state["base_strategy_id"],
                        name=base_strategy_name,
                        code_length=len(base_strategy_code),
                    )
                except Exception as e:
                    logger.error("Failed to fetch base strategy", strategy_id=state["base_strategy_id"], error=str(e))
                    return {
                        **state,
                        "status": "failed",
                        "errors": state["errors"] + [f"Failed to fetch base strategy: {e}"],
                        "terminated": True,
                        "termination_reason": "base_strategy_fetch_failed",
                    }

            engineer_input = {
                "id": state["base_strategy_id"],
                "name": base_strategy_name,
                "code": base_strategy_code,  # Real code from backend
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

            # Get code from current_result or fall back to previous engineer_result
            previous_code = ""
            if state.get("current_result") and state["current_result"].get("strategy_code"):
                previous_code = state["current_result"]["strategy_code"]
            elif state.get("engineer_result"):
                # Fall back to engineer's generated code (useful when backtest failed)
                previous_code = state["engineer_result"].get("generated_code", "") or state["engineer_result"].get("code", "")

            engineer_input = {
                "id": state["current_strategy_id"],
                "name": f"strategy_{state['current_strategy_id']}_v{iteration}",
                "code": previous_code,
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

        logger.info(
            "Engineer completed successfully",
            iteration=iteration,
        )

        return {
            "engineer_result": engineer_result,
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

    Creates the generated strategy in the backend first,
    then submits it for backtesting.

    Args:
        state: Current orchestrator state
        config: Optional configuration containing gRPC settings

    Returns:
        State update with backtest job ID and strategy ID
    """
    iteration = state["current_iteration"]
    run_id = state["optimization_run_id"]

    logger.info(
        "Submitting backtest for iteration",
        iteration=iteration,
        run_id=run_id,
    )

    try:
        # Get gRPC configuration
        grpc_address = config.get("grpc_address", "localhost:50051") if config else "localhost:50051"

        # Get engineer result from state
        engineer_result = state.get("engineer_result")
        if not engineer_result:
            logger.error("No engineer result available")
            return {
                "errors": state["errors"] + ["No engineer result available"],
                "terminated": True,
                "termination_reason": "missing_engineer_result",
            }

        generated_code = engineer_result.get("generated_code", "") or engineer_result.get("code", "")
        if not generated_code:
            logger.error("Engineer result has no code")
            return {
                "errors": state["errors"] + ["Engineer result has no code"],
                "terminated": True,
                "termination_reason": "missing_generated_code",
            }

        # Determine base strategy name for naming
        base_strategy_id = state["base_strategy_id"]

        # Get backtest configuration from state's optimization_config or use defaults
        opt_config = state.get("optimization_config", {})
        backtest_config_data = opt_config.get("backtest_config", {})
        backtest_cfg = BacktestConfig(
            exchange=backtest_config_data.get("exchange", "binance"),
            pairs=backtest_config_data.get("pairs", ["BTC/USDT"]),
            timeframe=backtest_config_data.get("timeframe", "1h"),
            timerange_start=backtest_config_data.get("timerange_start", "20230101"),
            timerange_end=backtest_config_data.get("timerange_end", "20230131"),
            dry_run_wallet=backtest_config_data.get("dry_run_wallet", 1000.0),
            max_open_trades=backtest_config_data.get("max_open_trades", 3),
            stake_amount=backtest_config_data.get("stake_amount", "unlimited"),
        )

        # Create strategy in backend and submit backtest via gRPC
        async with FreqSearchClient(grpc_address) as client:
            # First, validate the strategy code
            try:
                validation_result = await client.validate_strategy(
                    code=generated_code,
                    name=f"strategy_iter_{iteration}",
                )

                if not validation_result.get("valid", False):
                    validation_errors = validation_result.get("errors", ["Unknown validation error"])
                    logger.warning(
                        "Strategy validation failed",
                        iteration=iteration,
                        errors=validation_errors,
                    )
                    # Return error to trigger engineer retry with feedback
                    return {
                        "backtest_error": f"Validation failed: {'; '.join(validation_errors)}",
                        "analyst_decision": "NEEDS_MODIFICATION",
                        "analyst_feedback": f"Strategy code failed validation: {'; '.join(validation_errors)}. Please fix these issues.",
                    }

                logger.info("Strategy validation passed", iteration=iteration)

            except Exception as e:
                logger.warning(
                    "Strategy validation call failed, proceeding anyway",
                    iteration=iteration,
                    error=str(e),
                )
                # Continue without validation if the service is unavailable

            # Create the new strategy in backend
            try:
                # Get base strategy name for better naming
                base_strategy_name = f"strategy_{base_strategy_id}"
                if iteration == 0:
                    # For first iteration, try to get the actual name
                    try:
                        base_response = await client.get_strategy(base_strategy_id)
                        base_strategy_name = base_response.get("strategy", {}).get("name", base_strategy_name)
                    except Exception:
                        # If we can't fetch it, just use the ID-based name
                        pass

                strategy_response = await client.create_strategy(
                    name=f"{base_strategy_name}_opt_{run_id}_iter_{iteration}",
                    code=generated_code,
                    description=f"Generated in optimization run {run_id}, iteration {iteration}",
                    parent_id=base_strategy_id if iteration == 0 else state.get("current_strategy_id"),
                )
                generated_strategy_id = strategy_response["strategy"]["id"]

                logger.info(
                    "Created strategy in backend",
                    strategy_id=generated_strategy_id,
                    iteration=iteration,
                    parent_id=base_strategy_id if iteration == 0 else state.get("current_strategy_id"),
                )
            except Exception as e:
                logger.error("Failed to create strategy in backend", iteration=iteration, error=str(e))
                return {
                    "errors": state["errors"] + [f"Failed to create strategy: {e}"],
                    "terminated": True,
                    "termination_reason": "strategy_creation_failed",
                }

            # Now submit backtest with the real strategy ID
            logger.debug(
                "Submitting backtest via gRPC",
                address=grpc_address,
                strategy_id=generated_strategy_id,
                optimization_run_id=run_id,
            )

            response = await client.submit_backtest(
                strategy_id=generated_strategy_id,
                config=backtest_cfg,
                optimization_run_id=run_id,
                priority=config.get("priority", 0) if config else 0,
            )

            job_id = response["job"]["id"]

        logger.info(
            "Backtest submitted via gRPC",
            job_id=job_id,
            strategy_id=generated_strategy_id,
        )

        # Publish backtest submitted event
        await publish_event(
            Events.BACKTEST_SUBMITTED,
            {
                "job_id": job_id,
                "strategy_id": generated_strategy_id,
                "optimization_run_id": run_id,
                "iteration": iteration,
            },
        )

        return {
            "current_strategy_id": generated_strategy_id,
            "current_backtest_job_id": job_id,
        }

    except GrpcConnectionError as e:
        logger.error("gRPC connection failed", iteration=iteration, error=str(e))
        return {
            "errors": state["errors"] + [f"gRPC connection error: {str(e)}"],
            "terminated": True,
            "termination_reason": "grpc_connection_failed",
        }
    except Exception as e:
        logger.exception("Failed to submit backtest", iteration=iteration, error=str(e))
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
    grpc_address = config.get("grpc_address", "localhost:50051") if config else "localhost:50051"
    poll_interval = config.get("poll_interval", 5.0) if config else 5.0
    max_wait_time = config.get("max_wait_time", 3600.0) if config else 3600.0
    elapsed = 0.0

    try:
        # Poll for job completion using gRPC
        async with FreqSearchClient(grpc_address) as client:
            job_status = None
            job_data = None

            while elapsed < max_wait_time:
                logger.debug("Polling backtest job status", job_id=job_id, elapsed=elapsed)

                # Get current job status
                job_data = await client.get_backtest_job(job_id)
                job_status = job_data["job"]["status"]

                logger.debug("Job status", job_id=job_id, status=job_status)

                # Check if job is in terminal state
                if job_status == "JOB_STATUS_COMPLETED":
                    logger.info("Backtest completed successfully", job_id=job_id)
                    break
                elif job_status == "JOB_STATUS_FAILED":
                    error_msg = job_data["job"].get("error_message", "Unknown error")
                    logs = job_data["job"].get("logs", "")
                    logger.warning("Backtest failed - will provide feedback to Engineer", job_id=job_id, error=error_msg)
                    # Return failed result for Analyst to review and provide feedback
                    # Don't terminate - let the optimization loop continue with feedback
                    return {
                        "current_result": {
                            "job_id": job_id,
                            "strategy_id": state["current_strategy_id"],
                            "status": "FAILED",
                            "error_message": error_msg,
                            "logs": logs,
                            "total_trades": 0,
                            "profit_pct": 0.0,
                            "win_rate": 0.0,
                            "max_drawdown_pct": 0.0,
                            "sharpe_ratio": 0.0,
                        },
                        # Do not add to errors, as this is a handled failure state
                        # "errors": state["errors"] + [f"Backtest failed: {error_msg}"],
                    }
                elif job_status == "JOB_STATUS_CANCELLED":
                    logger.warning("Backtest was cancelled", job_id=job_id)
                    return {
                        "errors": state["errors"] + ["Backtest was cancelled"],
                        "terminated": True,
                        "termination_reason": "backtest_cancelled",
                    }

                # Wait before next poll
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            # Check if we timed out
            if elapsed >= max_wait_time:
                logger.error("Backtest timeout", job_id=job_id, elapsed=elapsed)
                return {
                    "errors": state["errors"] + [f"Backtest timeout after {max_wait_time}s"],
                    "terminated": True,
                    "termination_reason": "backtest_timeout",
                }

            # Fetch full result
            logger.debug("Fetching full backtest result", job_id=job_id)
            result_response = await client.get_backtest_result(job_id)
            result_data = result_response["result"]

            # Combine job and result data
            result = {
                "job_id": job_id,
                "strategy_id": state["current_strategy_id"],
                "status": "COMPLETED",
                "total_trades": result_data.get("total_trades", 0),
                "profit_pct": result_data.get("profit_pct", 0.0),
                "win_rate": result_data.get("win_rate", 0.0),
                "max_drawdown_pct": result_data.get("max_drawdown_pct", 0.0),
                "sharpe_ratio": result_data.get("sharpe_ratio", 0.0),
                "sortino_ratio": result_data.get("sortino_ratio", 0.0),
                "calmar_ratio": result_data.get("calmar_ratio", 0.0),
                "profit_factor": result_data.get("profit_factor", 0.0),
                "winning_trades": result_data.get("winning_trades", 0),
                "losing_trades": result_data.get("losing_trades", 0),
                "avg_trade_duration_minutes": result_data.get("avg_trade_duration_minutes", 0.0),
                "avg_profit_per_trade": result_data.get("avg_profit_per_trade", 0.0),
                "best_trade_pct": result_data.get("best_trade_pct", 0.0),
                "worst_trade_pct": result_data.get("worst_trade_pct", 0.0),
                "pair_results": result_data.get("pair_results", []),
                "trades_json": result_data.get("trades_json", ""),
            }

        logger.info(
            "Backtest result fetched",
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

    except GrpcConnectionError as e:
        logger.error("gRPC connection failed during polling", job_id=job_id, error=str(e))
        return {
            "errors": state["errors"] + [f"gRPC connection error: {str(e)}"],
            "terminated": True,
            "termination_reason": "grpc_connection_failed",
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

    # Handle failed backtests directly - no need to call Analyst
    if result.get("status") == "FAILED":
        error_msg = result.get("error_message", "Unknown error")
        logs = result.get("logs", "")
        logger.warning(
            "Backtest failed - automatically requesting code fix",
            job_id=result.get("job_id"),
            iteration=state["current_iteration"],
            error=error_msg,
        )
        # Extract relevant error info from logs for Engineer
        feedback = {
            "suggestion_type": "code_fix",
            "suggestion_description": f"Fix code error: {error_msg}",
            "error_message": error_msg,
            "logs": logs[-2000:] if logs else "",  # Last 2000 chars of logs
            "issues": [error_msg],
            "root_causes": ["Strategy code contains errors that prevent execution"],
        }
        return {
            "analyst_decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
            "analyst_feedback": feedback,
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
            # Note: Not adding analyst_result to messages as it's not in LangGraph message format
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

    # Handle validation failure case - no backtest result, but needs retry
    if not current_result:
        if decision == DiagnosisStatus.NEEDS_MODIFICATION.value:
            # Validation failed, skip result processing and continue to retry
            logger.info(
                "Processing validation failure - no backtest result, will retry",
                decision=decision,
                iteration=iteration,
                feedback=state.get("analyst_feedback", "")[:100],
            )
            return {}  # No updates needed, routing will handle retry
        else:
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
            Events.OPTIMIZATION_NEW_BEST,
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
        Events.OPTIMIZATION_ITERATION_COMPLETED,
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

    # Get gRPC config
    opt_config = state.get("optimization_config", {})
    grpc_address = opt_config.get("grpc_address", "localhost:50051")
    if config and "grpc_address" in config:
        grpc_address = config["grpc_address"]

    # Set optimization status to COMPLETED
    try:
        async with FreqSearchClient(grpc_address) as client:
            # Set status to completed with metadata
            await client.control_optimization(
                run_id,
                "complete",
                termination_reason=termination_reason,
                best_strategy_id=state.get("best_strategy_id"),
            )
            logger.info("Set optimization status to COMPLETED", run_id=run_id)

            # Get the final optimization run state
            opt_run_data = await client.get_optimization_run(run_id)

            logger.info(
                "Retrieved final optimization run status",
                run_id=run_id,
                status=opt_run_data.get("run", {}).get("status"),
            )

            # Add backend status to summary
            summary["backend_status"] = opt_run_data.get("run", {}).get("status")

    except GrpcConnectionError as e:
        logger.warning(
            "Could not update/retrieve final optimization status from backend",
            run_id=run_id,
            error=str(e),
        )
        # Non-fatal: continue with completion
    except Exception as e:
        logger.warning(
            "Error updating/retrieving final optimization status",
            run_id=run_id,
            error=str(e),
        )
        # Non-fatal: continue with completion

    # Publish completion event
    await publish_event(
        Events.OPTIMIZATION_COMPLETED,
        summary,
    )

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

    # Get gRPC config
    opt_config = state.get("optimization_config", {})
    grpc_address = opt_config.get("grpc_address", "localhost:50051")
    if config and "grpc_address" in config:
        grpc_address = config["grpc_address"]

    # Set optimization status to FAILED
    try:
        async with FreqSearchClient(grpc_address) as client:
            await client.control_optimization(
                run_id,
                "fail",
                termination_reason=termination_reason,
            )
            logger.info("Set optimization status to FAILED", run_id=run_id)
    except Exception as e:
        logger.warning("Failed to set optimization status to FAILED", run_id=run_id, error=str(e))

    # Publish failure event
    await publish_event(
        Events.OPTIMIZATION_FAILED,
        {
            "optimization_run_id": run_id,
            "base_strategy_id": state["base_strategy_id"],
            "iteration": state["current_iteration"],
            "reason": termination_reason,
            "errors": errors,
        },
    )

    return {"terminated": True}
