"""Optimization context management for external loop orchestrator.

This module handles loading and saving optimization state between
single-iteration graph executions, using PostgreSQL via gRPC.
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

from ...grpc_client.client import FreqSearchClient
from ...core.state import SingleIterationState

logger = structlog.get_logger(__name__)


@dataclass
class OptimizationContext:
    """Optimization context loaded from and persisted to PostgreSQL.

    This context is passed between iterations of the external optimization loop.
    Each iteration loads context, runs a single-iteration graph, and saves results.
    """

    # Run identification
    run_id: str
    base_strategy_id: str

    # Iteration tracking
    current_iteration: int
    max_iterations: int

    # Best tracking
    best_strategy_id: str | None
    best_sharpe: float

    # Current strategy (evolves each iteration)
    current_strategy_id: str
    current_code: str

    # Feedback from previous iteration
    previous_feedback: str | None

    # Configuration
    backtest_config: dict[str, Any] = field(default_factory=dict)

    # Status
    status: str = "running"  # "pending", "running", "paused", "completed", "failed", "cancelled"

    @classmethod
    async def load(
        cls,
        client: FreqSearchClient,
        run_id: str,
    ) -> "OptimizationContext":
        """Load optimization context from backend.

        Args:
            client: Connected gRPC client
            run_id: Optimization run ID

        Returns:
            Loaded OptimizationContext
        """
        logger.info("Loading optimization context", run_id=run_id)

        # Get optimization run with iterations
        run_data = await client.get_optimization_run(run_id)
        run = run_data["run"]
        iterations = run_data.get("iterations", [])

        # Determine current strategy and code
        current_strategy_id = run.get("best_strategy_id") or run["base_strategy_id"]

        # Get code from current strategy
        strategy_data = await client.get_strategy(current_strategy_id)
        current_code = strategy_data.get("strategy", {}).get("code", "")

        # Get feedback from latest iteration if exists
        previous_feedback = None
        if iterations:
            latest = iterations[-1]
            if latest.get("analyst_feedback"):
                previous_feedback = latest["analyst_feedback"]

        # Parse config
        config = run.get("config", {})
        backtest_config = config.get("backtest_config", {})

        context = cls(
            run_id=run_id,
            base_strategy_id=run["base_strategy_id"],
            current_iteration=run.get("current_iteration", 0),
            max_iterations=run.get("max_iterations", 10),
            best_strategy_id=run.get("best_strategy_id"),
            best_sharpe=run.get("best_sharpe", float("-inf")),
            current_strategy_id=current_strategy_id,
            current_code=current_code,
            previous_feedback=previous_feedback,
            backtest_config=backtest_config,
            status=run.get("status", "running"),
        )

        logger.info(
            "Optimization context loaded",
            run_id=run_id,
            iteration=context.current_iteration,
            max_iterations=context.max_iterations,
            best_sharpe=context.best_sharpe,
        )

        return context

    def to_iteration_state(self) -> SingleIterationState:
        """Convert context to SingleIterationState for graph execution.

        Returns:
            SingleIterationState ready for graph invocation
        """
        return SingleIterationState(
            # Context
            optimization_run_id=self.run_id,
            current_iteration=self.current_iteration,
            base_strategy_id=self.base_strategy_id,
            current_strategy_id=self.current_strategy_id,
            backtest_config=self.backtest_config,
            # Input
            input_code=self.current_code,
            input_feedback=self.previous_feedback,
            mode="new" if self.current_iteration == 0 else "evolve",
            # Best tracking
            best_sharpe=self.best_sharpe,
            best_strategy_id=self.best_strategy_id,
            # Outputs (initialized)
            engineer_result=None,
            generated_strategy_id=None,
            backtest_job_id=None,
            backtest_result=None,
            analyst_decision=None,
            analyst_feedback=None,
            # Validation
            validation_passed=False,
            validation_retry_count=0,
            # Control
            should_terminate=False,
            termination_reason=None,
            is_new_best=False,
            new_best_sharpe=None,
        )

    async def save_iteration_result(
        self,
        client: FreqSearchClient,
        result: SingleIterationState,
    ) -> None:
        """Save iteration result to backend.

        Args:
            client: Connected gRPC client
            result: Completed iteration state
        """
        logger.info(
            "Saving iteration result",
            run_id=self.run_id,
            iteration=self.current_iteration,
            is_new_best=result.get("is_new_best", False),
        )

        # Update best if this iteration found a better strategy
        if result.get("is_new_best") and result.get("generated_strategy_id"):
            self.best_strategy_id = result["generated_strategy_id"]
            self.best_sharpe = result.get("new_best_sharpe", self.best_sharpe)

        # Update current strategy for next iteration
        if result.get("generated_strategy_id"):
            self.current_strategy_id = result["generated_strategy_id"]

        # Store feedback for next iteration
        if result.get("analyst_feedback"):
            self.previous_feedback = result["analyst_feedback"]

        # Increment iteration
        self.current_iteration += 1

        # Note: The backend tracks iteration via the iteration table
        # We just need to control the run status appropriately
        if result.get("should_terminate"):
            reason = result.get("termination_reason", "unknown")
            if reason == "approved":
                await client.control_optimization(
                    self.run_id,
                    "complete",
                    termination_reason=reason,
                    best_strategy_id=self.best_strategy_id,
                )
            elif reason in ("archived", "validation_failed"):
                await client.control_optimization(
                    self.run_id,
                    "fail",
                    termination_reason=reason,
                )
            # max_iterations is handled by the runner

        logger.info(
            "Iteration result saved",
            run_id=self.run_id,
            new_iteration=self.current_iteration,
            best_sharpe=self.best_sharpe,
        )

    def is_complete(self) -> bool:
        """Check if optimization is complete.

        Returns:
            True if optimization should not continue
        """
        return self.status in ("completed", "failed", "cancelled")

    def has_iterations_remaining(self) -> bool:
        """Check if there are iterations remaining.

        Returns:
            True if current_iteration < max_iterations
        """
        return self.current_iteration < self.max_iterations
