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

    async def run_optimization(
        self,
        run_id: str,
        base_strategy_id: str,
        max_iterations: int = 10,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run optimization with external iteration loop.

        Args:
            run_id: Optimization run ID
            base_strategy_id: Base strategy to optimize
            max_iterations: Maximum iterations allowed
            config: Optional configuration (backtest settings, etc.)

        Returns:
            Final optimization result
        """
        logger.info(
            "Starting optimization with external runner",
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
            await client.control_optimization(run_id, "resume")

            # Main iteration loop
            while context.has_iterations_remaining():
                # Reload context to check for external cancellation/pause
                context = await OptimizationContext.load(client, run_id)
                if context.status in ("cancelled", "paused", "completed", "failed"):
                    logger.info(
                        "Optimization stopped externally",
                        status=context.status,
                        run_id=run_id,
                        iteration=context.current_iteration,
                    )
                    break

                logger.info(
                    "Starting iteration",
                    run_id=run_id,
                    iteration=context.current_iteration,
                    max_iterations=max_iterations,
                )

                # Publish iteration started event
                await publish_event(
                    Events.OPTIMIZATION_ITERATION_STARTED,
                    {
                        "optimization_run_id": run_id,
                        "iteration": context.current_iteration,
                        "max_iterations": max_iterations,
                    },
                )

                try:
                    # Create fresh graph for this iteration
                    graph = create_single_iteration_graph()

                    # Prepare state from context
                    iteration_state = context.to_iteration_state()

                    # Run single iteration
                    result = await graph.ainvoke(
                        iteration_state,
                        config={"configurable": {"thread_id": f"{run_id}-iter-{context.current_iteration}"}},
                    )

                    # Persist results
                    await context.save_iteration_result(client, result)

                    # Publish iteration completed event
                    await publish_event(
                        Events.OPTIMIZATION_ITERATION_COMPLETED,
                        {
                            "optimization_run_id": run_id,
                            "iteration": context.current_iteration - 1,  # Already incremented
                            "decision": result.get("analyst_decision"),
                            "sharpe_ratio": result.get("new_best_sharpe"),
                            "is_best": result.get("is_new_best", False),
                        },
                    )

                    # Check if should terminate
                    if result.get("should_terminate"):
                        logger.info(
                            "Optimization terminating",
                            run_id=run_id,
                            reason=result.get("termination_reason"),
                            iterations=context.current_iteration,
                        )
                        return self._build_result(context, result.get("termination_reason"))

                    # Reload context for next iteration (gets updated code, etc.)
                    context = await OptimizationContext.load(client, run_id)

                except Exception as e:
                    logger.exception(
                        "Iteration failed with exception",
                        run_id=run_id,
                        iteration=context.current_iteration,
                        error=str(e),
                    )
                    try:
                        await client.control_optimization(
                            run_id,
                            "fail",
                            termination_reason=f"iteration_exception: {str(e)}",
                        )
                    except Exception as control_error:
                        logger.error(
                            "Failed to mark optimization as failed after exception",
                            run_id=run_id,
                            original_error=str(e),
                            control_error=str(control_error),
                        )
                        # Continue anyway - return result to caller
                    return self._build_result(context, "exception", error=str(e))

            # Check why loop ended
            if context.status == "cancelled":
                logger.info(
                    "Optimization cancelled by user",
                    run_id=run_id,
                    iterations=context.current_iteration,
                )
                return self._build_result(context, "cancelled")
            elif context.status == "paused":
                logger.info(
                    "Optimization paused",
                    run_id=run_id,
                    iterations=context.current_iteration,
                )
                return self._build_result(context, "paused")
            elif context.status in ("completed", "failed"):
                logger.info(
                    "Optimization already finished",
                    run_id=run_id,
                    status=context.status,
                    iterations=context.current_iteration,
                )
                return self._build_result(context, context.status)
            else:
                # Max iterations reached
                logger.info(
                    "Max iterations reached",
                    run_id=run_id,
                    iterations=context.current_iteration,
                )
                try:
                    await client.control_optimization(
                        run_id,
                        "complete",
                        termination_reason="max_iterations",
                        best_strategy_id=context.best_strategy_id,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to mark optimization as complete after max iterations",
                        run_id=run_id,
                        error=str(e),
                    )
                    # Continue anyway - return result to caller
                return self._build_result(context, "max_iterations")

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
