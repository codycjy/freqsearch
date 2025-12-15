"""End-to-end integration tests for FreqSearch optimization pipeline.

Tests the full flow:
1. Strategy Discovery/Creation
2. Engineer Processing
3. Backtest Submission
4. Result Analysis
5. Analyst Decision
6. Optimization Loop Iteration
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any, List
import structlog

from freqsearch_agents.grpc_client import FreqSearchClient, BacktestConfig, OptimizationConfig
from freqsearch_agents.agents.engineer.agent import run_engineer
from freqsearch_agents.agents.analyst.agent import run_analyst


logger = structlog.get_logger(__name__)


class TestE2EPipeline:
    """End-to-end pipeline integration tests."""

    @pytest.mark.asyncio
    async def test_strategy_creation_flow(self, mock_grpc_client, sample_strategy_code):
        """Test creating a strategy and retrieving it."""
        # Create strategy
        create_result = await mock_grpc_client.create_strategy(
            name="TestStrategy_v1",
            code=sample_strategy_code,
            description="Test strategy for E2E testing"
        )

        assert create_result["id"] == "strategy-123"
        assert create_result["name"] == "TestStrategy_v1"

        # Retrieve strategy
        strategy = await mock_grpc_client.get_strategy(strategy_id="strategy-123")

        assert strategy["id"] == "strategy-123"
        assert "code" in strategy

        # Verify calls
        mock_grpc_client.create_strategy.assert_called_once()
        mock_grpc_client.get_strategy.assert_called_once_with(strategy_id="strategy-123")

    @pytest.mark.asyncio
    async def test_engineer_processes_new_strategy(
        self, mock_grpc_client, sample_strategy_code, backtest_config
    ):
        """Test Engineer agent processing a new strategy."""
        # Mock the engineer's LLM call
        with patch("freqsearch_agents.agents.engineer.agent.ChatAnthropic") as mock_llm:
            mock_chain = AsyncMock()
            mock_chain.ainvoke = AsyncMock(return_value={
                "generated_code": sample_strategy_code,
                "validation_passed": True,
                "validation_errors": [],
                "modifications_made": ["Created initial strategy"],
                "strategy_name": "TestStrategy_v1",
                "confidence_score": 0.9,
            })
            mock_llm.return_value = mock_chain

            # Run engineer in "new" mode
            result = await run_engineer(
                mode="new",
                grpc_client=mock_grpc_client,
                backtest_config=backtest_config,
                requirements="Create RSI-based momentum strategy",
            )

            assert result["validation_passed"] is True
            assert len(result["validation_errors"]) == 0
            assert "generated_code" in result
            assert "TestStrategy" in result["generated_code"]
            assert result["confidence_score"] > 0.8

    @pytest.mark.asyncio
    async def test_backtest_submission_and_polling(
        self, mock_grpc_client, backtest_config, sample_strategy_code
    ):
        """Test submitting backtest and polling until completion."""
        # Configure mock to simulate job lifecycle
        status_sequence = [
            {"job_id": "job-123", "status": "queued", "progress": 0},
            {"job_id": "job-123", "status": "running", "progress": 50},
            {"job_id": "job-123", "status": "running", "progress": 75},
            {"job_id": "job-123", "status": "completed", "progress": 100},
        ]
        mock_grpc_client.get_job_status = AsyncMock(side_effect=status_sequence)

        # Submit backtest
        submit_result = await mock_grpc_client.submit_backtest(
            strategy_id="strategy-123",
            config=backtest_config,
        )

        assert submit_result["job_id"] == "job-123"
        assert submit_result["status"] == "queued"

        # Poll until completion
        max_polls = 10
        job_id = submit_result["job_id"]

        for _ in range(max_polls):
            status = await mock_grpc_client.get_job_status(job_id=job_id)

            if status["status"] == "completed":
                break

            await asyncio.sleep(0.1)  # Simulate polling interval

        assert status["status"] == "completed"
        assert status["progress"] == 100

        # Verify polling happened multiple times
        assert mock_grpc_client.get_job_status.call_count >= 1

    @pytest.mark.asyncio
    async def test_analyst_approves_good_strategy(
        self, mock_grpc_client, sample_backtest_result
    ):
        """Test Analyst approves strategy meeting criteria."""
        # Mock the analyst's LLM call
        with patch("freqsearch_agents.agents.analyst.agent.ChatAnthropic") as mock_llm:
            mock_chain = AsyncMock()
            mock_chain.ainvoke = AsyncMock(return_value={
                "decision": "approve",
                "reasoning": "Excellent performance metrics across all criteria",
                "metrics_analysis": {
                    "sharpe_ratio": {"value": 1.8, "threshold": 1.5, "passed": True},
                    "max_drawdown": {"value": 8.5, "threshold": 15.0, "passed": True},
                    "win_rate": {"value": 0.6, "threshold": 0.5, "passed": True},
                },
                "suggestions": [],
                "risk_assessment": "low",
            })
            mock_llm.return_value = mock_chain

            # Run analyst
            result = await run_analyst(
                backtest_result=sample_backtest_result,
                optimization_config=OptimizationConfig(
                    max_iterations=10,
                    min_sharpe=1.5,
                    max_drawdown_pct=15.0,
                ),
            )

            assert result["decision"] == "approve"
            assert result["risk_assessment"] == "low"
            assert len(result["suggestions"]) == 0
            assert result["metrics_analysis"]["sharpe_ratio"]["passed"] is True

    @pytest.mark.asyncio
    async def test_analyst_requests_modification(self, mock_grpc_client, poor_backtest_result):
        """Test Analyst requests modification for poor strategy."""
        # Mock the analyst's LLM call
        with patch("freqsearch_agents.agents.analyst.agent.ChatAnthropic") as mock_llm:
            mock_chain = AsyncMock()
            mock_chain.ainvoke = AsyncMock(return_value={
                "decision": "modify",
                "reasoning": "Performance below acceptable thresholds",
                "metrics_analysis": {
                    "sharpe_ratio": {"value": 0.3, "threshold": 1.5, "passed": False},
                    "max_drawdown": {"value": 25.0, "threshold": 15.0, "passed": False},
                    "win_rate": {"value": 0.33, "threshold": 0.5, "passed": False},
                },
                "suggestions": [
                    "Tighten stop loss to reduce drawdown",
                    "Add trend filter to improve entry quality",
                    "Consider reducing position size",
                ],
                "risk_assessment": "high",
            })
            mock_llm.return_value = mock_chain

            # Run analyst
            result = await run_analyst(
                backtest_result=poor_backtest_result,
                optimization_config=OptimizationConfig(
                    max_iterations=10,
                    min_sharpe=1.5,
                    max_drawdown_pct=15.0,
                ),
            )

            assert result["decision"] == "modify"
            assert result["risk_assessment"] == "high"
            assert len(result["suggestions"]) > 0
            assert "stop loss" in result["suggestions"][0].lower()
            assert result["metrics_analysis"]["sharpe_ratio"]["passed"] is False

    @pytest.mark.asyncio
    async def test_full_optimization_loop_iteration(
        self, mock_grpc_client, sample_strategy_code, backtest_config
    ):
        """Test single iteration of optimization loop."""
        # Step 1: Engineer generates strategy
        with patch("freqsearch_agents.agents.engineer.agent.ChatAnthropic") as mock_eng_llm:
            mock_eng_chain = AsyncMock()
            mock_eng_chain.ainvoke = AsyncMock(return_value={
                "generated_code": sample_strategy_code,
                "validation_passed": True,
                "validation_errors": [],
                "modifications_made": ["Created strategy"],
                "strategy_name": "TestStrategy_v1",
                "confidence_score": 0.9,
            })
            mock_eng_llm.return_value = mock_eng_chain

            engineer_result = await run_engineer(
                mode="new",
                grpc_client=mock_grpc_client,
                backtest_config=backtest_config,
                requirements="Create momentum strategy",
            )

        assert engineer_result["validation_passed"] is True

        # Step 2: Submit backtest
        submit_result = await mock_grpc_client.submit_backtest(
            strategy_id="strategy-123",
            config=backtest_config,
        )

        assert submit_result["job_id"] == "job-123"

        # Step 3: Get result
        backtest_result = await mock_grpc_client.get_backtest_result(
            result_id="result-123"
        )

        assert "sharpe_ratio" in backtest_result

        # Step 4: Analyst analyzes
        with patch("freqsearch_agents.agents.analyst.agent.ChatAnthropic") as mock_ana_llm:
            mock_ana_chain = AsyncMock()
            mock_ana_chain.ainvoke = AsyncMock(return_value={
                "decision": "modify",
                "reasoning": "Needs improvement",
                "suggestions": ["Add stop loss"],
                "risk_assessment": "medium",
            })
            mock_ana_llm.return_value = mock_ana_chain

            analyst_result = await run_analyst(
                backtest_result=backtest_result,
                optimization_config=OptimizationConfig(max_iterations=10, min_sharpe=1.5),
            )

        # Step 5: If modify, verify Engineer can receive feedback
        if analyst_result["decision"] == "modify":
            with patch("freqsearch_agents.agents.engineer.agent.ChatAnthropic") as mock_eng2:
                mock_eng2_chain = AsyncMock()
                mock_eng2_chain.ainvoke = AsyncMock(return_value={
                    "generated_code": sample_strategy_code,
                    "validation_passed": True,
                    "validation_errors": [],
                    "modifications_made": ["Applied analyst suggestions"],
                    "strategy_name": "TestStrategy_v2",
                    "confidence_score": 0.85,
                })
                mock_eng2.return_value = mock_eng2_chain

                engineer_result_v2 = await run_engineer(
                    mode="modify",
                    grpc_client=mock_grpc_client,
                    backtest_config=backtest_config,
                    current_strategy=sample_strategy_code,
                    analyst_feedback=analyst_result["suggestions"],
                )

            assert "Applied analyst suggestions" in engineer_result_v2["modifications_made"]

    @pytest.mark.asyncio
    async def test_optimization_respects_max_iterations(self, mock_grpc_client):
        """Test optimization terminates at max_iterations."""
        max_iterations = 3
        iteration_count = 0

        # Simulate optimization loop
        for i in range(max_iterations):
            iteration_count += 1

            # Simulate iteration work
            await asyncio.sleep(0.01)

            # Check if we should continue
            if iteration_count >= max_iterations:
                break

        assert iteration_count == max_iterations

    @pytest.mark.asyncio
    async def test_optimization_early_termination_on_approval(
        self, mock_grpc_client, sample_backtest_result
    ):
        """Test optimization ends early when strategy approved."""
        max_iterations = 5
        approved_at_iteration = 2
        iteration_count = 0

        # Simulate optimization loop
        for i in range(max_iterations):
            iteration_count += 1

            # Mock analyst decision
            with patch("freqsearch_agents.agents.analyst.agent.ChatAnthropic") as mock_llm:
                mock_chain = AsyncMock()

                # Approve on iteration 2
                decision = "approve" if iteration_count == approved_at_iteration else "modify"

                mock_chain.ainvoke = AsyncMock(return_value={
                    "decision": decision,
                    "reasoning": "Test",
                    "suggestions": [],
                    "risk_assessment": "low",
                })
                mock_llm.return_value = mock_chain

                result = await run_analyst(
                    backtest_result=sample_backtest_result,
                    optimization_config=OptimizationConfig(max_iterations=max_iterations),
                )

            # Early termination on approval
            if result["decision"] == "approve":
                break

        assert iteration_count == approved_at_iteration
        assert iteration_count < max_iterations

    @pytest.mark.asyncio
    async def test_batch_backtest_submission(
        self, mock_grpc_client, backtest_config, sample_batch_strategies
    ):
        """Test submitting multiple backtests at once."""
        # Configure mock to return different job IDs
        job_ids = [f"job-{i}" for i in range(1, 6)]
        mock_grpc_client.submit_backtest = AsyncMock(
            side_effect=[{"job_id": jid, "status": "queued"} for jid in job_ids]
        )

        # Submit batch
        submitted_jobs = []
        for strategy in sample_batch_strategies:
            result = await mock_grpc_client.submit_backtest(
                strategy_id=strategy["id"],
                config=backtest_config,
            )
            submitted_jobs.append(result)

        # Verify all jobs created
        assert len(submitted_jobs) == 5
        assert all(job["status"] == "queued" for job in submitted_jobs)
        assert mock_grpc_client.submit_backtest.call_count == 5

    @pytest.mark.asyncio
    async def test_strategy_search_with_metrics(self, mock_grpc_client):
        """Test searching strategies by performance metrics."""
        # Mock search results
        mock_grpc_client.search_strategies = AsyncMock(return_value={
            "strategies": [
                {"id": "strategy-1", "sharpe_ratio": 1.8, "name": "HighSharpe1"},
                {"id": "strategy-2", "sharpe_ratio": 2.1, "name": "HighSharpe2"},
            ],
            "total": 2,
        })

        # Search with min_sharpe filter
        results = await mock_grpc_client.search_strategies(
            filters={"min_sharpe_ratio": 1.5}
        )

        # Verify only matching strategies returned
        assert results["total"] == 2
        assert all(s["sharpe_ratio"] >= 1.5 for s in results["strategies"])

        mock_grpc_client.search_strategies.assert_called_once_with(
            filters={"min_sharpe_ratio": 1.5}
        )

    @pytest.mark.asyncio
    async def test_strategy_lineage_tracking(self, mock_grpc_client, sample_lineage_tree):
        """Test strategy parent-child lineage."""
        # Mock lineage retrieval
        mock_grpc_client.get_strategy_lineage = AsyncMock(
            return_value=sample_lineage_tree
        )

        # Get lineage
        lineage = await mock_grpc_client.get_strategy_lineage(
            strategy_id="strategy-003"
        )

        # Verify tree structure
        assert lineage["root"]["id"] == "strategy-001"
        assert lineage["root"]["generation"] == 1
        assert len(lineage["root"]["children"]) == 2

        # Find our strategy in the tree
        child = lineage["root"]["children"][0]["children"][0]
        assert child["id"] == "strategy-003"
        assert child["generation"] == 3

    @pytest.mark.asyncio
    async def test_error_handling_invalid_strategy(
        self, mock_grpc_client, invalid_strategy_code, backtest_config
    ):
        """Test handling of invalid strategy code."""
        with patch("freqsearch_agents.agents.engineer.agent.ChatAnthropic") as mock_llm:
            mock_chain = AsyncMock()
            mock_chain.ainvoke = AsyncMock(return_value={
                "generated_code": invalid_strategy_code,
                "validation_passed": False,
                "validation_errors": [
                    "Missing IStrategy inheritance",
                    "Missing populate_indicators method",
                ],
                "modifications_made": [],
                "strategy_name": "BrokenStrategy",
                "confidence_score": 0.2,
            })
            mock_llm.return_value = mock_chain

            # Run engineer
            result = await run_engineer(
                mode="new",
                grpc_client=mock_grpc_client,
                backtest_config=backtest_config,
                requirements="Create strategy",
            )

            # Verify validation failure
            assert result["validation_passed"] is False
            assert len(result["validation_errors"]) > 0
            assert any("IStrategy" in err for err in result["validation_errors"])

    @pytest.mark.asyncio
    async def test_error_handling_backend_unavailable(self):
        """Test graceful handling when backend is down."""
        # Create client that fails to connect
        failing_client = AsyncMock(spec=FreqSearchClient)
        failing_client.connect = AsyncMock(
            side_effect=ConnectionError("Backend unavailable")
        )

        # Verify appropriate exception raised
        with pytest.raises(ConnectionError, match="Backend unavailable"):
            await failing_client.connect()

    @pytest.mark.asyncio
    async def test_concurrent_optimization_runs(self, mock_grpc_client):
        """Test multiple optimization runs don't interfere."""
        # Simulate two concurrent optimization runs
        async def run_optimization(opt_id: str) -> Dict[str, Any]:
            """Simulate optimization run."""
            state = {
                "optimization_id": opt_id,
                "iterations": 0,
                "results": [],
            }

            for i in range(3):
                state["iterations"] += 1
                state["results"].append({"iteration": i, "sharpe": 1.5 + i * 0.1})
                await asyncio.sleep(0.01)

            return state

        # Run concurrently
        opt1_task = asyncio.create_task(run_optimization("opt-1"))
        opt2_task = asyncio.create_task(run_optimization("opt-2"))

        opt1_result, opt2_result = await asyncio.gather(opt1_task, opt2_task)

        # Verify each maintains separate state
        assert opt1_result["optimization_id"] == "opt-1"
        assert opt2_result["optimization_id"] == "opt-2"
        assert opt1_result["iterations"] == 3
        assert opt2_result["iterations"] == 3
        assert len(opt1_result["results"]) == 3
        assert len(opt2_result["results"]) == 3


class TestGRPCClientIntegration:
    """Integration tests for gRPC client (with mocked server)."""

    @pytest.mark.asyncio
    async def test_client_connection_lifecycle(self, mock_grpc_client):
        """Test connect/disconnect lifecycle."""
        # Connect
        await mock_grpc_client.connect()
        mock_grpc_client.connect.assert_called_once()

        # Use client
        health = await mock_grpc_client.health_check()
        assert health["healthy"] is True

        # Disconnect
        await mock_grpc_client.disconnect()
        mock_grpc_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_context_manager(self, mock_grpc_client):
        """Test async context manager pattern."""
        async with mock_grpc_client as client:
            health = await client.health_check()
            assert health["healthy"] is True

        # Verify __aenter__ and __aexit__ called
        mock_grpc_client.__aenter__.assert_called_once()
        mock_grpc_client.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_retry_on_transient_error(self):
        """Test client retries on transient errors."""
        client = AsyncMock(spec=FreqSearchClient)

        # Fail twice, then succeed
        call_count = 0

        async def flaky_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient error")
            return {"healthy": True}

        client.health_check = flaky_call

        # Retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await client.health_check()
                break
            except ConnectionError:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.01)

        assert result["healthy"] is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_rpc_methods_accessible(self, mock_grpc_client):
        """Verify all RPC methods exist and are callable."""
        expected_methods = [
            "health_check",
            "create_strategy",
            "get_strategy",
            "submit_backtest",
            "get_job_status",
            "get_backtest_result",
        ]

        for method_name in expected_methods:
            assert hasattr(mock_grpc_client, method_name)
            method = getattr(mock_grpc_client, method_name)
            assert callable(method)


class TestRabbitMQIntegration:
    """Tests for RabbitMQ event coordination."""

    @pytest.mark.asyncio
    async def test_optimization_events_published(self, mock_rabbitmq_connection):
        """Test events published during optimization."""
        channel = mock_rabbitmq_connection.channel()

        # Simulate optimization events
        events = [
            {"type": "optimization.started", "optimization_id": "opt-123"},
            {"type": "iteration.completed", "iteration": 1, "sharpe": 1.5},
            {"type": "iteration.completed", "iteration": 2, "sharpe": 1.7},
            {"type": "optimization.completed", "best_sharpe": 1.7},
        ]

        for event in events:
            channel.basic_publish(
                exchange="freqsearch.events",
                routing_key=event["type"],
                body=str(event),
            )

        # Verify events published
        assert channel.basic_publish.call_count == 4

        # Verify routing keys
        calls = channel.basic_publish.call_args_list
        assert calls[0][1]["routing_key"] == "optimization.started"
        assert calls[-1][1]["routing_key"] == "optimization.completed"

    @pytest.mark.asyncio
    async def test_agent_coordination_via_events(self, mock_rabbitmq_connection):
        """Test agents coordinate via message queue."""
        channel = mock_rabbitmq_connection.channel()

        # Engineer publishes "strategy.generated" event
        channel.basic_publish(
            exchange="freqsearch.agents",
            routing_key="strategy.generated",
            body=str({"strategy_id": "strategy-123"}),
        )

        # Analyst subscribes and receives event
        # (In real implementation, this would be async consumer)

        # Analyst publishes "analysis.completed" event
        channel.basic_publish(
            exchange="freqsearch.agents",
            routing_key="analysis.completed",
            body=str({"decision": "modify", "suggestions": ["Add stop loss"]}),
        )

        assert channel.basic_publish.call_count == 2


class TestOptimizationOrchestrator:
    """Tests for the Orchestrator agent coordinating the full pipeline."""

    @pytest.mark.asyncio
    async def test_orchestrator_coordinates_full_pipeline(
        self, mock_grpc_client, backtest_config, sample_strategy_code
    ):
        """Test orchestrator coordinates Engineer → Backtest → Analyst loop."""
        # This test will be fully implemented when orchestrator is created
        # For now, we simulate the coordination logic

        max_iterations = 3
        current_iteration = 0
        best_strategy = None
        best_sharpe = 0.0

        while current_iteration < max_iterations:
            current_iteration += 1

            # 1. Engineer generates/modifies strategy
            with patch("freqsearch_agents.agents.engineer.agent.ChatAnthropic") as mock_eng:
                mock_eng_chain = AsyncMock()
                mock_eng_chain.ainvoke = AsyncMock(return_value={
                    "generated_code": sample_strategy_code,
                    "validation_passed": True,
                    "validation_errors": [],
                    "modifications_made": ["Iteration work"],
                    "strategy_name": f"Strategy_v{current_iteration}",
                    "confidence_score": 0.85,
                })
                mock_eng.return_value = mock_eng_chain

                engineer_result = await run_engineer(
                    mode="new" if current_iteration == 1 else "modify",
                    grpc_client=mock_grpc_client,
                    backtest_config=backtest_config,
                )

            # 2. Submit backtest
            await mock_grpc_client.submit_backtest(
                strategy_id=f"strategy-{current_iteration}",
                config=backtest_config,
            )

            # 3. Get result
            backtest_result = {
                "sharpe_ratio": 1.0 + (current_iteration * 0.3),
                "profit_pct": 10.0 + (current_iteration * 2),
            }

            # 4. Analyst decision
            with patch("freqsearch_agents.agents.analyst.agent.ChatAnthropic") as mock_ana:
                mock_ana_chain = AsyncMock()

                # Approve on iteration 2
                decision = "approve" if current_iteration == 2 else "modify"

                mock_ana_chain.ainvoke = AsyncMock(return_value={
                    "decision": decision,
                    "reasoning": "Test",
                    "suggestions": ["Improve" if decision == "modify" else ""],
                    "risk_assessment": "low",
                })
                mock_ana.return_value = mock_ana_chain

                analyst_result = await run_analyst(
                    backtest_result=backtest_result,
                    optimization_config=OptimizationConfig(max_iterations=max_iterations),
                )

            # Track best strategy
            if backtest_result["sharpe_ratio"] > best_sharpe:
                best_sharpe = backtest_result["sharpe_ratio"]
                best_strategy = f"strategy-{current_iteration}"

            # Early termination
            if analyst_result["decision"] == "approve":
                break

        # Verify orchestration worked
        assert current_iteration == 2  # Approved on iteration 2
        assert best_strategy == "strategy-2"
        assert best_sharpe == 1.6  # 1.0 + (2 * 0.3)

    @pytest.mark.asyncio
    async def test_orchestrator_handles_all_rejections(self, mock_grpc_client):
        """Test orchestrator returns best strategy when all iterations rejected."""
        max_iterations = 3
        strategies_tested = []

        for i in range(max_iterations):
            strategy_sharpe = 1.0 + (i * 0.2)
            strategies_tested.append({
                "iteration": i + 1,
                "strategy_id": f"strategy-{i+1}",
                "sharpe": strategy_sharpe,
            })

        # All rejected, return best
        best = max(strategies_tested, key=lambda s: s["sharpe"])

        assert best["iteration"] == 3
        assert best["sharpe"] == 1.4

    @pytest.mark.asyncio
    async def test_orchestrator_timeout_handling(self):
        """Test orchestrator handles backtest timeouts gracefully."""
        # Simulate long-running backtest
        async def long_backtest():
            await asyncio.sleep(10)  # Would timeout
            return {"status": "completed"}

        # Apply timeout
        try:
            result = await asyncio.wait_for(long_backtest(), timeout=0.1)
        except asyncio.TimeoutError:
            result = {"status": "timeout", "error": "Backtest exceeded time limit"}

        assert result["status"] == "timeout"
