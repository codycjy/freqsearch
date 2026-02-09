"""Retry utilities for gRPC operations with exponential backoff.

This module provides async retry decorators and helpers for handling transient
gRPC failures (UNAVAILABLE, INTERNAL, DEADLINE_EXCEEDED) with exponential backoff.
"""

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import structlog

from .client import (
    CancelledError,
    ConnectionError,
    FreqSearchClientError,
    InternalError,
    NotFoundError,
    TimeoutError,
    ValidationError,
)

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# Exceptions that should trigger retry (transient errors)
RETRYABLE_EXCEPTIONS = (
    ConnectionError,  # gRPC UNAVAILABLE
    InternalError,    # gRPC INTERNAL
    TimeoutError,     # gRPC DEADLINE_EXCEEDED
)

# Exceptions that should NOT be retried (permanent errors)
PERMANENT_EXCEPTIONS = (
    NotFoundError,        # gRPC NOT_FOUND
    ValidationError,      # gRPC INVALID_ARGUMENT, FAILED_PRECONDITION, OUT_OF_RANGE
    CancelledError,       # gRPC CANCELLED
)


def with_retry(
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to retry async functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Base delay in seconds (default: 2.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2.0)

    Returns:
        Decorator function

    Example:
        @with_retry(max_retries=3, base_delay=1.0)
        async def load_data(client, id):
            return await client.get_strategy(id)

    Retry schedule with defaults (2, 4, 8, 16, 32 seconds):
        - Attempt 1: immediate
        - Attempt 2: after 2s
        - Attempt 3: after 4s
        - Attempt 4: after 8s
        - Attempt 5: after 16s
        - Attempt 6: after 32s
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except PERMANENT_EXCEPTIONS as e:
                    # Don't retry permanent errors
                    logger.warning(
                        "Permanent error, not retrying",
                        function=func.__name__,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    raise

                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e

                    if attempt >= max_retries:
                        logger.error(
                            "Max retries exceeded",
                            function=func.__name__,
                            attempts=attempt + 1,
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    logger.warning(
                        "Retryable error, will retry",
                        function=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        retry_after_seconds=delay,
                        error=str(e),
                        error_type=type(e).__name__,
                    )

                    await asyncio.sleep(delay)

                except Exception as e:
                    # Unknown exception - log and re-raise without retry
                    logger.error(
                        "Unexpected error, not retrying",
                        function=func.__name__,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    raise

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise FreqSearchClientError("Retry logic error: no exception captured")

        return wrapper

    return decorator


async def retry_async(
    coro_func: Callable[[], T],
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    operation_name: str = "operation",
) -> T:
    """Retry an async coroutine function with exponential backoff.

    This is a functional alternative to the decorator for cases where you
    need to retry a specific call without decorating the function.

    Args:
        coro_func: Async function to retry (should be a lambda or callable)
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        operation_name: Name for logging purposes

    Returns:
        Result from the async function

    Example:
        result = await retry_async(
            lambda: client.get_strategy(id),
            max_retries=3,
            operation_name="get_strategy"
        )
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await coro_func()

        except PERMANENT_EXCEPTIONS as e:
            logger.warning(
                "Permanent error, not retrying",
                operation=operation_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

        except RETRYABLE_EXCEPTIONS as e:
            last_exception = e

            if attempt >= max_retries:
                logger.error(
                    "Max retries exceeded",
                    operation=operation_name,
                    attempts=attempt + 1,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

            delay = min(base_delay * (exponential_base ** attempt), max_delay)

            logger.warning(
                "Retryable error, will retry",
                operation=operation_name,
                attempt=attempt + 1,
                max_retries=max_retries,
                retry_after_seconds=delay,
                error=str(e),
                error_type=type(e).__name__,
            )

            await asyncio.sleep(delay)

        except Exception as e:
            logger.error(
                "Unexpected error, not retrying",
                operation=operation_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    if last_exception:
        raise last_exception
    raise FreqSearchClientError("Retry logic error: no exception captured")
