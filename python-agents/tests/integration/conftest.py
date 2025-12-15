"""Shared fixtures for integration tests."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List
import structlog

from freqsearch_agents.grpc_client import FreqSearchClient, BacktestConfig, OptimizationConfig


logger = structlog.get_logger(__name__)


@pytest.fixture
def sample_strategy_code() -> str:
    """Sample Freqtrade strategy code for testing."""
    return '''
from freqtrade.strategy import IStrategy
import talib.abstract as ta
import pandas as pd


class TestStrategy(IStrategy):
    """Sample test strategy for E2E testing."""

    minimal_roi = {
        "0": 0.10,
        "30": 0.05,
        "60": 0.01
    }

    stoploss = -0.10
    timeframe = "5m"

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Add RSI indicator."""
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Define entry conditions."""
        dataframe.loc[
            (dataframe["rsi"] < 30),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """Define exit conditions."""
        dataframe.loc[
            (dataframe["rsi"] > 70),
            "exit_long"
        ] = 1
        return dataframe
'''


@pytest.fixture
def invalid_strategy_code() -> str:
    """Invalid strategy code for error testing."""
    return '''
class BrokenStrategy:
    # Missing IStrategy inheritance
    # Missing required methods
    pass
'''


@pytest.fixture
def backtest_config() -> BacktestConfig:
    """Standard backtest configuration for tests."""
    return BacktestConfig(
        exchange="okx",
        pairs=["BTC/USDT", "ETH/USDT"],
        timeframe="5m",
        timerange_start="20241001",
        timerange_end="20241101",
        dry_run_wallet=1000.0,
        max_open_trades=3,
        stake_amount="unlimited",
    )


@pytest.fixture
def optimization_config() -> OptimizationConfig:
    """Standard optimization configuration."""
    return OptimizationConfig(
        max_iterations=10,
        target_metric="sharpe_ratio",
        min_sharpe=1.5,
        max_drawdown_pct=15.0,
        min_trades=20,
    )


@pytest.fixture
def sample_backtest_result() -> Dict[str, Any]:
    """Sample successful backtest result with good metrics."""
    return {
        "id": "result-123",
        "job_id": "job-123",
        "strategy_id": "strategy-123",
        "total_trades": 50,
        "winning_trades": 30,
        "losing_trades": 20,
        "win_rate": 0.6,
        "profit_pct": 15.5,
        "sharpe_ratio": 1.8,
        "sortino_ratio": 2.1,
        "max_drawdown_pct": 8.5,
        "profit_factor": 1.9,
        "avg_trade_duration_minutes": 120,
        "completed_at": "2024-12-14T10:00:00Z",
    }


@pytest.fixture
def poor_backtest_result() -> Dict[str, Any]:
    """Sample backtest result with poor metrics."""
    return {
        "id": "result-456",
        "job_id": "job-456",
        "strategy_id": "strategy-456",
        "total_trades": 15,
        "winning_trades": 5,
        "losing_trades": 10,
        "win_rate": 0.33,
        "profit_pct": -8.5,
        "sharpe_ratio": 0.3,
        "sortino_ratio": 0.2,
        "max_drawdown_pct": 25.0,
        "profit_factor": 0.7,
        "avg_trade_duration_minutes": 45,
        "completed_at": "2024-12-14T10:30:00Z",
    }


@pytest.fixture
def sample_strategy_metadata() -> Dict[str, Any]:
    """Sample strategy metadata."""
    return {
        "id": "strategy-123",
        "name": "TestStrategy_v1",
        "created_at": "2024-12-14T09:00:00Z",
        "description": "RSI-based momentum strategy",
        "parent_id": None,
        "generation": 1,
        "tags": ["rsi", "momentum", "test"],
    }


@pytest.fixture
async def mock_grpc_client():
    """Create mocked gRPC client with common responses."""
    client = AsyncMock(spec=FreqSearchClient)

    # Health check
    client.health_check = AsyncMock(return_value={"healthy": True, "version": "1.0.0"})

    # Strategy creation
    client.create_strategy = AsyncMock(return_value={
        "id": "strategy-123",
        "name": "TestStrategy_v1",
        "created_at": "2024-12-14T09:00:00Z",
    })

    # Strategy retrieval
    client.get_strategy = AsyncMock(return_value={
        "id": "strategy-123",
        "name": "TestStrategy_v1",
        "code": "class TestStrategy(IStrategy): pass",
        "created_at": "2024-12-14T09:00:00Z",
    })

    # Backtest submission
    client.submit_backtest = AsyncMock(return_value={
        "job_id": "job-123",
        "status": "queued",
        "created_at": "2024-12-14T09:30:00Z",
    })

    # Job status (starts queued, then running, then completed)
    client.get_job_status = AsyncMock(return_value={
        "job_id": "job-123",
        "status": "completed",
        "progress": 100,
    })

    # Backtest result
    client.get_backtest_result = AsyncMock(return_value={
        "id": "result-123",
        "job_id": "job-123",
        "strategy_id": "strategy-123",
        "sharpe_ratio": 1.8,
        "profit_pct": 15.5,
    })

    # Connection lifecycle
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    return client


@pytest.fixture
def mock_rabbitmq_connection():
    """Create mocked RabbitMQ connection."""
    connection = MagicMock()
    channel = MagicMock()

    connection.channel = MagicMock(return_value=channel)
    channel.basic_publish = MagicMock()
    channel.queue_declare = MagicMock()
    channel.exchange_declare = MagicMock()

    return connection


@pytest.fixture
def sample_optimization_state() -> Dict[str, Any]:
    """Sample optimization state for testing."""
    return {
        "optimization_id": "opt-123",
        "current_iteration": 3,
        "max_iterations": 10,
        "best_strategy_id": "strategy-456",
        "best_sharpe": 1.9,
        "strategies_tested": [
            {"id": "strategy-123", "sharpe": 1.5},
            {"id": "strategy-456", "sharpe": 1.9},
            {"id": "strategy-789", "sharpe": 1.2},
        ],
        "status": "running",
        "started_at": "2024-12-14T08:00:00Z",
    }


@pytest.fixture
def sample_engineer_output() -> Dict[str, Any]:
    """Sample Engineer agent output."""
    return {
        "generated_code": "class NewStrategy(IStrategy): pass",
        "validation_passed": True,
        "validation_errors": [],
        "modifications_made": ["Added RSI indicator", "Adjusted entry threshold"],
        "strategy_name": "TestStrategy_v2",
        "confidence_score": 0.85,
    }


@pytest.fixture
def sample_analyst_output() -> Dict[str, Any]:
    """Sample Analyst agent output."""
    return {
        "decision": "approve",
        "reasoning": "Strategy meets all criteria with Sharpe ratio 1.8 and low drawdown",
        "metrics_analysis": {
            "sharpe_ratio": {"value": 1.8, "threshold": 1.5, "passed": True},
            "max_drawdown": {"value": 8.5, "threshold": 15.0, "passed": True},
            "win_rate": {"value": 0.6, "threshold": 0.5, "passed": True},
        },
        "suggestions": [],
        "risk_assessment": "low",
    }


@pytest.fixture
def sample_analyst_modify_output() -> Dict[str, Any]:
    """Sample Analyst output requesting modification."""
    return {
        "decision": "modify",
        "reasoning": "Sharpe ratio below threshold and high drawdown",
        "metrics_analysis": {
            "sharpe_ratio": {"value": 0.3, "threshold": 1.5, "passed": False},
            "max_drawdown": {"value": 25.0, "threshold": 15.0, "passed": False},
        },
        "suggestions": [
            "Tighten stop loss to reduce drawdown",
            "Add trend filter to improve entry quality",
            "Consider reducing position size during volatile periods",
        ],
        "risk_assessment": "high",
    }


@pytest.fixture
async def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_batch_strategies() -> List[Dict[str, Any]]:
    """Sample batch of strategies for testing."""
    return [
        {
            "id": f"strategy-{i}",
            "name": f"TestStrategy_v{i}",
            "code": f"class TestStrategy_v{i}(IStrategy): pass",
        }
        for i in range(1, 6)
    ]


@pytest.fixture
def sample_lineage_tree() -> Dict[str, Any]:
    """Sample strategy lineage tree."""
    return {
        "root": {
            "id": "strategy-001",
            "name": "BaseStrategy",
            "generation": 1,
            "children": [
                {
                    "id": "strategy-002",
                    "name": "BaseStrategy_mod1",
                    "generation": 2,
                    "children": [
                        {
                            "id": "strategy-003",
                            "name": "BaseStrategy_mod1_refined",
                            "generation": 3,
                            "children": [],
                        }
                    ],
                },
                {
                    "id": "strategy-004",
                    "name": "BaseStrategy_mod2",
                    "generation": 2,
                    "children": [],
                },
            ],
        }
    }
