"""Tests for financial metrics calculations."""

import pytest
import math

from freqsearch_agents.tools.analysis.metrics import (
    compute_sharpe_ratio,
    compute_sortino_ratio,
    compute_calmar_ratio,
    compute_expectancy,
    compute_profit_factor,
    compute_max_drawdown,
)


class TestSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_positive_sharpe(self):
        """Test positive Sharpe ratio."""
        # Consistent positive returns
        returns = [0.01, 0.02, 0.01, 0.015, 0.02]
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe is not None
        assert sharpe > 0

    def test_negative_sharpe(self):
        """Test negative Sharpe ratio."""
        # Consistent negative returns
        returns = [-0.01, -0.02, -0.01, -0.015, -0.02]
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe is not None
        assert sharpe < 0

    def test_insufficient_data(self):
        """Test with insufficient data."""
        returns = [0.01]
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe is None

    def test_zero_volatility(self):
        """Test with zero volatility (constant returns)."""
        returns = [0.01, 0.01, 0.01, 0.01]
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe is None


class TestSortinoRatio:
    """Tests for Sortino ratio calculation."""

    def test_positive_sortino(self):
        """Test positive Sortino ratio."""
        returns = [0.01, 0.02, -0.005, 0.015, 0.02]
        sortino = compute_sortino_ratio(returns)
        assert sortino is not None
        assert sortino > 0

    def test_no_downside(self):
        """Test with no downside returns."""
        returns = [0.01, 0.02, 0.01, 0.015]
        sortino = compute_sortino_ratio(returns)
        # Should be None since there's no downside deviation
        assert sortino is None


class TestCalmarRatio:
    """Tests for Calmar ratio calculation."""

    def test_positive_calmar(self):
        """Test positive Calmar ratio."""
        calmar = compute_calmar_ratio(total_return=20.0, max_drawdown=10.0, periods=1)
        assert calmar is not None
        assert calmar == pytest.approx(2.0, rel=0.01)

    def test_zero_drawdown(self):
        """Test with zero drawdown."""
        calmar = compute_calmar_ratio(total_return=20.0, max_drawdown=0.0)
        assert calmar is None

    def test_multi_year(self):
        """Test with multi-year period."""
        # 50% return over 2 years should annualize to ~22.5%
        calmar = compute_calmar_ratio(total_return=50.0, max_drawdown=10.0, periods=2)
        assert calmar is not None
        assert calmar > 2.0


class TestExpectancy:
    """Tests for expectancy calculation."""

    def test_positive_expectancy(self):
        """Test positive expectancy."""
        expectancy = compute_expectancy(
            win_rate=0.6,
            avg_win=100,
            avg_loss=50,
        )
        # (0.6 * 100) - (0.4 * 50) = 60 - 20 = 40
        assert expectancy == pytest.approx(40.0)

    def test_negative_expectancy(self):
        """Test negative expectancy."""
        expectancy = compute_expectancy(
            win_rate=0.3,
            avg_win=50,
            avg_loss=100,
        )
        # (0.3 * 50) - (0.7 * 100) = 15 - 70 = -55
        assert expectancy == pytest.approx(-55.0)

    def test_breakeven(self):
        """Test breakeven expectancy."""
        expectancy = compute_expectancy(
            win_rate=0.5,
            avg_win=100,
            avg_loss=100,
        )
        assert expectancy == pytest.approx(0.0)

    def test_invalid_win_rate(self):
        """Test with invalid win rate."""
        expectancy = compute_expectancy(win_rate=1.5, avg_win=100, avg_loss=50)
        assert expectancy is None


class TestProfitFactor:
    """Tests for profit factor calculation."""

    def test_positive_profit_factor(self):
        """Test positive profit factor."""
        pf = compute_profit_factor(gross_profit=1000, gross_loss=500)
        assert pf == pytest.approx(2.0)

    def test_zero_loss(self):
        """Test with zero loss."""
        pf = compute_profit_factor(gross_profit=1000, gross_loss=0)
        assert pf is None


class TestMaxDrawdown:
    """Tests for max drawdown calculation."""

    def test_simple_drawdown(self):
        """Test simple drawdown calculation."""
        equity = [100, 110, 105, 115, 100, 120]
        dd_abs, dd_pct = compute_max_drawdown(equity)

        # Max drawdown is from 115 to 100 = 15 (13.04%)
        assert dd_abs == pytest.approx(15.0)
        assert dd_pct == pytest.approx(13.04, rel=0.01)

    def test_no_drawdown(self):
        """Test with no drawdown (monotonically increasing)."""
        equity = [100, 105, 110, 115, 120]
        dd_abs, dd_pct = compute_max_drawdown(equity)
        assert dd_abs == 0.0
        assert dd_pct == 0.0

    def test_insufficient_data(self):
        """Test with insufficient data."""
        equity = [100]
        dd_abs, dd_pct = compute_max_drawdown(equity)
        assert dd_abs == 0.0
        assert dd_pct == 0.0
