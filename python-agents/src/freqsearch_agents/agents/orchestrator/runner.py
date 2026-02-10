"""External loop orchestrator runner.

This module provides the OrchestratorRunner class that manages optimization
iterations using an external Python loop instead of LangGraph's internal looping.

Benefits:
- No LangGraph recursion limits
- Fresh graph per iteration (memory bounded)
- Clean state management via PostgreSQL
- Support for graceful resume after failures
"""

from typing import Any

import structlog

from ...core.messaging import Events, publish_event
from ...grpc_client.client import FreqSearchClient
from ...grpc_client.retry import with_retry
from .context import OptimizationContext
from .graph import create_single_iteration_graph

logger = structlog.get_logger(__name__)


class OrchestratorRunner:
    """External loop controller for optimization runs.

    Instead of using LangGraph's internal looping (which can hit recursion limits),
    this runner manages iterations externally with a simple Python while loop.

    Each iteration:
    1. Loads context from PostgreSQL
    2. Creates a fresh single-iteration graph
    3. Runs the graph
    4. Persists results back to PostgreSQL
    5. Checks termination conditions
    """

    def __init__(
        self,
        grpc_address: str = "localhost:50051",
    ):
        """Initialize the runner.

        Args:
            grpc_address: gRPC server address
        """
        self.grpc_address = grpc_address

    @staticmethod
    @with_retry(max_retries=5, base_delay=2.0)
    async def _control_optimization_with_retry(
        client: FreqSearchClient,
        run_id: str,
        action: str,
        **kwargs,
    ) -> None:
        """Control optimization with retry logic.

        Args:
            client: gRPC client
            run_id: Optimization run ID
            action: Control action
            **kwargs: Additional arguments for control_optimization
        """
        await client.control_optimization(run_id, action, **kwargs)

    async def run_optimization(
        self,
        run_id: str,
        base_strategy_id: str,
        max_iterations: int = 10,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run optimization - Baseline + Improve workflow.

        Args:
            run_id: Optimization run ID
            base_strategy_id: Base strategy to optimize
            max_iterations: Maximum improvement iterations (not including baseline)
            config: Optional configuration (backtest settings, etc.)

        Returns:
            Final optimization result
        """
        logger.info(
            "Starting optimization with Baseline + Improve workflow",
            run_id=run_id,
            base_strategy_id=base_strategy_id,
            max_iterations=max_iterations,
        )

        async with FreqSearchClient(self.grpc_address) as client:
            # Load initial context (supports resume)
            context = await OptimizationContext.load(client, run_id)

            # Check if already complete
            if context.is_complete():
                logger.info(
                    "Optimization already complete",
                    run_id=run_id,
                    status=context.status,
                )
                return self._build_result(context, "already_complete")

            # Set to running
            await self._control_optimization_with_retry(client, run_id, "resume")

            # ========== Phase 1: Baseline ==========
            if not context.baseline_completed:
                logger.info("Running baseline iteration", run_id=run_id)

                await publish_event(
                    Events.OPTIMIZATION_ITERATION_STARTED,
                    {
                        "optimization_run_id": run_id,
                        "iteration": 0,
                        "mode": "baseline",
                    },
                )

                try:
                    graph = create_single_iteration_graph()
                    iteration_state = context.to_iteration_state()

                    result = await graph.ainvoke(
                        iteration_state,
                        config={
                            "configurable": {"thread_id": f"{run_id}-baseline"},
                            "recursion_limit": 100,
                        },
                    )

                    await context.save_iteration_result(client, result)

                    await publish_event(
                        Events.OPTIMIZATION_ITERATION_COMPLETED,
                        {
                            "optimization_run_id": run_id,
                            "iteration": 0,
                            "mode": "baseline",
                            "backtest_result": result.get("backtest_result"),
                        },
                    )

                    if result.get("should_terminate"):
                        return self._build_result(context, result.get("termination_reason"))

                    # Note: We don't reload context here because save_iteration_result
                    # already updated the local context with baseline data.
                    # Reloading from DB might fail if backend hasn't stored iterations yet.
                    logger.info(
                        "Baseline completed, context updated",
                        baseline_result_sharpe=context.baseline_result.get("sharpe_ratio") if context.baseline_result else None,
                        baseline_strategy_id=context.baseline_strategy_id,
                    )

                except Exception as e:
                    logger.exception("Baseline iteration failed", error=str(e))
                    try:
                        await self._control_optimization_with_retry(
                            client, run_id, "fail", termination_reason=str(e)
                        )
                    except Exception:
                        pass
                    return self._build_result(context, "exception", error=str(e))

            # ========== Phase 2: Improve Iterations ==========
            # max_iterations is for improve iterations (not including baseline)
            # current_iteration starts from 1 (after baseline)
            # Preserve baseline data in case reload fails to get it from backend
            baseline_result_cache = context.baseline_result
            baseline_strategy_id_cache = context.baseline_strategy_id

            while context.current_iteration <= max_iterations:
                # Check external control (reload to check status)
                old_baseline_result = context.baseline_result
                context = await OptimizationContext.load(client, run_id)
                if context.status in ("cancelled", "paused", "completed", "failed"):
                    break

                # Restore baseline data if reload lost it
                if not context.baseline_result and baseline_result_cache:
                    logger.warning(
                        "Baseline data lost after reload, restoring from cache",
                        run_id=run_id,
                    )
                    context.baseline_result = baseline_result_cache
                    context.baseline_strategy_id = baseline_strategy_id_cache
                    context.baseline_completed = True
                    context.previous_backtest_result = old_baseline_result or baseline_result_cache

                iteration = context.current_iteration
                logger.info(
                    "Starting improve iteration",
                    run_id=run_id,
                    iteration=iteration,
                    max_iterations=max_iterations,
                )

                await publish_event(
                    Events.OPTIMIZATION_ITERATION_STARTED,
                    {
                        "optimization_run_id": run_id,
                        "iteration": iteration,
                        "mode": "improve",
                    },
                )

                try:
                    graph = create_single_iteration_graph()
                    iteration_state = context.to_iteration_state()

                    result = await graph.ainvoke(
                        iteration_state,
                        config={
                            "configurable": {"thread_id": f"{run_id}-iter-{iteration}"},
                            "recursion_limit": 100,
                        },
                    )

                    await context.save_iteration_result(client, result)

                    await publish_event(
                        Events.OPTIMIZATION_ITERATION_COMPLETED,
                        {
                            "optimization_run_id": run_id,
                            "iteration": iteration,
                            "mode": "improve",
                            "decision": result.get("analyst_decision"),
                            "improvement_vs_baseline": result.get("improvement_vs_baseline"),
                            "is_new_best": result.get("is_new_best", False),
                        },
                    )

                    if result.get("should_terminate"):
                        logger.info(
                            "Optimization terminating",
                            run_id=run_id,
                            reason=result.get("termination_reason"),
                            iterations=iteration,
                        )
                        return self._build_result(context, result.get("termination_reason"))

                    # Reload context
                    context = await OptimizationContext.load(client, run_id)

                except Exception as e:
                    logger.exception(
                        "Iteration failed",
                        run_id=run_id,
                        iteration=iteration,
                        error=str(e),
                    )
                    try:
                        await self._control_optimization_with_retry(
                            client, run_id, "fail", termination_reason=str(e)
                        )
                    except Exception:
                        pass
                    return self._build_result(context, "exception", error=str(e))

            # ========== Max Iterations Reached ==========
            if context.status not in ("cancelled", "paused", "completed", "failed"):
                logger.info("Max iterations reached", run_id=run_id, max_iterations=max_iterations)
                try:
                    await self._control_optimization_with_retry(
                        client,
                        run_id,
                        "complete",
                        termination_reason="max_iterations",
                        best_strategy_id=context.best_strategy_id,
                    )
                except Exception as e:
                    logger.error("Failed to complete optimization", error=str(e))
                return self._build_result(context, "max_iterations")

            return self._build_result(context, context.status)

    async def resume_optimization(self, run_id: str) -> dict[str, Any]:
        """Resume an optimization from where it left off.

        Args:
            run_id: Optimization run ID to resume

        Returns:
            Final optimization result
        """
        logger.info("Resuming optimization", run_id=run_id)

        async with FreqSearchClient(self.grpc_address) as client:
            context = await OptimizationContext.load(client, run_id)

            if context.is_complete():
                logger.info(
                    "Optimization already complete",
                    run_id=run_id,
                    status=context.status,
                )
                return self._build_result(context, "already_complete")

            # ISSUE #2 FIX: Use loaded context's max_iterations value
            logger.info(
                "Resuming with loaded configuration",
                run_id=run_id,
                max_iterations=context.max_iterations,
                current_iteration=context.current_iteration,
            )

            return await self.run_optimization(
                run_id=run_id,
                base_strategy_id=context.base_strategy_id,
                max_iterations=context.max_iterations,  # Use loaded value, not default
            )

    def _build_result(
        self,
        context: OptimizationContext,
        termination_reason: str,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Build the final result dictionary.

        Args:
            context: Final optimization context
            termination_reason: Why optimization terminated
            error: Optional error message

        Returns:
            Result dictionary
        """
        result = {
            "run_id": context.run_id,
            "base_strategy_id": context.base_strategy_id,
            "iterations_completed": context.current_iteration,
            "max_iterations": context.max_iterations,
            "best_strategy_id": context.best_strategy_id,
            "best_sharpe": context.best_sharpe,
            "baseline_completed": context.baseline_completed,
            "baseline_result": context.baseline_result,
            "termination_reason": termination_reason,
            "status": "completed" if termination_reason in ("approved", "max_iterations") else "failed",
        }

        if error:
            result["error"] = error

        return result


async def run_optimization(
    run_id: str,
    base_strategy_id: str,
    max_iterations: int = 10,
    grpc_address: str = "localhost:50051",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience function to run optimization.

    Args:
        run_id: Optimization run ID
        base_strategy_id: Base strategy to optimize
        max_iterations: Maximum iterations
        grpc_address: gRPC server address
        config: Optional configuration

    Returns:
        Final optimization result
    """
    runner = OrchestratorRunner(grpc_address)
    return await runner.run_optimization(
        run_id=run_id,
        base_strategy_id=base_strategy_id,
        max_iterations=max_iterations,
        config=config,
    )
