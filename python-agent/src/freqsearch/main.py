"""FreqSearch Agent entry point."""

import asyncio
import signal
import sys

import structlog

from freqsearch.config import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if not settings.log_json else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(settings.log_level),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class AgentService:
    """Main agent service orchestrator."""

    def __init__(self) -> None:
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the agent service."""
        logger.info(
            "Starting FreqSearch Agent",
            env=settings.env.value,
            grpc_server=settings.grpc_server,
            llm_provider=settings.llm_provider.value,
        )

        self._running = True

        # TODO: Initialize components
        # - gRPC client
        # - RabbitMQ consumer
        # - LangGraph workflow

        logger.info("FreqSearch Agent started successfully")

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    async def stop(self) -> None:
        """Stop the agent service gracefully."""
        logger.info("Stopping FreqSearch Agent...")
        self._running = False
        self._shutdown_event.set()

        # TODO: Cleanup
        # - Close gRPC channel
        # - Close RabbitMQ connection

        logger.info("FreqSearch Agent stopped")


async def run_agent() -> None:
    """Run the agent service."""
    service = AgentService()

    # Setup signal handlers
    loop = asyncio.get_running_loop()

    def signal_handler() -> None:
        logger.info("Received shutdown signal")
        asyncio.create_task(service.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await service.start()
    except Exception as e:
        logger.exception("Agent service error", error=str(e))
        raise


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception("Fatal error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
