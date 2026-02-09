"""Integration test: Retry logic with simulated backend restart."""

import asyncio
from unittest.mock import AsyncMock, patch

import grpc
import pytest

from src.freqsearch_agents.grpc_client.client import ConnectionError, FreqSearchClient
from src.freqsearch_agents.grpc_client.retry import with_retry


class TestBackendRestartScenario:
    """Simulate real-world backend restart during optimization."""

    @pytest.mark.asyncio
    async def test_optimization_survives_backend_restart(self):
        """Test that optimization continues after backend restart.

        Simulates:
        1. Backend is healthy
        2. Backend goes down (UNAVAILABLE)
        3. Backend comes back up after 2 retries
        4. Optimization completes successfully
        """
        call_count = 0
        backend_down_calls = 2  # Simulate 2 failed attempts

        @with_retry(max_retries=5, base_delay=0.1)
        async def load_context():
            nonlocal call_count
            call_count += 1

            if call_count <= backend_down_calls:
                # Simulate backend down
                raise ConnectionError(
                    "Backend unavailable during restart",
                    grpc.StatusCode.UNAVAILABLE,
                )

            # Backend recovered
            return {
                "run_id": "test-123",
                "status": "running",
                "iteration": 3,
            }

        # Execute with simulated backend restart
        result = await load_context()

        # Verify success after retries
        assert result["run_id"] == "test-123"
        assert result["status"] == "running"
        assert call_count == backend_down_calls + 1  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_multiple_operations_with_intermittent_failures(self):
        """Test multiple operations with different failure patterns."""
        operation_calls = {"load": 0, "save": 0, "control": 0}

        @with_retry(max_retries=3, base_delay=0.1)
        async def load_operation():
            operation_calls["load"] += 1
            if operation_calls["load"] == 1:
                raise ConnectionError("Temporary failure", grpc.StatusCode.UNAVAILABLE)
            return "load_success"

        @with_retry(max_retries=3, base_delay=0.1)
        async def save_operation():
            operation_calls["save"] += 1
            if operation_calls["save"] <= 2:
                raise ConnectionError("Temporary failure", grpc.StatusCode.UNAVAILABLE)
            return "save_success"

        @with_retry(max_retries=3, base_delay=0.1)
        async def control_operation():
            operation_calls["control"] += 1
            return "control_success"

        # Run all operations
        load_result = await load_operation()
        save_result = await save_operation()
        control_result = await control_operation()

        # Verify all succeeded with retries
        assert load_result == "load_success"
        assert save_result == "save_success"
        assert control_result == "control_success"

        # Verify retry counts
        assert operation_calls["load"] == 2  # 1 failure + 1 success
        assert operation_calls["save"] == 3  # 2 failures + 1 success
        assert operation_calls["control"] == 1  # No failures

    @pytest.mark.asyncio
    async def test_concurrent_operations_with_retry(self):
        """Test that concurrent operations handle retries independently."""
        results = []
        call_counts = {"op1": 0, "op2": 0, "op3": 0}

        @with_retry(max_retries=3, base_delay=0.05)
        async def operation_1():
            call_counts["op1"] += 1
            if call_counts["op1"] == 1:
                raise ConnectionError("Temp failure", grpc.StatusCode.UNAVAILABLE)
            await asyncio.sleep(0.1)
            return "op1_done"

        @with_retry(max_retries=3, base_delay=0.05)
        async def operation_2():
            call_counts["op2"] += 1
            await asyncio.sleep(0.1)
            return "op2_done"

        @with_retry(max_retries=3, base_delay=0.05)
        async def operation_3():
            call_counts["op3"] += 1
            if call_counts["op3"] <= 2:
                raise ConnectionError("Temp failure", grpc.StatusCode.UNAVAILABLE)
            await asyncio.sleep(0.1)
            return "op3_done"

        # Run concurrently
        results = await asyncio.gather(operation_1(), operation_2(), operation_3())

        # Verify all completed
        assert results == ["op1_done", "op2_done", "op3_done"]

        # Verify independent retry counts
        assert call_counts["op1"] == 2  # 1 retry
        assert call_counts["op2"] == 1  # No retries
        assert call_counts["op3"] == 3  # 2 retries

    @pytest.mark.asyncio
    async def test_optimization_context_load_resilience(self):
        """Test OptimizationContext.load() with simulated failures."""
        from src.freqsearch_agents.agents.orchestrator.context import (
            OptimizationContext,
        )

        # Create mock client
        mock_client = AsyncMock(spec=FreqSearchClient)

        # Simulate transient failure then success
        call_count = {"count": 0}

        async def mock_get_optimization_run(run_id):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise ConnectionError("Backend down", grpc.StatusCode.UNAVAILABLE)
            return {
                "run": {
                    "base_strategy_id": "base-123",
                    "current_iteration": 2,
                    "max_iterations": 10,
                    "best_strategy_id": "best-456",
                    "best_sharpe": 1.5,
                    "status": "running",
                },
                "iterations": [],
            }

        async def mock_get_strategy(strategy_id):
            return {"strategy": {"id": strategy_id, "code": "# strategy code"}}

        mock_client.get_optimization_run = mock_get_optimization_run
        mock_client.get_strategy = mock_get_strategy

        # Load context (should retry and succeed)
        context = await OptimizationContext.load(mock_client, "run-123")

        # Verify context loaded correctly
        assert context.run_id == "run-123"
        assert context.current_iteration == 2
        assert context.best_strategy_id == "best-456"
        assert call_count["count"] == 2  # 1 failure + 1 success

    @pytest.mark.asyncio
    async def test_save_iteration_with_control_retry(self):
        """Test save_iteration_result() retries control_optimization."""
        from src.freqsearch_agents.agents.orchestrator.context import (
            OptimizationContext,
        )
        from src.freqsearch_agents.core.state import SingleIterationState

        # Create mock client
        mock_client = AsyncMock(spec=FreqSearchClient)

        # Mock get_strategy (no failures)
        async def mock_get_strategy(strategy_id):
            return {"strategy": {"id": strategy_id, "code": "# updated code"}}

        # Mock control_optimization with retry
        control_calls = {"count": 0}

        async def mock_control_optimization(run_id, action, **kwargs):
            control_calls["count"] += 1
            if control_calls["count"] == 1:
                raise ConnectionError("Network error", grpc.StatusCode.UNAVAILABLE)
            return {"success": True}

        mock_client.get_strategy = mock_get_strategy
        mock_client.control_optimization = mock_control_optimization

        # Create context
        context = OptimizationContext(
            run_id="test-run",
            base_strategy_id="base-123",
            current_iteration=1,
            max_iterations=5,
            best_strategy_id=None,
            best_sharpe=float("-inf"),
            current_strategy_id="current-456",
            current_code="# old code",
            previous_feedback=None,
        )

        # Create iteration result with termination
        result = SingleIterationState(
            optimization_run_id="test-run",
            current_iteration=1,
            base_strategy_id="base-123",
            current_strategy_id="current-456",
            mode="improve",
            generated_strategy_id="new-789",
            is_new_best=True,
            new_best_sharpe=2.0,
            should_terminate=True,
            termination_reason="approved",
        )

        # Save with retry (will call control_optimization)
        await context.save_iteration_result(mock_client, result)

        # Verify retry happened for control_optimization
        assert control_calls["count"] == 2  # 1 failure + 1 success

        # Verify context updated
        assert context.current_strategy_id == "new-789"
        assert context.best_strategy_id == "new-789"
        assert context.best_sharpe == 2.0
        assert context.status == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
