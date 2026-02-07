"""Node implementations for single-iteration graph.

These nodes are designed for the external-loop orchestrator where each
graph invocation handles exactly one optimization iteration.

Architecture: Baseline + Analyst-First + Pre-Backtest循环
- Iteration 0: submit_baseline_backtest (不修改代码，获取基准)
- Iteration 1+: analyst_diagnose -> engineer_modify -> analyst_review_code -> submit_backtest
"""

import asyncio
from typing import Any

import structlog

from ...agents.engineer.agent import run_engineer
from ...agents.analyst.agent import run_analyst, run_analyst_code_review
from ...core.messaging import Events, publish_event
from ...core.state import SingleIterationState
from ...grpc_client.client import BacktestConfig, FreqSearchClient
from ...schemas.diagnosis import DiagnosisStatus

logger = structlog.get_logger(__name__)

# Configuration
MAX_VALIDATION_RETRIES = 5
MAX_CODE_ITERATIONS = 3  # 每次优化迭代内的代码审核循环次数
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
                "generated_code": generated_code,
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

    # Max validation retries exhausted - continue to next iteration instead of terminating
    # The next iteration will have feedback about the validation errors
    logger.warning(
        "Max validation retries exhausted - will retry in next iteration",
        iteration=iteration,
        retries=validation_retry_count,
        last_errors=last_validation_errors,
    )
    error_summary = "; ".join(last_validation_errors) if last_validation_errors else "Unknown validation errors"
    return {
        "validation_passed": False,
        "validation_retry_count": validation_retry_count,
        # Don't terminate - let the flow continue to analyst which will trigger next iteration
        "analyst_decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
        "analyst_feedback": f"Code validation failed after {validation_retry_count} retries: {error_summary}. Please fix these syntax/structure errors.",
    }


async def submit_baseline_backtest_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """提交 baseline backtest - 不修改代码，直接运行原始策略.

    这是第0次迭代，目的是获取原始策略的基准表现。

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with baseline backtest job ID
    """
    run_id = state["optimization_run_id"]
    strategy_id = state["base_strategy_id"]

    logger.info(
        "Submitting baseline backtest",
        run_id=run_id,
        strategy_id=strategy_id,
    )

    grpc_address = config.get("grpc_address", GRPC_ADDRESS) if config else GRPC_ADDRESS

    async with FreqSearchClient(grpc_address) as client:
        # 直接使用 base strategy，不修改代码
        bt_config_data = state.get("backtest_config", {})
        backtest_config = BacktestConfig(
            exchange=bt_config_data.get("exchange", ""),
            pairs=bt_config_data.get("pairs", []),
            timeframe=bt_config_data.get("timeframe", ""),
            timerange_start=bt_config_data.get("timerange_start", "20240101"),
            timerange_end=bt_config_data.get("timerange_end", "20240401"),
            dry_run_wallet=bt_config_data.get("dry_run_wallet", 0),
            max_open_trades=bt_config_data.get("max_open_trades", 0),
            stake_amount=bt_config_data.get("stake_amount", ""),
        )

        try:
            backtest_response = await client.submit_backtest(
                strategy_id=strategy_id,
                config=backtest_config,
                optimization_run_id=run_id,
            )
            job_id = backtest_response.get("job", {}).get("id")

            if not job_id:
                raise KeyError("job.id not found in backtest response")

            logger.info(
                "Baseline backtest submitted",
                job_id=job_id,
                strategy_id=strategy_id,
            )
        except Exception as e:
            logger.error("Failed to submit baseline backtest", error=str(e))
            return {
                "should_terminate": True,
                "termination_reason": "baseline_backtest_failed",
            }

    return {
        "backtest_job_id": job_id,
        "baseline_strategy_id": strategy_id,
        "validation_passed": True,
    }


async def analyst_diagnose_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyst 诊断节点 - 分析上次 backtest 结果.

    在 Engineer 之前运行，提供结构化的诊断报告。
    这是 Pre-Backtest 循环的起点。

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with diagnosis report
    """
    previous_result = state.get("previous_backtest_result")
    baseline_result = state.get("baseline_result")
    iteration = state["current_iteration"]
    run_id = state["optimization_run_id"]

    if not previous_result:
        logger.warning("No previous result to diagnose, using baseline")
        previous_result = baseline_result

    if not previous_result:
        logger.error("No result to diagnose")
        return {
            "should_terminate": True,
            "termination_reason": "no_result_to_diagnose",
        }

    logger.info(
        "Running Analyst diagnosis (BEFORE Engineer)",
        run_id=run_id,
        iteration=iteration,
    )

    # 计算 vs baseline 的对比
    baseline_comparison = _compute_baseline_comparison(previous_result, baseline_result)

    # 运行 Analyst 诊断
    try:
        analyst_result = await run_analyst(
            backtest_result={
                **previous_result,
                "baseline_comparison": baseline_comparison,
                "optimization_run_id": run_id,
                "current_iteration": iteration,
            },
            strategy_code=state.get("input_code"),
            diagnosis_mode=True,  # 诊断模式，不做最终决策
        )

        diagnosis_report = {
            "issues": analyst_result.get("issues", []),
            "root_causes": analyst_result.get("root_causes", []),
            "suggestion_type": analyst_result.get("suggestion_type"),
            "suggestion_description": analyst_result.get("suggestion_description"),
            "target_metrics": analyst_result.get("target_metrics", []),
            "confidence": analyst_result.get("confidence", 0.5),
            "baseline_comparison": baseline_comparison,
        }

        logger.info(
            "Diagnosis completed",
            issues=diagnosis_report["issues"],
            suggestion_type=diagnosis_report["suggestion_type"],
        )

        return {"diagnosis_report": diagnosis_report}

    except Exception as e:
        logger.exception("Analyst diagnosis failed", error=str(e))
        return {
            "diagnosis_report": {
                "issues": ["Diagnosis failed"],
                "root_causes": [str(e)],
                "suggestion_type": "ADD_FILTER",
                "suggestion_description": "Generic improvement needed",
                "target_metrics": ["sharpe_ratio"],
                "confidence": 0.3,
            }
        }


async def engineer_modify_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Engineer 修改节点 - 根据诊断报告修改代码.

    接收结构化的 DiagnosisReport，进行针对性修改。

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with generated code and validation status
    """
    diagnosis = state.get("diagnosis_report") or {}
    iteration = state["current_iteration"]
    code_iter = state.get("code_iteration_count", 0)
    run_id = state["optimization_run_id"]

    # Handle case where diagnosis is missing (should be caught by routing, but defensive)
    if not diagnosis:
        logger.warning("No diagnosis report available, using defaults")

    logger.info(
        "Running Engineer with diagnosis",
        run_id=run_id,
        iteration=iteration,
        code_iteration=code_iter,
        issues=diagnosis.get("issues", []),
    )

    # 构建 engineer 输入
    engineer_input = {
        "id": state["current_strategy_id"],
        "name": f"strategy_{state['base_strategy_id']}_iter_{iteration}_v{code_iter}",
        "code": state.get("generated_code") or state["input_code"],
        "diagnosis": {
            "issues": diagnosis.get("issues", []),
            "root_causes": diagnosis.get("root_causes", []),
            "suggestion_type": diagnosis.get("suggestion_type", "ADD_FILTER"),
            "suggestion_description": diagnosis.get("suggestion_description", ""),
            "target_metrics": diagnosis.get("target_metrics", []),
        },
        "baseline_comparison": diagnosis.get("baseline_comparison", {}),
    }

    # 如果有代码审核反馈，添加进去
    if state.get("code_review_feedback"):
        engineer_input["code_review_feedback"] = state["code_review_feedback"]

    grpc_address = config.get("grpc_address", GRPC_ADDRESS) if config else GRPC_ADDRESS

    try:
        engineer_result = await run_engineer(
            input_data=engineer_input,
            mode="evolve",
            thread_id=f"{run_id}-engineer-{iteration}-v{code_iter}",
        )
    except Exception as e:
        logger.exception("Engineer failed", error=str(e))
        return {
            "validation_passed": False,
            "code_review_passed": False,
            "code_review_feedback": f"Engineer error: {str(e)}",
        }

    generated_code = engineer_result.get("generated_code", "")

    if not generated_code:
        return {
            "validation_passed": False,
            "code_review_passed": False,
            "code_review_feedback": "Engineer produced no code",
        }

    # 基础验证
    if not engineer_result.get("validation_passed", False):
        return {
            "generated_code": generated_code,
            "engineer_result": engineer_result,
            "validation_passed": False,
            "code_review_passed": False,
            "code_review_feedback": f"Validation errors: {engineer_result.get('validation_errors', [])}",
            "code_iteration_count": code_iter + 1,
        }

    # Docker 验证
    async with FreqSearchClient(grpc_address) as client:
        try:
            validation_result = await client.validate_strategy(
                code=generated_code,
                name=f"strategy_iter_{iteration}_v{code_iter}",
            )
        except Exception:
            validation_result = {"valid": True}

    if not validation_result.get("valid", False):
        return {
            "generated_code": generated_code,
            "engineer_result": engineer_result,
            "validation_passed": False,
            "code_review_passed": False,
            "code_review_feedback": f"Docker validation failed: {validation_result.get('errors', [])}",
            "code_iteration_count": code_iter + 1,
        }

    return {
        "generated_code": generated_code,
        "engineer_result": engineer_result,
        "validation_passed": True,
        "code_iteration_count": code_iter + 1,
    }


async def analyst_review_code_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyst 代码审核节点 - 在 backtest 之前审核代码质量.

    检查代码是否符合诊断建议，决定是否可以提交 backtest。

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with code review result
    """
    generated_code = state.get("generated_code")
    diagnosis = state.get("diagnosis_report") or {}
    code_iter = state.get("code_iteration_count", 0)
    max_code_iter = state.get("max_code_iterations", MAX_CODE_ITERATIONS)

    logger.info(
        "Analyst reviewing code",
        code_iteration=code_iter,
        max_code_iterations=max_code_iter,
    )

    # 如果验证都没通过，直接不通过
    if not state.get("validation_passed"):
        return {
            "code_review_passed": False,
            "code_review_feedback": state.get("code_review_feedback") or "Validation not passed",
        }

    # 如果达到最大代码迭代次数，强制通过
    if code_iter >= max_code_iter:
        logger.warning(
            "Max code iterations reached, forcing submission",
            code_iteration=code_iter,
        )
        return {
            "code_review_passed": True,
            "code_review_feedback": "Max code iterations reached, proceeding to backtest",
        }

    # 运行 Analyst 代码审核
    try:
        review_result = await _run_analyst_code_review(
            code=generated_code,
            diagnosis=diagnosis,
            baseline_result=state.get("baseline_result"),
        )

        approved = review_result.get("approved", False)
        feedback = review_result.get("feedback", "")

        logger.info(
            "Code review completed",
            approved=approved,
            feedback=feedback[:100] if feedback else None,
        )

        return {
            "code_review_passed": approved,
            "code_review_feedback": feedback,
        }

    except Exception as e:
        logger.exception("Code review failed", error=str(e))
        # 审核失败时，如果代码验证通过了，就让它过
        return {
            "code_review_passed": state.get("validation_passed", False),
            "code_review_feedback": f"Review error (proceeding anyway): {str(e)}",
        }


async def compare_results_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """对比结果节点 - 计算 vs baseline 和 vs previous 的改进.

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with comparison results
    """
    current_result = state.get("backtest_result", {})
    baseline_result = state.get("baseline_result", {})
    previous_result = state.get("previous_backtest_result")

    logger.info("Comparing results with baseline")

    improvement_vs_baseline = _compute_baseline_comparison(current_result, baseline_result)
    improvement_vs_previous = _compute_baseline_comparison(current_result, previous_result) if previous_result else None

    # 记录改进情况
    baseline_sharpe = baseline_result.get("sharpe_ratio", 0)
    current_sharpe = current_result.get("sharpe_ratio", 0)

    logger.info(
        "Result comparison",
        baseline_sharpe=baseline_sharpe,
        current_sharpe=current_sharpe,
        improvement=current_sharpe - baseline_sharpe if baseline_sharpe else 0,
    )

    return {
        "improvement_vs_baseline": improvement_vs_baseline,
        "improvement_vs_previous": improvement_vs_previous,
    }


def _compute_baseline_comparison(
    current: dict[str, Any],
    baseline: dict[str, Any] | None,
) -> dict[str, float]:
    """计算当前结果 vs baseline 的改进.

    Args:
        current: Current backtest result
        baseline: Baseline backtest result

    Returns:
        Dictionary with improvement metrics
    """
    if not baseline:
        return {}

    metrics = ["sharpe_ratio", "profit_pct", "win_rate", "max_drawdown_pct", "total_trades"]
    comparison = {}

    for metric in metrics:
        curr_val = current.get(metric, 0) or 0
        base_val = baseline.get(metric, 0) or 0

        if metric == "max_drawdown_pct":
            # 回撤越小越好
            comparison[f"{metric}_improvement"] = base_val - curr_val
        else:
            comparison[f"{metric}_improvement"] = curr_val - base_val

        comparison[f"{metric}_current"] = curr_val
        comparison[f"{metric}_baseline"] = base_val

    return comparison


async def _run_analyst_code_review(
    code: str,
    diagnosis: dict[str, Any],
    baseline_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """运行 Analyst 代码审核.

    Delegates to the actual Analyst code review functionality.

    Args:
        code: Generated strategy code
        diagnosis: Diagnosis report
        baseline_result: Baseline backtest result for reference

    Returns:
        Dictionary with approved flag and feedback
    """
    # Use the actual analyst code review function
    return await run_analyst_code_review(
        code=code,
        diagnosis=diagnosis,
        baseline_result=baseline_result,
    )


async def submit_backtest_node(
    state: SingleIterationState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Submit backtest to Go backend.

    只有代码审核通过后才提交 backtest，并创建新的策略记录。

    Args:
        state: Current iteration state
        config: Optional configuration

    Returns:
        State update with backtest job ID and strategy ID
    """
    # 检查验证和代码审核是否通过
    if not state.get("validation_passed"):
        logger.warning("Skipping backtest - validation not passed")
        return {}

    if not state.get("code_review_passed"):
        logger.warning("Skipping backtest - code review not passed")
        return {}

    iteration = state["current_iteration"]
    run_id = state["optimization_run_id"]

    logger.info(
        "Submitting backtest after code review passed",
        run_id=run_id,
        iteration=iteration,
    )

    grpc_address = config.get("grpc_address", GRPC_ADDRESS) if config else GRPC_ADDRESS
    # 使用 generated_code (来自 engineer_modify_node)
    generated_code = state.get("generated_code", "")

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
            logger.exception("Strategy creation failed", error=str(e))
            return {
                "should_terminate": True,
                "termination_reason": f"strategy_creation_failed: {str(e)[:200]}",
                "error_details": str(e),
            }

        # Build backtest config
        # Use empty string for exchange to inherit from base_config.json (OKX by default)
        # Use longer timerange (3 months) to have enough candles for strategies with high startup_candle_count
        bt_config_data = state.get("backtest_config", {})
        backtest_config = BacktestConfig(
            exchange=bt_config_data.get("exchange", ""),
            pairs=bt_config_data.get("pairs", []),
            timeframe=bt_config_data.get("timeframe", ""),
            timerange_start=bt_config_data.get("timerange_start", "20240101"),
            timerange_end=bt_config_data.get("timerange_end", "20240401"),
            dry_run_wallet=bt_config_data.get("dry_run_wallet", 0),
            max_open_trades=bt_config_data.get("max_open_trades", 0),
            stake_amount=bt_config_data.get("stake_amount", ""),
        )

        # Submit backtest
        try:
            backtest_response = await client.submit_backtest(
                strategy_id=generated_strategy_id,
                config=backtest_config,
                optimization_run_id=run_id,
            )
            # Response format is {"job": {"id": "...", ...}, ...}
            job_id = backtest_response.get("job", {}).get("id")
            if not job_id:
                raise KeyError("job.id not found in backtest response")
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
                # Response is nested: {"job": {"status": "JOB_STATUS_..."}}
                job_data = job_response.get("job", {})
                status = job_data.get("status", "unknown")

                logger.debug(
                    "Polling backtest status",
                    job_id=job_id,
                    raw_status=status,
                )

                if status == "JOB_STATUS_COMPLETED":
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

                elif status == "JOB_STATUS_FAILED":
                    error_msg = job_data.get("error", "Unknown backtest error")
                    logger.error(
                        "Backtest failed",
                        job_id=job_id,
                        error=error_msg,
                    )
                    return {
                        "backtest_result": {"error": error_msg, "status": "failed"},
                    }

                elif status == "JOB_STATUS_CANCELLED":
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

        # Timeout - cancel the zombie backtest job
        logger.error("Backtest timeout", job_id=job_id, waited=total_wait)
        try:
            await client.cancel_backtest(job_id)
            logger.info("Cancelled timed-out backtest", job_id=job_id)
        except Exception as cancel_err:
            logger.warning("Failed to cancel timed-out backtest", job_id=job_id, error=str(cancel_err))

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
        # Enrich backtest result with optimization context
        enriched_result = {
            **backtest_result,
            "job_id": state.get("backtest_job_id", ""),
            "strategy_id": state.get("generated_strategy_id", state["current_strategy_id"]),
            "optimization_run_id": run_id,
            "current_iteration": iteration,
        }

        analyst_result = await run_analyst(
            backtest_result=enriched_result,
            strategy_code=state.get("generated_code"),
        )

        decision = analyst_result.get("decision", "modify")
        # Normalize decision - handle both lowercase keys and DiagnosisStatus values
        decision_map = {
            # Lowercase keys (from simple returns)
            "approve": DiagnosisStatus.READY_FOR_LIVE.value,
            "modify": DiagnosisStatus.NEEDS_MODIFICATION.value,
            "archive": DiagnosisStatus.ARCHIVE.value,
            # DiagnosisStatus enum values (from Analyst agent)
            DiagnosisStatus.READY_FOR_LIVE.value: DiagnosisStatus.READY_FOR_LIVE.value,
            DiagnosisStatus.NEEDS_MODIFICATION.value: DiagnosisStatus.NEEDS_MODIFICATION.value,
            DiagnosisStatus.ARCHIVE.value: DiagnosisStatus.ARCHIVE.value,
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
    - Whether this iteration found a new best (vs baseline and vs previous best)

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
    baseline_result = state.get("baseline_result", {})
    baseline_sharpe = baseline_result.get("sharpe_ratio", float("-inf")) if baseline_result else float("-inf")

    logger.info(
        "Processing decision",
        decision=decision,
        current_sharpe=current_sharpe,
        best_sharpe=state["best_sharpe"],
        baseline_sharpe=baseline_sharpe,
    )

    updates: dict[str, Any] = {}

    # Check if new best (vs best_sharpe which starts at baseline)
    if current_sharpe > state["best_sharpe"]:
        logger.info(
            "New best found",
            new_sharpe=current_sharpe,
            old_sharpe=state["best_sharpe"],
            improvement_vs_baseline=current_sharpe - baseline_sharpe,
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
                "baseline_sharpe": baseline_sharpe,
                "improvement": current_sharpe - baseline_sharpe,
            },
        )

    # 检查是否相比 baseline 有显著退化
    improvement_vs_baseline = state.get("improvement_vs_baseline", {})
    sharpe_improvement = improvement_vs_baseline.get("sharpe_ratio_improvement", 0)

    if sharpe_improvement < -0.5 and state["current_iteration"] > 3:
        # 相比 baseline 显著退化，考虑提前终止
        logger.warning(
            "Strategy significantly worse than baseline",
            current_sharpe=current_sharpe,
            baseline_sharpe=baseline_sharpe,
            improvement=sharpe_improvement,
        )
        # 但不强制终止，让 Analyst 决定

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
