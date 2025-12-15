"""Unit tests for Orchestrator Agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from freqsearch_agents.core.state import OrchestratorState
from freqsearch_agents.schemas.diagnosis import DiagnosisStatus
from freqsearch_agents.agents.orchestrator.nodes import (
    initialize_run_node,
    invoke_engineer_node,
    submit_backtest_node,
    wait_for_result_node,
    invoke_analyst_node,
    process_decision_node,
    increment_iteration_node,
    complete_optimization_node,
    handle_failure_node,
)
from freqsearch_agents.agents.orchestrator.agent import (
    should_continue,
    route_after_decision,
    create_orchestrator_agent,
)


@pytest.fixture
def base_state() -> OrchestratorState:
    """Create a base orchestrator state for testing."""
    return {
        "messages": [],
        "optimization_run_id": "test_run_123",
        "base_strategy_id": "base_strategy_abc",
        "current_strategy_id": "base_strategy_abc",
        "current_iteration": 0,
        "max_iterations": 10,
        "best_strategy_id": None,
        "best_result": None,
        "best_sharpe": float("-inf"),
        "current_backtest_job_id": None,
        "current_result": None,
        "analyst_decision": None,
        "analyst_feedback": None,
        "terminated": False,
        "termination_reason": None,
        "errors": [],
    }


class TestInitializeRunNode:
    """Tests for initialize_run_node."""

    @pytest.mark.asyncio
    async def test_initialization_success(self, base_state):
        """Test successful initialization."""
        with patch("freqsearch_agents.agents.orchestrator.nodes.publish_event") as mock_publish:
            result = await initialize_run_node(base_state)

            assert result["current_iteration"] == 0
            assert result["best_sharpe"] == float("-inf")
            assert result["errors"] == []
            assert result["terminated"] is False

            # Verify event published
            mock_publish.assert_called_once()
            call_args = mock_publish.call_args
            assert call_args[0][0] == "optimization.iteration.started"

    @pytest.mark.asyncio
    async def test_initialization_preserves_run_id(self, base_state):
        """Test that initialization preserves run configuration."""
        result = await initialize_run_node(base_state)

        # Should not modify core run configuration
        assert "optimization_run_id" not in result
        assert "base_strategy_id" not in result
        assert "max_iterations" not in result


class TestInvokeEngineerNode:
    """Tests for invoke_engineer_node."""

    @pytest.mark.asyncio
    async def test_first_iteration_new_mode(self, base_state):
        """Test engineer invocation in first iteration (new mode)."""
        with patch("freqsearch_agents.agents.orchestrator.nodes.run_engineer") as mock_engineer:
            mock_engineer.return_value = {
                "validation_passed": True,
                "generated_code": "# New code",
                "strategy_name": "test_strategy",
            }

            result = await invoke_engineer_node(base_state)

            # Verify engineer was called with "new" mode
            mock_engineer.assert_called_once()
            call_kwargs = mock_engineer.call_args.kwargs
            assert call_kwargs["mode"] == "new"

            # Verify state updates
            assert "current_strategy_id" in result
            assert result["current_strategy_id"].startswith("strategy_")

    @pytest.mark.asyncio
    async def test_evolution_mode_with_feedback(self, base_state):
        """Test engineer invocation with analyst feedback (evolve mode)."""
        base_state["current_iteration"] = 1
        base_state["analyst_feedback"] = {
            "suggestion_type": "risk_management",
            "suggestion_description": "Improve stop loss",
            "target_metrics": ["max_drawdown"],
        }
        base_state["current_result"] = {
            "strategy_code": "# Original code",
        }

        with patch("freqsearch_agents.agents.orchestrator.nodes.run_engineer") as mock_engineer:
            mock_engineer.return_value = {
                "validation_passed": True,
                "generated_code": "# Evolved code",
            }

            result = await invoke_engineer_node(base_state)

            # Verify engineer was called with "evolve" mode
            call_kwargs = mock_engineer.call_args.kwargs
            assert call_kwargs["mode"] == "evolve"
            assert "diagnosis" in call_kwargs["input_data"]

    @pytest.mark.asyncio
    async def test_validation_failure_handling(self, base_state):
        """Test handling of engineer validation failure."""
        with patch("freqsearch_agents.agents.orchestrator.nodes.run_engineer") as mock_engineer:
            mock_engineer.return_value = {
                "validation_passed": False,
                "validation_errors": ["Syntax error", "Missing required method"],
            }

            result = await invoke_engineer_node(base_state)

            # Verify error handling
            assert len(result["errors"]) > 0
            assert result["terminated"] is True
            assert result["termination_reason"] == "engineer_validation_failed"

    @pytest.mark.asyncio
    async def test_missing_feedback_for_evolution(self, base_state):
        """Test error when feedback is missing for evolution."""
        base_state["current_iteration"] = 1
        base_state["analyst_feedback"] = None

        result = await invoke_engineer_node(base_state)

        assert len(result["errors"]) > 0
        assert "No analyst feedback" in result["errors"][0]
        assert result["terminated"] is True


class TestSubmitBacktestNode:
    """Tests for submit_backtest_node."""

    @pytest.mark.asyncio
    async def test_successful_submission(self, base_state):
        """Test successful backtest submission."""
        base_state["current_strategy_id"] = "strategy_v1"

        with patch("freqsearch_agents.agents.orchestrator.nodes.publish_event") as mock_publish:
            result = await submit_backtest_node(base_state)

            assert "current_backtest_job_id" in result
            assert result["current_backtest_job_id"].startswith("job_")

            # Verify event published
            mock_publish.assert_called_once()
            call_args = mock_publish.call_args
            assert "job_id" in call_args[0][1]


class TestWaitForResultNode:
    """Tests for wait_for_result_node."""

    @pytest.mark.asyncio
    async def test_successful_wait(self, base_state):
        """Test successful wait for backtest completion."""
        base_state["current_backtest_job_id"] = "job_123"

        with patch("freqsearch_agents.agents.orchestrator.nodes.publish_event") as mock_publish:
            result = await wait_for_result_node(base_state, config={"poll_interval": 0.1})

            assert "current_result" in result
            assert result["current_result"]["status"] == "COMPLETED"
            assert "sharpe_ratio" in result["current_result"]

    @pytest.mark.asyncio
    async def test_missing_job_id(self, base_state):
        """Test error handling when job ID is missing."""
        base_state["current_backtest_job_id"] = None

        result = await wait_for_result_node(base_state)

        assert len(result["errors"]) > 0
        assert result["terminated"] is True
        assert result["termination_reason"] == "missing_job_id"


class TestInvokeAnalystNode:
    """Tests for invoke_analyst_node."""

    @pytest.mark.asyncio
    async def test_successful_analysis(self, base_state):
        """Test successful analyst invocation."""
        base_state["current_result"] = {
            "job_id": "job_123",
            "strategy_id": "strategy_v1",
            "sharpe_ratio": 1.5,
            "profit_pct": 10.0,
        }

        with patch("freqsearch_agents.agents.orchestrator.nodes.run_analyst") as mock_analyst:
            mock_analyst.return_value = {
                "decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
                "confidence": 0.85,
                "suggestion_type": "risk_management",
                "suggestion_description": "Improve stop loss",
                "target_metrics": ["max_drawdown"],
                "metrics": {"sharpe_ratio": 1.5},
                "issues": ["High drawdown"],
                "root_causes": ["Loose stop loss"],
            }

            result = await invoke_analyst_node(base_state)

            assert result["analyst_decision"] == DiagnosisStatus.NEEDS_MODIFICATION.value
            assert result["analyst_feedback"] is not None
            assert result["analyst_feedback"]["suggestion_type"] == "risk_management"

    @pytest.mark.asyncio
    async def test_approval_decision(self, base_state):
        """Test analyst approval decision."""
        base_state["current_result"] = {
            "job_id": "job_123",
            "sharpe_ratio": 2.5,
        }

        with patch("freqsearch_agents.agents.orchestrator.nodes.run_analyst") as mock_analyst:
            mock_analyst.return_value = {
                "decision": DiagnosisStatus.READY_FOR_LIVE.value,
                "confidence": 0.95,
            }

            result = await invoke_analyst_node(base_state)

            assert result["analyst_decision"] == DiagnosisStatus.READY_FOR_LIVE.value
            assert result["analyst_feedback"] is None  # No feedback needed for approval

    @pytest.mark.asyncio
    async def test_missing_result(self, base_state):
        """Test error when backtest result is missing."""
        base_state["current_result"] = None

        result = await invoke_analyst_node(base_state)

        assert len(result["errors"]) > 0
        assert result["terminated"] is True


class TestProcessDecisionNode:
    """Tests for process_decision_node."""

    @pytest.mark.asyncio
    async def test_new_best_strategy(self, base_state):
        """Test processing when new best strategy is found."""
        base_state["current_result"] = {
            "strategy_id": "strategy_v2",
            "sharpe_ratio": 2.0,
            "profit_pct": 15.0,
        }
        base_state["current_strategy_id"] = "strategy_v2"
        base_state["analyst_decision"] = DiagnosisStatus.NEEDS_MODIFICATION.value
        base_state["best_sharpe"] = 1.5

        with patch("freqsearch_agents.agents.orchestrator.nodes.publish_event") as mock_publish:
            result = await process_decision_node(base_state)

            assert result["best_strategy_id"] == "strategy_v2"
            assert result["best_sharpe"] == 2.0
            assert result["best_result"] is not None

            # Verify new best event published
            assert mock_publish.call_count >= 2  # new_best + iteration.completed

    @pytest.mark.asyncio
    async def test_approval_termination(self, base_state):
        """Test termination on approval."""
        base_state["current_result"] = {
            "sharpe_ratio": 2.0,
        }
        base_state["analyst_decision"] = DiagnosisStatus.READY_FOR_LIVE.value

        result = await process_decision_node(base_state)

        assert result["terminated"] is True
        assert result["termination_reason"] == "approved"

    @pytest.mark.asyncio
    async def test_max_iterations_termination(self, base_state):
        """Test termination when max iterations reached."""
        base_state["current_iteration"] = 9
        base_state["max_iterations"] = 10
        base_state["current_result"] = {"sharpe_ratio": 1.5}
        base_state["analyst_decision"] = DiagnosisStatus.NEEDS_MODIFICATION.value

        result = await process_decision_node(base_state)

        assert result["terminated"] is True
        assert result["termination_reason"] == "max_iterations_reached"

    @pytest.mark.asyncio
    async def test_archive_termination(self, base_state):
        """Test termination on archive decision."""
        base_state["current_result"] = {"sharpe_ratio": 0.5}
        base_state["analyst_decision"] = DiagnosisStatus.ARCHIVE.value

        result = await process_decision_node(base_state)

        assert result["terminated"] is True
        assert result["termination_reason"] == "archived"


class TestIncrementIterationNode:
    """Tests for increment_iteration_node."""

    @pytest.mark.asyncio
    async def test_increment(self, base_state):
        """Test iteration increment."""
        base_state["current_iteration"] = 2

        result = await increment_iteration_node(base_state)

        assert result["current_iteration"] == 3
        assert result["current_backtest_job_id"] is None
        assert result["current_result"] is None
        assert result["analyst_decision"] is None


class TestCompleteOptimizationNode:
    """Tests for complete_optimization_node."""

    @pytest.mark.asyncio
    async def test_successful_completion(self, base_state):
        """Test successful optimization completion."""
        base_state["best_strategy_id"] = "strategy_v5"
        base_state["best_sharpe"] = 2.5
        base_state["best_result"] = {
            "profit_pct": 20.0,
            "win_rate": 0.65,
            "max_drawdown_pct": 5.0,
        }
        base_state["current_iteration"] = 5
        base_state["termination_reason"] = "approved"

        with patch("freqsearch_agents.agents.orchestrator.nodes.publish_event") as mock_publish:
            result = await complete_optimization_node(base_state)

            assert result["terminated"] is True

            # Verify completion event
            mock_publish.assert_called_once()
            event_data = mock_publish.call_args[0][1]
            assert event_data["best_strategy_id"] == "strategy_v5"
            assert event_data["best_sharpe"] == 2.5


class TestHandleFailureNode:
    """Tests for handle_failure_node."""

    @pytest.mark.asyncio
    async def test_failure_handling(self, base_state):
        """Test failure event publishing."""
        base_state["errors"] = ["Error 1", "Error 2"]
        base_state["termination_reason"] = "engineer_validation_failed"

        with patch("freqsearch_agents.agents.orchestrator.nodes.publish_event") as mock_publish:
            result = await handle_failure_node(base_state)

            assert result["terminated"] is True

            # Verify failure event
            mock_publish.assert_called_once()
            event_data = mock_publish.call_args[0][1]
            assert event_data["reason"] == "engineer_validation_failed"
            assert len(event_data["errors"]) == 2


class TestRoutingLogic:
    """Tests for routing functions."""

    def test_should_continue_with_errors(self, base_state):
        """Test should_continue returns fail when errors exist."""
        base_state["errors"] = ["Some error"]

        result = should_continue(base_state)

        assert result == "fail"

    def test_should_continue_approved(self, base_state):
        """Test should_continue returns complete on approval."""
        base_state["terminated"] = True
        base_state["termination_reason"] = "approved"

        result = should_continue(base_state)

        assert result == "complete"

    def test_should_continue_max_iterations(self, base_state):
        """Test should_continue returns complete on max iterations."""
        base_state["terminated"] = True
        base_state["termination_reason"] = "max_iterations_reached"

        result = should_continue(base_state)

        assert result == "complete"

    def test_should_continue_other_termination(self, base_state):
        """Test should_continue returns fail on other termination reasons."""
        base_state["terminated"] = True
        base_state["termination_reason"] = "engineer_validation_failed"

        result = should_continue(base_state)

        assert result == "fail"

    def test_route_after_decision_iterate(self, base_state):
        """Test route_after_decision returns iterate for modification."""
        base_state["analyst_decision"] = DiagnosisStatus.NEEDS_MODIFICATION.value
        base_state["analyst_feedback"] = {"suggestion_type": "test"}

        result = route_after_decision(base_state)

        assert result == "iterate"

    def test_route_after_decision_approve(self, base_state):
        """Test route_after_decision returns complete for approval."""
        base_state["analyst_decision"] = DiagnosisStatus.READY_FOR_LIVE.value

        result = route_after_decision(base_state)

        assert result == "complete"

    def test_route_after_decision_max_iterations(self, base_state):
        """Test route_after_decision returns complete at max iterations."""
        base_state["current_iteration"] = 9
        base_state["max_iterations"] = 10
        base_state["analyst_decision"] = DiagnosisStatus.NEEDS_MODIFICATION.value

        result = route_after_decision(base_state)

        assert result == "complete"

    def test_route_after_decision_archive(self, base_state):
        """Test route_after_decision returns archive for archive decision."""
        base_state["analyst_decision"] = DiagnosisStatus.ARCHIVE.value

        result = route_after_decision(base_state)

        assert result == "archive"


class TestOrchestratorAgent:
    """Tests for orchestrator agent creation."""

    def test_create_orchestrator_agent(self):
        """Test that orchestrator agent is created successfully."""
        agent = create_orchestrator_agent()

        assert agent is not None
        # Verify it's a compiled graph
        assert hasattr(agent, "ainvoke")
        assert hasattr(agent, "astream")
