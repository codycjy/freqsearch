"""Financial metrics calculations."""

import math
from typing import Sequence


def compute_sharpe_ratio(
    returns: Sequence[float],
    risk_free_rate: float = 0.0,
    annualization_factor: float = 252,
) -> float | None:
    """Compute Sharpe ratio.

    Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns

    Args:
        returns: Sequence of periodic returns
        risk_free_rate: Risk-free rate (default 0)
        annualization_factor: Factor to annualize (252 for daily, 52 for weekly)

    Returns:
        Sharpe ratio or None if insufficient data
    """
    if len(returns) < 2:
        return None

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
    std_dev = math.sqrt(variance)

    if std_dev == 0:
        return None

    sharpe = (mean_return - risk_free_rate) / std_dev
    # Annualize
    sharpe *= math.sqrt(annualization_factor)

    return sharpe


def compute_sortino_ratio(
    returns: Sequence[float],
    target_return: float = 0.0,
    annualization_factor: float = 252,
) -> float | None:
    """Compute Sortino ratio.

    Similar to Sharpe but only penalizes downside volatility.

    Args:
        returns: Sequence of periodic returns
        target_return: Target/minimum acceptable return
        annualization_factor: Factor to annualize

    Returns:
        Sortino ratio or None if insufficient data
    """
    if len(returns) < 2:
        return None

    mean_return = sum(returns) / len(returns)

    # Calculate downside deviation
    downside_returns = [min(0, r - target_return) ** 2 for r in returns]
    downside_deviation = math.sqrt(sum(downside_returns) / len(returns))

    if downside_deviation == 0:
        return None

    sortino = (mean_return - target_return) / downside_deviation
    sortino *= math.sqrt(annualization_factor)

    return sortino


def compute_calmar_ratio(
    total_return: float,
    max_drawdown: float,
    periods: int = 1,
) -> float | None:
    """Compute Calmar ratio.

    Calmar = Annualized Return / Max Drawdown

    Args:
        total_return: Total return as percentage
        max_drawdown: Maximum drawdown as positive percentage
        periods: Number of years in backtest

    Returns:
        Calmar ratio or None if invalid data
    """
    if max_drawdown <= 0 or periods <= 0:
        return None

    # Annualize return
    annualized_return = (1 + total_return / 100) ** (1 / periods) - 1
    annualized_return *= 100

    calmar = annualized_return / max_drawdown

    return calmar


def compute_expectancy(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float | None:
    """Compute expectancy (expected value per trade).

    Expectancy = (Win% * Avg Win) - (Loss% * Avg Loss)

    Args:
        win_rate: Win rate as decimal (0-1)
        avg_win: Average winning trade profit
        avg_loss: Average losing trade loss (as positive number)

    Returns:
        Expectancy per trade
    """
    if not (0 <= win_rate <= 1):
        return None

    loss_rate = 1 - win_rate
    expectancy = (win_rate * avg_win) - (loss_rate * abs(avg_loss))

    return expectancy


def compute_profit_factor(
    gross_profit: float,
    gross_loss: float,
) -> float | None:
    """Compute profit factor.

    Profit Factor = Gross Profit / Gross Loss

    Args:
        gross_profit: Total profit from winning trades
        gross_loss: Total loss from losing trades (as positive number)

    Returns:
        Profit factor or None if no losses
    """
    if gross_loss <= 0:
        return None

    return gross_profit / abs(gross_loss)


def compute_max_drawdown(equity_curve: Sequence[float]) -> tuple[float, float]:
    """Compute maximum drawdown from equity curve.

    Args:
        equity_curve: Sequence of equity values

    Returns:
        Tuple of (max_drawdown_absolute, max_drawdown_percentage)
    """
    if len(equity_curve) < 2:
        return 0.0, 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    max_dd_pct = 0.0

    for value in equity_curve:
        if value > peak:
            peak = value
        dd = peak - value
        dd_pct = dd / peak if peak > 0 else 0

        if dd > max_dd:
            max_dd = dd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

    return max_dd, max_dd_pct * 100
