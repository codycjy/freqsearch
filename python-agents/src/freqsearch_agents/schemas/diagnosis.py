"""Diagnosis-related Pydantic schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DiagnosisStatus(str, Enum):
    """Possible outcomes of strategy diagnosis."""

    READY_FOR_LIVE = "READY_FOR_LIVE"  # Strategy approved for live trading
    NEEDS_MODIFICATION = "NEEDS_MODIFICATION"  # Strategy needs changes
    ARCHIVE = "ARCHIVE"  # Strategy should be discarded


class SuggestionType(str, Enum):
    """Types of modification suggestions."""

    # Entry/Exit logic
    ADD_FILTER = "ADD_FILTER"  # Add a condition filter
    REMOVE_FILTER = "REMOVE_FILTER"  # Remove overly restrictive condition
    MODIFY_CONDITION = "MODIFY_CONDITION"  # Change existing condition

    # Risk management
    ADD_STOPLOSS = "ADD_STOPLOSS"  # Add or modify stoploss
    ADD_TRAILING_STOP = "ADD_TRAILING_STOP"  # Add trailing stoploss
    MODIFY_ROI = "MODIFY_ROI"  # Adjust ROI table

    # Parameters
    NARROW_PARAMETER_RANGE = "NARROW_PARAMETER_RANGE"  # Reduce search space
    WIDEN_PARAMETER_RANGE = "WIDEN_PARAMETER_RANGE"  # Expand search space
    CHANGE_DEFAULT = "CHANGE_DEFAULT"  # Change parameter default

    # Indicators
    ADD_INDICATOR = "ADD_INDICATOR"  # Add new indicator
    REMOVE_INDICATOR = "REMOVE_INDICATOR"  # Remove unhelpful indicator
    CHANGE_INDICATOR_PARAMS = "CHANGE_INDICATOR_PARAMS"  # Modify indicator settings

    # Timeframe/Pairs
    CHANGE_TIMEFRAME = "CHANGE_TIMEFRAME"  # Try different timeframe
    FILTER_PAIRS = "FILTER_PAIRS"  # Restrict to certain pairs

    # Structural
    ADD_INFORMATIVE_PAIRS = "ADD_INFORMATIVE_PAIRS"  # Add multi-timeframe analysis
    SIMPLIFY_LOGIC = "SIMPLIFY_LOGIC"  # Reduce complexity


class MetricsSummary(BaseModel):
    """Summary of backtest metrics."""

    # Basic stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    # Profitability
    profit_total: float
    profit_pct: float
    profit_factor: float | None = None

    # Risk metrics
    max_drawdown: float
    max_drawdown_pct: float
    max_drawdown_duration_days: float | None = None

    # Advanced metrics
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    calmar_ratio: float | None = None
    expectancy: float | None = None

    # Trade details
    avg_profit_per_trade: float | None = None
    avg_trade_duration_minutes: float | None = None
    best_trade_pct: float | None = None
    worst_trade_pct: float | None = None


class DiagnosisReport(BaseModel):
    """Complete diagnosis report from Analyst Agent.

    This is sent to Engineer Agent when modification is needed.
    """

    # References
    job_id: str
    strategy_id: str
    strategy_name: str

    # Decision
    status: DiagnosisStatus
    confidence: float = Field(ge=0.0, le=1.0)

    # Analysis
    issues: list[str] = Field(default_factory=list)
    root_causes: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)

    # Modification suggestions (only when status == NEEDS_MODIFICATION)
    suggestion_type: SuggestionType | None = None
    suggestion_description: str | None = None
    suggested_code_changes: str | None = None  # Pseudo-code or description
    target_metrics: list[str] = Field(default_factory=list)

    # Metrics summary
    metrics_summary: MetricsSummary | None = None

    # Market context
    market_regime: str | None = None  # "trending_up", "trending_down", "ranging"
    performance_by_regime: dict[str, float] | None = None

    # Tracking
    created_at: datetime = Field(default_factory=datetime.utcnow)
    analyst_model: str = "gpt-4-turbo-preview"
