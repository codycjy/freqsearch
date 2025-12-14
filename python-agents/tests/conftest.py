"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_strategy_code() -> str:
    """Sample valid Freqtrade strategy code."""
    return '''
from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta
from pandas import DataFrame

class SampleStrategy(IStrategy):
    """Sample strategy for testing."""

    timeframe = '5m'
    stoploss = -0.10

    rsi_period = IntParameter(7, 21, default=14, space='buy')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['rsi'] < 30),
            'enter_long'
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['rsi'] > 70),
            'exit_long'
        ] = 1
        return dataframe
'''


@pytest.fixture
def sample_invalid_strategy_code() -> str:
    """Sample invalid strategy code (missing methods)."""
    return '''
from freqtrade.strategy import IStrategy

class InvalidStrategy(IStrategy):
    timeframe = '5m'

    def populate_indicators(self, dataframe, metadata):
        return dataframe
'''


@pytest.fixture
def sample_backtest_result() -> dict:
    """Sample backtest result data."""
    return {
        "job_id": "test-job-123",
        "strategy_id": "test-strategy-456",
        "strategy_name": "TestStrategy",
        "total_trades": 100,
        "winning_trades": 55,
        "losing_trades": 45,
        "profit_total": 150.0,
        "profit_pct": 15.0,
        "max_drawdown": 500.0,
        "max_drawdown_pct": 10.0,
        "sharpe_ratio": 1.5,
        "profit_factor": 1.8,
        "avg_profit_winning": 5.0,
        "avg_profit_losing": -3.0,
        "avg_trade_duration_minutes": 240,
        "best_trade_pct": 15.0,
        "worst_trade_pct": -8.0,
    }
