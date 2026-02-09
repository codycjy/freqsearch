"""Optimization context management for external loop orchestrator.

This module handles loading and saving optimization state between
single-iteration graph executions, using PostgreSQL via gRPC.
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

from ...core.state import SingleIterationState
from ...grpc_client.client import FreqSearchClient
from ...grpc_client.retry import with_retry

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

    # === Baseline tracking ===
    baseline_completed: bool = False  # baseline is completed
    baseline_strategy_id: str | None = None  # baseline strategy ID
    baseline_result: dict[str, Any] | None = None  # baseline backtest result

    # === Previous iteration data (for Analyst-First) ===
    previous_backtest_result: dict[str, Any] | None = None  # previous backtest result

    def determine_mode(self) -> str:
        """Determine the mode for the current iteration.

        Returns:
            "baseline" if iteration 0
            "improve" if iteration 1+
        """
        if self.current_iteration == 0:
            return "baseline"
        return "improve"

    @classmethod
    @with_retry(max_retries=5, base_delay=2.0)
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

        # Get optimization run with iterations (with retry)
        run_data = await client.get_optimization_run(run_id)
        run = run_data["run"]
        iterations = run_data.get("iterations", [])

        # Determine current strategy and code
        current_strategy_id = run.get("best_strategy_id") or run["base_strategy_id"]

        # Get code from current strategy (with retry)
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

        # Check if baseline is completed (iteration > 0 means baseline is done)
        baseline_completed = run.get("current_iteration", 0) > 0

        # Load baseline result and previous backtest result
        baseline_result = None
        baseline_strategy_id = None
        previous_backtest_result = None

        if iterations:
            # First iteration is baseline
            if len(iterations) > 0:
                first_iter = iterations[0]
                if first_iter.get("iteration_number", 0) == 0:
                    baseline_result = first_iter.get("result")
                    baseline_strategy_id = first_iter.get("strategy_id") or run["base_strategy_id"]

            # Latest iteration result as previous
            latest = iterations[-1]
            previous_backtest_result = latest.get("result")

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
            baseline_completed=baseline_completed,
            baseline_strategy_id=baseline_strategy_id,
            baseline_result=baseline_result,
            previous_backtest_result=previous_backtest_result,
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
        mode = self.determine_mode()

        return SingleIterationState(
            # Context
            optimization_run_id=self.run_id,
            current_iteration=self.current_iteration,
            base_strategy_id=self.base_strategy_id,
            current_strategy_id=self.current_strategy_id,
            backtest_config=self.backtest_config,
            # Input
            input_code=self.current_code,
            mode=mode,
            # Baseline related
            baseline_result=self.baseline_result,
            baseline_strategy_id=self.baseline_strategy_id,
            # Analyst-First related
            previous_backtest_result=self.previous_backtest_result,
            diagnosis_report=None,
            # Pre-Backtest loop
            code_iteration_count=0,
            max_code_iterations=3,
            code_review_passed=False,
            code_review_feedback=None,
            # Best tracking
            best_sharpe=self.best_sharpe,
            best_strategy_id=self.best_strategy_id,
            # Outputs (initialized)
            engineer_result=None,
            generated_code=None,
            generated_strategy_id=None,
            backtest_job_id=None,
            backtest_result=None,
            analyst_decision=None,
            analyst_feedback=None,
            # Validation
            validation_passed=False,
            validation_retry_count=0,
            # Improvements
            improvement_vs_baseline=None,
            improvement_vs_previous=None,
            # Control
            should_terminate=False,
            termination_reason=None,
            is_new_best=False,
            new_best_sharpe=None,
        )

    @with_retry(max_retries=5, base_delay=2.0)
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
            mode=result.get("mode"),
            is_new_best=result.get("is_new_best", False),
        )

        # Handle baseline iteration
        if result.get("mode") == "baseline":
            self.baseline_completed = True
            self.baseline_strategy_id = result.get("baseline_strategy_id") or self.base_strategy_id
            self.baseline_result = result.get("backtest_result")
            # Save backtest result for next iteration
            self.previous_backtest_result = result.get("backtest_result")
            # After baseline completes, current_iteration becomes 1
            self.current_iteration = 1
            logger.info(
                "Baseline completed",
                run_id=self.run_id,
                baseline_strategy_id=self.baseline_strategy_id,
            )
            return

        # Handle improve iteration
        # Save previous backtest result
        self.previous_backtest_result = result.get("backtest_result")

        # Update best
        if result.get("is_new_best") and result.get("generated_strategy_id"):
            self.best_strategy_id = result["generated_strategy_id"]
            self.best_sharpe = result.get("new_best_sharpe", self.best_sharpe)

        # Update current strategy
        if result.get("generated_strategy_id"):
            self.current_strategy_id = result["generated_strategy_id"]
            # Get new code (with retry handled by decorator on parent method)
            try:
                strategy_data = await client.get_strategy(self.current_strategy_id)
                self.current_code = strategy_data.get("strategy", {}).get("code", "")
            except Exception as e:
                logger.warning("Failed to get strategy code", error=str(e))

        # Increment iteration
        self.current_iteration += 1

        # Handle termination (with retry handled by decorator on parent method)
        if result.get("should_terminate"):
            reason = result.get("termination_reason", "unknown")
            if reason in ("approved", "archived"):
                try:
                    await client.control_optimization(
                        self.run_id,
                        "complete",
                        termination_reason=reason,
                        best_strategy_id=self.best_strategy_id,
                    )
                    self.status = "completed"
                except Exception as e:
                    logger.error("Failed to complete optimization", error=str(e))
                    raise

        logger.info(
            "Iteration result saved",
            run_id=self.run_id,
            new_iteration=self.current_iteration,
        )

    def is_complete(self) -> bool:
        """Check if optimization is complete.

        Returns:
            True if optimization should not continue
        """
        return self.status in ("completed", "failed", "cancelled")

    def has_iterations_remaining(self) -> bool:
        """Check if there are iterations remaining and not cancelled/stopped.

        Returns:
            True if current_iteration < max_iterations and status allows continuing
        """
        # Don't continue if optimization was cancelled, paused, or already complete
        if self.status in ("cancelled", "paused", "completed", "failed"):
            return False
        return self.current_iteration < self.max_iterations
