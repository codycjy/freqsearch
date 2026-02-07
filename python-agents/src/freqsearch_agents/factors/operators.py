"""Factor operators for WorldQuant-style alpha expressions.

Implements 18 core operators used in quantitative factor construction:
- Time series: delay, delta, ts_sum, ts_mean, ts_std, ts_rank, ts_min, ts_max, etc.
- Cross-sectional: rank, scale
- Statistical: correlation, covariance
- Arithmetic: log, sign, abs_

All operators work with pandas Series/DataFrame and support vectorized operations.
"""

from typing import Callable

import numpy as np
import pandas as pd
from scipy.stats import rankdata


# ============================================================================
# Time Series Operators
# ============================================================================


def delay(df: pd.Series, period: int = 1) -> pd.Series:
    """Shift time series by a specified period.

    Args:
        df: Input time series
        period: Number of periods to shift (default: 1)

    Returns:
        Time series shifted by period positions

    Example:
        delay(close, 1)  # Previous day's close price
        delay(volume, 5)  # Volume from 5 days ago
    """
    return df.shift(period)


def delta(df: pd.Series, period: int = 1) -> pd.Series:
    """Calculate difference between current and past values.

    Args:
        df: Input time series
        period: Number of periods to look back (default: 1)

    Returns:
        Difference between x[t] and x[t-period]

    Example:
        delta(close, 1)  # Daily price change
        delta(volume, 2)  # 2-day volume change
    """
    return df.diff(period)


def ts_sum(df: pd.Series, window: int = 10) -> pd.Series:
    """Rolling sum over a time window.

    Args:
        df: Input time series
        window: Rolling window size (default: 10)

    Returns:
        Rolling sum of values in window

    Example:
        ts_sum(volume, 5)  # 5-day cumulative volume
    """
    return df.rolling(window, min_periods=1).sum()


def ts_mean(df: pd.Series, window: int = 10) -> pd.Series:
    """Rolling mean (simple moving average).

    Args:
        df: Input time series
        window: Rolling window size (default: 10)

    Returns:
        Rolling mean of values in window

    Example:
        ts_mean(close, 20)  # 20-day SMA
    """
    return df.rolling(window, min_periods=1).mean()


def ts_std(df: pd.Series, window: int = 10) -> pd.Series:
    """Rolling standard deviation.

    Args:
        df: Input time series
        window: Rolling window size (default: 10)

    Returns:
        Rolling standard deviation of values in window

    Example:
        ts_std(returns, 20)  # 20-day volatility
    """
    return df.rolling(window, min_periods=1).std()


def ts_rank(df: pd.Series, window: int = 10) -> pd.Series:
    """Rolling rank (percentile) within window.

    Args:
        df: Input time series
        window: Rolling window size (default: 10)

    Returns:
        Percentile rank of current value within rolling window (0 to 1)

    Example:
        ts_rank(close, 10)  # Where does today's close rank in last 10 days?
    """
    return df.rolling(window, min_periods=1).apply(
        lambda x: rankdata(x)[-1] / len(x) if len(x) > 0 else np.nan,
        raw=True,
    )


def ts_min(df: pd.Series, window: int = 10) -> pd.Series:
    """Rolling minimum value.

    Args:
        df: Input time series
        window: Rolling window size (default: 10)

    Returns:
        Rolling minimum value in window

    Example:
        ts_min(low, 20)  # Lowest low in 20 days
    """
    return df.rolling(window, min_periods=1).min()


def ts_max(df: pd.Series, window: int = 10) -> pd.Series:
    """Rolling maximum value.

    Args:
        df: Input time series
        window: Rolling window size (default: 10)

    Returns:
        Rolling maximum value in window

    Example:
        ts_max(high, 20)  # Highest high in 20 days
    """
    return df.rolling(window, min_periods=1).max()


def ts_argmax(df: pd.Series, window: int = 10) -> pd.Series:
    """Index of maximum value within rolling window.

    Args:
        df: Input time series
        window: Rolling window size (default: 10)

    Returns:
        Number of periods since the maximum value (1 to window)

    Example:
        ts_argmax(volume, 10)  # Days since highest volume in 10 days
    """
    return df.rolling(window, min_periods=1).apply(
        lambda x: np.argmax(x) + 1 if len(x) > 0 else np.nan,
        raw=True,
    )


def ts_argmin(df: pd.Series, window: int = 10) -> pd.Series:
    """Index of minimum value within rolling window.

    Args:
        df: Input time series
        window: Rolling window size (default: 10)

    Returns:
        Number of periods since the minimum value (1 to window)

    Example:
        ts_argmin(close, 20)  # Days since lowest close in 20 days
    """
    return df.rolling(window, min_periods=1).apply(
        lambda x: np.argmin(x) + 1 if len(x) > 0 else np.nan,
        raw=True,
    )


def product(df: pd.Series, window: int = 10) -> pd.Series:
    """Rolling product of values.

    Args:
        df: Input time series
        window: Rolling window size (default: 10)

    Returns:
        Rolling product of values in window

    Example:
        product(1 + returns, 5)  # 5-day cumulative return
    """
    return df.rolling(window, min_periods=1).apply(
        lambda x: np.prod(x) if len(x) > 0 else np.nan,
        raw=True,
    )


def decay_linear(df: pd.Series, period: int = 10) -> pd.Series:
    """Linear decay weighted average.

    Applies linearly decreasing weights to recent values,
    with most recent value having highest weight.

    Args:
        df: Input time series
        period: Window size for decay (default: 10)

    Returns:
        Linearly weighted moving average

    Example:
        decay_linear(volume, 10)  # Volume with linear decay
    """
    weights = np.arange(1, period + 1)
    weights_sum = weights.sum()

    return df.rolling(period, min_periods=1).apply(
        lambda x: (
            np.dot(x, weights[-len(x) :]) / weights[-len(x) :].sum()
            if len(x) > 0
            else np.nan
        ),
        raw=True,
    )


# ============================================================================
# Cross-Sectional Operators
# ============================================================================


def rank(df: pd.Series) -> pd.Series:
    """Percentile rank transformation.

    Transforms values to their percentile rank (0 to 1).
    For single-asset strategies, this normalizes the time series.

    Args:
        df: Input time series

    Returns:
        Percentile rank of each value (0 to 1)

    Example:
        rank(volume)  # Normalized volume rank
    """
    return df.rank(pct=True)


def scale(df: pd.Series, k: float = 1.0) -> pd.Series:
    """Scale series to sum to k.

    Rescales values so their absolute sum equals k.

    Args:
        df: Input time series
        k: Target sum of absolute values (default: 1.0)

    Returns:
        Scaled series

    Example:
        scale(returns, 1)  # Normalize returns to sum to 1
    """
    abs_sum = np.abs(df).sum()
    if abs_sum == 0 or pd.isna(abs_sum):
        return df * 0
    return df * k / abs_sum


# ============================================================================
# Statistical Operators
# ============================================================================


def correlation(x: pd.Series, y: pd.Series, window: int = 10) -> pd.Series:
    """Rolling correlation between two time series.

    Args:
        x: First time series
        y: Second time series
        window: Rolling window size (default: 10)

    Returns:
        Rolling correlation coefficient (-1 to 1)

    Example:
        correlation(close, volume, 20)  # Price-volume correlation
    """
    return x.rolling(window, min_periods=1).corr(y)


def covariance(x: pd.Series, y: pd.Series, window: int = 10) -> pd.Series:
    """Rolling covariance between two time series.

    Args:
        x: First time series
        y: Second time series
        window: Rolling window size (default: 10)

    Returns:
        Rolling covariance

    Example:
        covariance(returns, market_returns, 60)
    """
    return x.rolling(window, min_periods=1).cov(y)


# ============================================================================
# Arithmetic Operators
# ============================================================================


def log(df: pd.Series) -> pd.Series:
    """Natural logarithm.

    Args:
        df: Input time series (positive values)

    Returns:
        Natural log of values

    Example:
        log(close)  # Log price for log returns
    """
    return np.log(df)


def sign(df: pd.Series) -> pd.Series:
    """Sign of values (-1, 0, or 1).

    Args:
        df: Input time series

    Returns:
        Sign of each value

    Example:
        sign(returns)  # Direction of returns
    """
    return np.sign(df)


def abs_(df: pd.Series) -> pd.Series:
    """Absolute value.

    Args:
        df: Input time series

    Returns:
        Absolute value of each element

    Example:
        abs_(returns)  # Magnitude of returns
    """
    return np.abs(df)


# ============================================================================
# Operator Registry
# ============================================================================

OPERATORS: dict[str, Callable] = {
    # Time series operators
    "delay": delay,
    "delta": delta,
    "ts_sum": ts_sum,
    "sum": ts_sum,  # Alias
    "ts_mean": ts_mean,
    "mean": ts_mean,  # Alias
    "sma": ts_mean,  # Alias for Simple Moving Average
    "ts_std": ts_std,
    "stddev": ts_std,  # Alias
    "ts_rank": ts_rank,
    "ts_min": ts_min,
    "ts_max": ts_max,
    "ts_argmax": ts_argmax,
    "ts_argmin": ts_argmin,
    "product": product,
    "decay_linear": decay_linear,
    # Cross-sectional operators
    "rank": rank,
    "scale": scale,
    # Statistical operators
    "correlation": correlation,
    "corr": correlation,  # Alias
    "covariance": covariance,
    "cov": covariance,  # Alias
    # Arithmetic operators
    "log": log,
    "sign": sign,
    "abs": abs_,
}


# Export all operators for direct import
__all__ = [
    # Time series
    "delay",
    "delta",
    "ts_sum",
    "ts_mean",
    "ts_std",
    "ts_rank",
    "ts_min",
    "ts_max",
    "ts_argmax",
    "ts_argmin",
    "product",
    "decay_linear",
    # Cross-sectional
    "rank",
    "scale",
    # Statistical
    "correlation",
    "covariance",
    # Arithmetic
    "log",
    "sign",
    "abs_",
    # Registry
    "OPERATORS",
]
