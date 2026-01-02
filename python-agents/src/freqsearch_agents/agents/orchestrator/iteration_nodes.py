"""Node implementations for single-iteration graph.

These nodes are designed for the external-loop orchestrator where each
graph invocation handles exactly one optimization iteration.
"""

import asyncio
from typing import Any

import structlog

from ...agents.engineer.agent import run_engineer
from ...agents.analyst.agent import run_analyst
from ...core.messaging import Events, publish_event
from ...core.state import SingleIterationState
from ...grpc_client.client import BacktestConfig, FreqSearchClient
from ...schemas.diagnosis import DiagnosisStatus

logger = structlog.get_logger(__name__)

# Configuration
MAX_VALIDATION_RETRIES = 5
BACKTEST_POLL_INTERVAL = 5  # seconds
BACKTEST_MAX_WAIT = 600  # 10 minutes
GRPC_ADDRESS = "localhost:50051"


async def validate_and_engineer_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Engineer node with internal validation retry loop.

    This handles validation failures WITHOUT consuming optimization iterations.
    Validation retries happen inside this node, not through the graph loop.

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with engineer result and validation status
    """
    iteration = state["current_iteration"]
    run_id = state["optimization_run_id"]

    logger.info(
        "Starting validate_and_engineer",
        run_id=run_id,
        iteration=iteration,
        mode=state["mode"],
    )

    grpc_address = config.get("grpc_address", GRPC_ADDRESS) if config else GRPC_ADDRESS
    validation_retry_count = 0
    last_validation_errors: list[str] = []

    # Prepare initial engineer input
    engineer_input = {
        "id": state["current_strategy_id"],
        "name": f"strategy_{state['base_strategy_id']}_iter_{iteration}",
        "code": state["input_code"],
    }

    # Add feedback if evolving
    if state["mode"] == "evolve" and state["input_feedback"]:
        engineer_input["diagnosis"] = state["input_feedback"]

    while validation_retry_count < MAX_VALIDATION_RETRIES:
        logger.info(
            "Running engineer",
            iteration=iteration,
            validation_retry=validation_retry_count,
        )

        # Run Engineer Agent
        try:
            engineer_result = await run_engineer(
                input_data=engineer_input,
                mode="new" if validation_retry_count == 0 and state["mode"] == "new" else "evolve",
                thread_id=f"{run_id}-engineer-{iteration}-v{validation_retry_count}",
            )
        except Exception as e:
            logger.exception("Engineer failed", error=str(e))
            return {
                "should_terminate": True,
                "termination_reason": "engineer_exception",
                "validation_passed": False,
            }

        # Check if engineer produced valid code
        if not engineer_result.get("validation_passed", False):
            logger.warning(
                "Engineer internal validation failed",
                iteration=iteration,
                errors=engineer_result.get("validation_errors", []),
            )
            validation_retry_count += 1
            last_validation_errors = engineer_result.get("validation_errors", [])
            engineer_input["diagnosis"] = f"Code validation failed: {last_validation_errors}. Please fix."
            continue

        generated_code = engineer_result.get("generated_code", "") or engineer_result.get("code", "")
        if not generated_code:
            logger.error("Engineer produced no code")
            return {
                "should_terminate": True,
                "termination_reason": "engineer_no_code",
                "validation_passed": False,
            }

        # Validate with Docker backend
        try:
            async with FreqSearchClient(grpc_address) as client:
                validation_result = await client.validate_strategy(
                    code=generated_code,
                    name=f"strategy_iter_{iteration}_v{validation_retry_count}",
                )
        except Exception as e:
            logger.warning(
                "Backend validation call failed, proceeding anyway",
                error=str(e),
            )
            # If backend validation unavailable, trust engineer's validation
            validation_result = {"valid": True}

        if validation_result.get("valid", False):
            logger.info(
                "Validation passed",
                iteration=iteration,
                validation_retries=validation_retry_count,
            )
            return {
                "engineer_result": engineer_result,
                "validation_passed": True,
                "validation_retry_count": validation_retry_count,
            }

        # Validation failed - retry with feedback
        validation_errors = validation_result.get("errors", ["Unknown validation error"])
        logger.warning(
            "Backend validation failed, retrying",
            iteration=iteration,
            validation_retry=validation_retry_count,
            errors=validation_errors,
        )

        validation_retry_count += 1
        last_validation_errors = validation_errors
        engineer_input["diagnosis"] = f"Strategy code failed Docker validation: {validation_errors}. Please fix these issues."
        engineer_input["code"] = generated_code  # Use latest code as base

    # Max validation retries exhausted
    logger.error(
        "Max validation retries exhausted",
        iteration=iteration,
        retries=validation_retry_count,
        last_errors=last_validation_errors,
    )
    return {
        "validation_passed": False,
        "validation_retry_count": validation_retry_count,
        "should_terminate": True,
        "termination_reason": "validation_max_retries",
    }


async def submit_backtest_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Submit backtest to Go backend.

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with backtest job ID and strategy ID
    """
    if not state.get("validation_passed"):
        logger.warning("Skipping backtest - validation not passed")
        return {}

    iteration = state["current_iteration"]
    run_id = state["optimization_run_id"]

    logger.info(
        "Submitting backtest",
        run_id=run_id,
        iteration=iteration,
    )

    grpc_address = config.get("grpc_address", GRPC_ADDRESS) if config else GRPC_ADDRESS
    engineer_result = state.get("engineer_result", {})
    generated_code = engineer_result.get("generated_code", "") or engineer_result.get("code", "")

    async with FreqSearchClient(grpc_address) as client:
        # Create strategy in backend
        try:
            strategy_response = await client.create_strategy(
                name=f"strategy_{state['base_strategy_id']}_opt_{run_id}_iter_{iteration}",
                code=generated_code,
                description=f"Generated in optimization run {run_id}, iteration {iteration}",
                parent_id=state["current_strategy_id"],
            )
            generated_strategy_id = strategy_response["strategy"]["id"]
            logger.info(
                "Strategy created",
                strategy_id=generated_strategy_id,
                iteration=iteration,
            )
        except Exception as e:
            logger.error("Failed to create strategy", error=str(e))
            return {
                "should_terminate": True,
                "termination_reason": "strategy_creation_failed",
            }

        # Build backtest config
        bt_config_data = state.get("backtest_config", {})
        backtest_config = BacktestConfig(
            exchange=bt_config_data.get("exchange", "binance"),
            pairs=bt_config_data.get("pairs", ["BTC/USDT"]),
            timeframe=bt_config_data.get("timeframe", "1h"),
            timerange_start=bt_config_data.get("timerange_start", "20230101"),
            timerange_end=bt_config_data.get("timerange_end", "20230131"),
            dry_run_wallet=bt_config_data.get("dry_run_wallet", 1000.0),
            max_open_trades=bt_config_data.get("max_open_trades", 3),
            stake_amount=bt_config_data.get("stake_amount", "unlimited"),
        )

        # Submit backtest
        try:
            backtest_response = await client.submit_backtest(
                strategy_id=generated_strategy_id,
                config=backtest_config,
                optimization_run_id=run_id,
            )
            job_id = backtest_response["job_id"]
            logger.info(
                "Backtest submitted",
                job_id=job_id,
                strategy_id=generated_strategy_id,
            )
        except Exception as e:
            logger.error("Failed to submit backtest", error=str(e))
            return {
                "generated_strategy_id": generated_strategy_id,
                "should_terminate": True,
                "termination_reason": "backtest_submission_failed",
            }

    return {
        "generated_strategy_id": generated_strategy_id,
        "backtest_job_id": job_id,
    }


async def wait_for_result_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wait for backtest to complete and get results.

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with backtest result
    """
    job_id = state.get("backtest_job_id")
    if not job_id:
        logger.warning("No backtest job ID to wait for")
        return {}

    run_id = state["optimization_run_id"]
    iteration = state["current_iteration"]

    logger.info(
        "Waiting for backtest result",
        run_id=run_id,
        iteration=iteration,
        job_id=job_id,
    )

    grpc_address = config.get("grpc_address", GRPC_ADDRESS) if config else GRPC_ADDRESS
    total_wait = 0

    async with FreqSearchClient(grpc_address) as client:
        while total_wait < BACKTEST_MAX_WAIT:
            try:
                job_response = await client.get_backtest_job(job_id)
                status = job_response.get("status", "unknown")

                if status == "completed":
                    # Get full result
                    result_response = await client.get_backtest_result(job_id)
                    backtest_result = result_response.get("result", {})

                    logger.info(
                        "Backtest completed",
                        job_id=job_id,
                        sharpe=backtest_result.get("sharpe_ratio"),
                        profit=backtest_result.get("profit_pct"),
                    )
                    return {"backtest_result": backtest_result}

                elif status == "failed":
                    error_msg = job_response.get("error", "Unknown backtest error")
                    logger.error(
                        "Backtest failed",
                        job_id=job_id,
                        error=error_msg,
                    )
                    return {
                        "backtest_result": {"error": error_msg, "status": "failed"},
                    }

                elif status == "cancelled":
                    logger.warning("Backtest was cancelled", job_id=job_id)
                    return {
                        "should_terminate": True,
                        "termination_reason": "backtest_cancelled",
                    }

                # Still running - wait and poll again
                await asyncio.sleep(BACKTEST_POLL_INTERVAL)
                total_wait += BACKTEST_POLL_INTERVAL

            except Exception as e:
                logger.error("Error polling backtest status", error=str(e))
                await asyncio.sleep(BACKTEST_POLL_INTERVAL)
                total_wait += BACKTEST_POLL_INTERVAL

    # Timeout
    logger.error("Backtest timeout", job_id=job_id, waited=total_wait)
    return {
        "should_terminate": True,
        "termination_reason": "backtest_timeout",
    }


async def invoke_analyst_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke Analyst Agent to analyze backtest results.

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with analyst decision and feedback
    """
    backtest_result = state.get("backtest_result")
    if not backtest_result:
        logger.warning("No backtest result to analyze")
        return {}

    # Check if backtest failed
    if backtest_result.get("status") == "failed":
        logger.warning("Backtest failed, skipping analyst")
        return {
            "analyst_decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
            "analyst_feedback": f"Backtest failed: {backtest_result.get('error', 'Unknown error')}",
        }

    iteration = state["current_iteration"]
    run_id = state["optimization_run_id"]

    logger.info(
        "Invoking Analyst Agent",
        run_id=run_id,
        iteration=iteration,
    )

    try:
        analyst_result = await run_analyst(
            job_id=state.get("backtest_job_id", ""),
            strategy_id=state.get("generated_strategy_id", state["current_strategy_id"]),
            backtest_result=backtest_result,
            optimization_run_id=run_id,
            current_iteration=iteration,
            max_iterations=10,  # Will be checked by external runner
            thread_id=f"{run_id}-analyst-{iteration}",
        )

        decision = analyst_result.get("decision", "modify")
        decision_map = {
            "approve": DiagnosisStatus.READY_FOR_LIVE.value,
            "modify": DiagnosisStatus.NEEDS_MODIFICATION.value,
            "archive": DiagnosisStatus.ARCHIVE.value,
        }

        analyst_decision = decision_map.get(decision, DiagnosisStatus.NEEDS_MODIFICATION.value)

        # Build feedback string
        feedback_parts = []
        if analyst_result.get("suggestion_description"):
            feedback_parts.append(analyst_result["suggestion_description"])
        if analyst_result.get("issues"):
            feedback_parts.append(f"Issues: {', '.join(analyst_result['issues'])}")
        if analyst_result.get("root_causes"):
            feedback_parts.append(f"Root causes: {', '.join(analyst_result['root_causes'])}")

        analyst_feedback = " ".join(feedback_parts) if feedback_parts else None

        logger.info(
            "Analyst completed",
            decision=analyst_decision,
            feedback_length=len(analyst_feedback) if analyst_feedback else 0,
        )

        return {
            "analyst_decision": analyst_decision,
            "analyst_feedback": analyst_feedback,
        }

    except Exception as e:
        logger.exception("Analyst failed", error=str(e))
        return {
            "analyst_decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
            "analyst_feedback": f"Analyst exception: {str(e)}",
        }


async def decide_next_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Determine termination and best tracking.

    This node processes the analyst decision and determines:
    - Whether to terminate
    - Whether this iteration found a new best

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with termination and best tracking
    """
    if state.get("should_terminate"):
        # Already terminated earlier in pipeline
        return {}

    decision = state.get("analyst_decision")
    backtest_result = state.get("backtest_result", {})
    current_sharpe = backtest_result.get("sharpe_ratio", float("-inf"))

    logger.info(
        "Processing decision",
        decision=decision,
        current_sharpe=current_sharpe,
        best_sharpe=state["best_sharpe"],
    )

    updates: dict[str, Any] = {}

    # Check if new best
    if current_sharpe > state["best_sharpe"]:
        logger.info(
            "New best found",
            new_sharpe=current_sharpe,
            old_sharpe=state["best_sharpe"],
        )
        updates["is_new_best"] = True
        updates["new_best_sharpe"] = current_sharpe

        # Publish event
        await publish_event(
            Events.OPTIMIZATION_NEW_BEST,
            {
                "optimization_run_id": state["optimization_run_id"],
                "iteration": state["current_iteration"],
                "strategy_id": state.get("generated_strategy_id"),
                "sharpe_ratio": current_sharpe,
            },
        )

    # Determine termination
    if decision == DiagnosisStatus.READY_FOR_LIVE.value:
        logger.info("Strategy approved - terminating")
        updates["should_terminate"] = True
        updates["termination_reason"] = "approved"

    elif decision == DiagnosisStatus.ARCHIVE.value:
        logger.info("Strategy archived - terminating")
        updates["should_terminate"] = True
        updates["termination_reason"] = "archived"

    # NEEDS_MODIFICATION continues to next iteration (handled by external runner)

    return updates
