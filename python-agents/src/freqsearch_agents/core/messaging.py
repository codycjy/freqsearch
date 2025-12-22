"""RabbitMQ messaging infrastructure."""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable, Coroutine

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange
import structlog

from ..config import get_settings

logger = structlog.get_logger(__name__)


# Event routing keys
class Events:
    """RabbitMQ event routing keys."""

    # Strategy lifecycle
    STRATEGY_DISCOVERED = "strategy.discovered"
    STRATEGY_NEEDS_PROCESSING = "strategy.needs_processing"
    STRATEGY_READY_FOR_BACKTEST = "strategy.ready_for_backtest"
    STRATEGY_APPROVED = "strategy.approved"
    STRATEGY_EVOLVE = "strategy.evolve"
    STRATEGY_ARCHIVED = "strategy.archived"

    # Backtest lifecycle
    BACKTEST_SUBMITTED = "backtest.submitted"
    BACKTEST_STARTED = "backtest.started"
    BACKTEST_COMPLETED = "backtest.completed"
    BACKTEST_FAILED = "backtest.failed"

    # Scout lifecycle
    SCOUT_TRIGGER = "scout.trigger"
    SCOUT_STARTED = "scout.started"
    SCOUT_PROGRESS = "scout.progress"
    SCOUT_COMPLETED = "scout.completed"
    SCOUT_FAILED = "scout.failed"
    SCOUT_CANCELLED = "scout.cancelled"

    # Agent heartbeat
    AGENT_HEARTBEAT = "agent.heartbeat"


class MessageBroker:
    """RabbitMQ message broker for agent communication."""

    def __init__(self) -> None:
        self._connection: AbstractConnection | None = None
        self._channel: AbstractChannel | None = None
        self._exchange: AbstractExchange | None = None
        self._settings = get_settings()

    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        if self._connection is not None:
            return

        self._connection = await aio_pika.connect_robust(
            self._settings.rabbitmq.url,
        )
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._settings.rabbitmq.prefetch_count)

        # Declare exchange
        self._exchange = await self._channel.declare_exchange(
            self._settings.rabbitmq.exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )

        logger.info(
            "Connected to RabbitMQ",
            exchange=self._settings.rabbitmq.exchange_name,
        )

    async def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._channel = None
            self._exchange = None
            logger.info("Disconnected from RabbitMQ")

    async def publish(
        self,
        routing_key: str,
        body: dict[str, Any],
        correlation_id: str | None = None,
    ) -> None:
        """Publish a message to the exchange.

        Args:
            routing_key: Routing key for the message (e.g., "strategy.discovered")
            body: Message body as dictionary
            correlation_id: Optional correlation ID for tracking
        """
        if self._exchange is None:
            await self.connect()

        message = Message(
            body=json.dumps(body).encode(),
            content_type="application/json",
            correlation_id=correlation_id,
        )

        await self._exchange.publish(message, routing_key=routing_key)
        logger.debug("Published message", routing_key=routing_key, correlation_id=correlation_id)

    async def subscribe(
        self,
        routing_key: str,
        queue_name: str,
        handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to messages with a specific routing key.

        Args:
            routing_key: Routing key pattern (e.g., "strategy.*")
            queue_name: Name of the queue to create/use
            handler: Async function to handle incoming messages
        """
        if self._channel is None:
            await self.connect()

        # Declare queue
        queue = await self._channel.declare_queue(queue_name, durable=True)

        # Bind queue to exchange with routing key
        await queue.bind(self._exchange, routing_key=routing_key)

        logger.info(
            "Subscribed to messages",
            routing_key=routing_key,
            queue=queue_name,
        )

        # Start consuming
        logger.info(
            "Starting message consumer",
            routing_key=routing_key,
            queue=queue_name,
        )
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                logger.info(
                    "Received message",
                    routing_key=message.routing_key,
                    correlation_id=message.correlation_id,
                )
                async with message.process():
                    try:
                        body = json.loads(message.body.decode())
                        await handler(body)
                        logger.info(
                            "Message processed successfully",
                            routing_key=message.routing_key,
                        )
                    except Exception as e:
                        logger.error(
                            "Error processing message",
                            error=str(e),
                            routing_key=message.routing_key,
                        )
                        # Message will be requeued on exception


# Global broker instance
_broker: MessageBroker | None = None


def get_broker() -> MessageBroker:
    """Get the global message broker instance."""
    global _broker
    if _broker is None:
        _broker = MessageBroker()
    return _broker


async def publish_event(
    routing_key: str,
    body: dict[str, Any],
    correlation_id: str | None = None,
) -> None:
    """Convenience function to publish an event.

    Automatically adds event_id (UUID) and timestamp if not present.

    Args:
        routing_key: Event routing key
        body: Event payload
        correlation_id: Optional correlation ID
    """
    # Auto-generate event_id if not present or empty
    if "event_id" not in body or not body["event_id"]:
        body["event_id"] = str(uuid.uuid4())

    # Auto-add timestamp if not present
    if "timestamp" not in body:
        body["timestamp"] = datetime.now(timezone.utc).isoformat()

    # Auto-add source if not present
    if "source" not in body:
        body["source"] = "python-agents"

    broker = get_broker()
    await broker.publish(routing_key, body, correlation_id)


@asynccontextmanager
async def message_broker() -> AsyncGenerator[MessageBroker, None]:
    """Context manager for message broker lifecycle."""
    broker = get_broker()
    await broker.connect()
    try:
        yield broker
    finally:
        await broker.disconnect()
