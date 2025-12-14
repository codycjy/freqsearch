"""Pydantic schemas for data structures."""

from .strategy import RawStrategy, ExecutableStrategy, HyperoptConfig, StrategyParameter
from .diagnosis import DiagnosisReport, DiagnosisStatus, SuggestionType
from .events import (
    StrategyDiscoveredEvent,
    StrategyReadyEvent,
    BacktestCompletedEvent,
    StrategyEvolveEvent,
)

__all__ = [
    # Strategy
    "RawStrategy",
    "ExecutableStrategy",
    "HyperoptConfig",
    "StrategyParameter",
    # Diagnosis
    "DiagnosisReport",
    "DiagnosisStatus",
    "SuggestionType",
    # Events
    "StrategyDiscoveredEvent",
    "StrategyReadyEvent",
    "BacktestCompletedEvent",
    "StrategyEvolveEvent",
]
