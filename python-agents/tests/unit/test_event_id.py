"""Tests for event ID (UUID) generation in messaging module."""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

from freqsearch_agents.core.messaging import publish_event, get_broker


class TestEventIdGeneration:
    """Tests for automatic event_id generation in publish_event."""

    @pytest.mark.asyncio
    async def test_auto_generates_event_id(self):
        """Test that event_id is automatically generated if not provided."""
        body = {"strategy_id": "test-123", "name": "TestStrategy"}

        with patch.object(get_broker(), "publish", new_callable=AsyncMock) as mock_publish:
            await publish_event("strategy.discovered", body)

        # Check that event_id was added
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        published_body = call_args[0][1]

        assert "event_id" in published_body
        assert published_body["event_id"] != ""

        # Verify it's a valid UUID
        try:
            uuid.UUID(published_body["event_id"])
        except ValueError:
            pytest.fail("event_id is not a valid UUID")

    @pytest.mark.asyncio
    async def test_preserves_existing_event_id(self):
        """Test that existing event_id is not overwritten."""
        existing_id = "custom-event-id-123"
        body = {
            "event_id": existing_id,
            "strategy_id": "test-123",
        }

        with patch.object(get_broker(), "publish", new_callable=AsyncMock) as mock_publish:
            await publish_event("strategy.discovered", body)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        published_body = call_args[0][1]

        assert published_body["event_id"] == existing_id

    @pytest.mark.asyncio
    async def test_replaces_empty_event_id(self):
        """Test that empty event_id is replaced with generated UUID."""
        body = {
            "event_id": "",  # Empty string
            "strategy_id": "test-123",
        }

        with patch.object(get_broker(), "publish", new_callable=AsyncMock) as mock_publish:
            await publish_event("strategy.discovered", body)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        published_body = call_args[0][1]

        assert published_body["event_id"] != ""

        # Verify it's a valid UUID
        try:
            uuid.UUID(published_body["event_id"])
        except ValueError:
            pytest.fail("event_id is not a valid UUID")

    @pytest.mark.asyncio
    async def test_auto_generates_timestamp(self):
        """Test that timestamp is automatically generated if not provided."""
        body = {"strategy_id": "test-123"}

        with patch.object(get_broker(), "publish", new_callable=AsyncMock) as mock_publish:
            await publish_event("strategy.discovered", body)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        published_body = call_args[0][1]

        assert "timestamp" in published_body
        assert published_body["timestamp"] != ""

    @pytest.mark.asyncio
    async def test_preserves_existing_timestamp(self):
        """Test that existing timestamp is not overwritten."""
        existing_ts = "2024-01-15T10:30:00Z"
        body = {
            "timestamp": existing_ts,
            "strategy_id": "test-123",
        }

        with patch.object(get_broker(), "publish", new_callable=AsyncMock) as mock_publish:
            await publish_event("strategy.discovered", body)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        published_body = call_args[0][1]

        assert published_body["timestamp"] == existing_ts

    @pytest.mark.asyncio
    async def test_auto_adds_source(self):
        """Test that source is automatically added if not provided."""
        body = {"strategy_id": "test-123"}

        with patch.object(get_broker(), "publish", new_callable=AsyncMock) as mock_publish:
            await publish_event("strategy.discovered", body)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        published_body = call_args[0][1]

        assert "source" in published_body
        assert published_body["source"] == "python-agents"

    @pytest.mark.asyncio
    async def test_preserves_existing_source(self):
        """Test that existing source is not overwritten."""
        body = {
            "source": "custom-source",
            "strategy_id": "test-123",
        }

        with patch.object(get_broker(), "publish", new_callable=AsyncMock) as mock_publish:
            await publish_event("strategy.discovered", body)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        published_body = call_args[0][1]

        assert published_body["source"] == "custom-source"

    @pytest.mark.asyncio
    async def test_unique_event_ids_per_call(self):
        """Test that each call generates a unique event_id."""
        event_ids = []

        with patch.object(get_broker(), "publish", new_callable=AsyncMock) as mock_publish:
            for _ in range(5):
                body = {"strategy_id": "test-123"}
                await publish_event("strategy.discovered", body)

        assert mock_publish.call_count == 5

        for call in mock_publish.call_args_list:
            event_id = call[0][1]["event_id"]
            assert event_id not in event_ids
            event_ids.append(event_id)

    @pytest.mark.asyncio
    async def test_correlation_id_passed_through(self):
        """Test that correlation_id is passed to broker."""
        body = {"strategy_id": "test-123"}
        correlation_id = "corr-123"

        with patch.object(get_broker(), "publish", new_callable=AsyncMock) as mock_publish:
            await publish_event("strategy.discovered", body, correlation_id=correlation_id)

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args

        assert call_args[0][2] == correlation_id
