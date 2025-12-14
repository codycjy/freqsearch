"""Tests for iteration limit enforcement in Analyst Agent."""

import pytest
from unittest.mock import AsyncMock, patch

from freqsearch_agents.agents.analyst.nodes import submit_decision_node
from freqsearch_agents.schemas.diagnosis import DiagnosisStatus


class TestIterationLimit:
    """Tests for iteration limit enforcement in submit_decision_node."""

    @pytest.fixture
    def base_state(self):
        """Create a base state for testing."""
        return {
            "messages": [],
            "job_id": "test-job-123",
            "strategy_id": "test-strategy-456",
            "backtest_result": {
                "strategy_name": "TestStrategy",
                "strategy_code": "# test code",
            },
            "metrics": {
                "profit_pct": 15.0,
                "win_rate": 0.55,
                "max_drawdown_pct": 12.0,
                "sharpe_ratio": 1.2,
            },
            "issues": ["Low win rate"],
            "suggestion_type": "ADD_FILTER",
            "suggestion_description": "Add trend filter",
            "target_metrics": ["win_rate"],
            "confidence": 0.7,
        }

    @pytest.mark.asyncio
    async def test_iteration_limit_not_reached(self, base_state):
        """Test that NEEDS_MODIFICATION is allowed when under limit."""
        state = {
            **base_state,
            "decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
            "current_iteration": 3,
            "max_iterations": 10,
        }

        with patch("freqsearch_agents.agents.analyst.nodes.publish_event", new_callable=AsyncMock) as mock_publish:
            result = await submit_decision_node(state)

        # Should publish evolve event (not archive)
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "strategy.evolve"

        # No termination reason
        assert result == {} or result.get("termination_reason") is None

    @pytest.mark.asyncio
    async def test_iteration_limit_reached_forces_archive(self, base_state):
        """Test that NEEDS_MODIFICATION becomes ARCHIVE when limit reached."""
        state = {
            **base_state,
            "decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
            "current_iteration": 10,
            "max_iterations": 10,
        }

        with patch("freqsearch_agents.agents.analyst.nodes.publish_event", new_callable=AsyncMock) as mock_publish:
            result = await submit_decision_node(state)

        # Should publish archive event instead of evolve
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "strategy.archived"

        # Should have termination reason
        assert "termination_reason" in result
        assert "Max iterations" in result["termination_reason"]

    @pytest.mark.asyncio
    async def test_iteration_limit_exceeded(self, base_state):
        """Test that limit works when exceeded (not just equal)."""
        state = {
            **base_state,
            "decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
            "current_iteration": 15,
            "max_iterations": 10,
        }

        with patch("freqsearch_agents.agents.analyst.nodes.publish_event", new_callable=AsyncMock) as mock_publish:
            result = await submit_decision_node(state)

        # Should publish archive event
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "strategy.archived"

    @pytest.mark.asyncio
    async def test_approved_not_affected_by_limit(self, base_state):
        """Test that READY_FOR_LIVE is not affected by iteration limit."""
        state = {
            **base_state,
            "decision": DiagnosisStatus.READY_FOR_LIVE.value,
            "current_iteration": 15,
            "max_iterations": 10,
        }

        with patch("freqsearch_agents.agents.analyst.nodes.publish_event", new_callable=AsyncMock) as mock_publish:
            result = await submit_decision_node(state)

        # Should still publish approved event
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "strategy.approved"

    @pytest.mark.asyncio
    async def test_archive_not_affected_by_limit(self, base_state):
        """Test that ARCHIVE decision is not affected by iteration limit."""
        state = {
            **base_state,
            "decision": DiagnosisStatus.ARCHIVE.value,
            "current_iteration": 5,
            "max_iterations": 10,
        }

        with patch("freqsearch_agents.agents.analyst.nodes.publish_event", new_callable=AsyncMock) as mock_publish:
            result = await submit_decision_node(state)

        # Should publish archive event normally
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "strategy.archived"

    @pytest.mark.asyncio
    async def test_default_max_iterations(self, base_state):
        """Test that default max_iterations is 10 if not specified."""
        state = {
            **base_state,
            "decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
            "current_iteration": 10,
            # max_iterations not set - should default to 10
        }

        with patch("freqsearch_agents.agents.analyst.nodes.publish_event", new_callable=AsyncMock) as mock_publish:
            result = await submit_decision_node(state)

        # Should force archive because current (10) >= default max (10)
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "strategy.archived"

    @pytest.mark.asyncio
    async def test_custom_max_iterations(self, base_state):
        """Test that custom max_iterations is respected."""
        state = {
            **base_state,
            "decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
            "current_iteration": 10,
            "max_iterations": 20,  # Custom higher limit
        }

        with patch("freqsearch_agents.agents.analyst.nodes.publish_event", new_callable=AsyncMock) as mock_publish:
            result = await submit_decision_node(state)

        # Should allow evolve because current (10) < max (20)
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "strategy.evolve"
