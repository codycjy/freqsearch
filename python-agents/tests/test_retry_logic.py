"""Tests for retry logic with exponential backoff."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
import grpc

from src.freqsearch_agents.grpc_client.retry import (
    with_retry,
    retry_async,
    RETRYABLE_EXCEPTIONS,
    PERMANENT_EXCEPTIONS,
)
from src.freqsearch_agents.grpc_client.client import (
    ConnectionError,
    InternalError,
    TimeoutError,
    NotFoundError,
    ValidationError,
)


class TestRetryDecorator:
    """Test suite for @with_retry decorator."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Test that successful calls don't retry."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.1)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Test that transient errors trigger retry."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.1)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Backend unavailable", grpc.StatusCode.UNAVAILABLE)
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 3  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_no_retry_on_permanent_error(self):
        """Test that permanent errors don't retry."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.1)
        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise NotFoundError("Resource not found", grpc.StatusCode.NOT_FOUND)

        with pytest.raises(NotFoundError):
            await failing_func()

        assert call_count == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that max retries are respected."""
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.1)
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise InternalError("Internal error", grpc.StatusCode.INTERNAL)

        with pytest.raises(InternalError):
            await always_failing()

        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Test that exponential backoff delays are correct."""
        call_times = []

        @with_retry(max_retries=3, base_delay=0.1, exponential_base=2.0)
        async def timed_func():
            call_times.append(asyncio.get_event_loop().time())
            if len(call_times) < 3:
                raise TimeoutError("Timeout", grpc.StatusCode.DEADLINE_EXCEEDED)
            return "success"

        await timed_func()

        # Verify delays: 0, 0.1, 0.2
        assert len(call_times) == 3
        # Allow 50% tolerance for timing
        assert call_times[1] - call_times[0] >= 0.05  # ~0.1s delay
        assert call_times[2] - call_times[1] >= 0.15  # ~0.2s delay

    @pytest.mark.asyncio
    async def test_all_retryable_exceptions(self):
        """Test all transient exception types."""
        for exc_class in RETRYABLE_EXCEPTIONS:
            call_count = 0

            @with_retry(max_retries=2, base_delay=0.1)
            async def func():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise exc_class("Transient error", grpc.StatusCode.UNAVAILABLE)
                return "success"

            result = await func()
            assert result == "success"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_permanent_exceptions(self):
        """Test all permanent exception types don't retry."""
        for exc_class in PERMANENT_EXCEPTIONS:
            call_count = 0

            @with_retry(max_retries=3, base_delay=0.1)
            async def func():
                nonlocal call_count
                call_count += 1
                raise exc_class("Permanent error", grpc.StatusCode.NOT_FOUND)

            with pytest.raises(exc_class):
                await func()

            assert call_count == 1  # No retries


class TestRetryAsync:
    """Test suite for retry_async helper function."""

    @pytest.mark.asyncio
    async def test_retry_async_success(self):
        """Test retry_async with successful call."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_async(func, max_retries=3, base_delay=0.1)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_with_retries(self):
        """Test retry_async with transient failures."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Unavailable", grpc.StatusCode.UNAVAILABLE)
            return "recovered"

        result = await retry_async(
            func,
            max_retries=5,
            base_delay=0.1,
            operation_name="test_operation",
        )
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_permanent_error(self):
        """Test retry_async doesn't retry permanent errors."""
        call_count = 0

        async def func():
            nonlocal call_count
            call_count += 1
            raise ValidationError("Invalid", grpc.StatusCode.INVALID_ARGUMENT)

        with pytest.raises(ValidationError):
            await retry_async(func, max_retries=3, base_delay=0.1)

        assert call_count == 1


class TestIntegrationWithContext:
    """Integration tests with OptimizationContext."""

    @pytest.mark.asyncio
    async def test_context_load_with_retry(self):
        """Test that OptimizationContext.load has retry decorator."""
        from src.freqsearch_agents.agents.orchestrator.context import OptimizationContext

        # Verify the load method has been decorated
        assert hasattr(OptimizationContext.load, "__wrapped__")

    @pytest.mark.asyncio
    async def test_context_save_with_retry(self):
        """Test that OptimizationContext.save_iteration_result has retry decorator."""
        from src.freqsearch_agents.agents.orchestrator.context import OptimizationContext

        # Verify the save_iteration_result method has been decorated
        assert hasattr(OptimizationContext.save_iteration_result, "__wrapped__")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
