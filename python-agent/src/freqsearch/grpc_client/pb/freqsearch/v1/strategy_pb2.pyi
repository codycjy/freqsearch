import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from freqsearch.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Strategy(_message.Message):
    __slots__ = ("id", "name", "code", "code_hash", "parent_id", "generation", "description", "metadata", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    CODE_HASH_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    code: str
    code_hash: str
    parent_id: str
    generation: int
    description: str
    metadata: StrategyMetadata
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., code: _Optional[str] = ..., code_hash: _Optional[str] = ..., parent_id: _Optional[str] = ..., generation: _Optional[int] = ..., description: _Optional[str] = ..., metadata: _Optional[_Union[StrategyMetadata, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class StrategyMetadata(_message.Message):
    __slots__ = ("timeframe", "indicators", "stoploss", "trailing_stop", "trailing_stop_positive", "trailing_stop_positive_offset", "minimal_roi", "startup_candle_count")
    class MinimalRoiEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: float
        def __init__(self, key: _Optional[str] = ..., value: _Optional[float] = ...) -> None: ...
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    INDICATORS_FIELD_NUMBER: _ClassVar[int]
    STOPLOSS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_POSITIVE_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_POSITIVE_OFFSET_FIELD_NUMBER: _ClassVar[int]
    MINIMAL_ROI_FIELD_NUMBER: _ClassVar[int]
    STARTUP_CANDLE_COUNT_FIELD_NUMBER: _ClassVar[int]
    timeframe: str
    indicators: _containers.RepeatedScalarFieldContainer[str]
    stoploss: float
    trailing_stop: bool
    trailing_stop_positive: float
    trailing_stop_positive_offset: float
    minimal_roi: _containers.ScalarMap[str, float]
    startup_candle_count: int
    def __init__(self, timeframe: _Optional[str] = ..., indicators: _Optional[_Iterable[str]] = ..., stoploss: _Optional[float] = ..., trailing_stop: bool = ..., trailing_stop_positive: _Optional[float] = ..., trailing_stop_positive_offset: _Optional[float] = ..., minimal_roi: _Optional[_Mapping[str, float]] = ..., startup_candle_count: _Optional[int] = ...) -> None: ...

class StrategyWithMetrics(_message.Message):
    __slots__ = ("strategy", "best_result", "backtest_count")
    STRATEGY_FIELD_NUMBER: _ClassVar[int]
    BEST_RESULT_FIELD_NUMBER: _ClassVar[int]
    BACKTEST_COUNT_FIELD_NUMBER: _ClassVar[int]
    strategy: Strategy
    best_result: StrategyPerformanceMetrics
    backtest_count: int
    def __init__(self, strategy: _Optional[_Union[Strategy, _Mapping]] = ..., best_result: _Optional[_Union[StrategyPerformanceMetrics, _Mapping]] = ..., backtest_count: _Optional[int] = ...) -> None: ...

class StrategyPerformanceMetrics(_message.Message):
    __slots__ = ("sharpe_ratio", "sortino_ratio", "profit_pct", "max_drawdown_pct", "total_trades", "win_rate", "profit_factor")
    SHARPE_RATIO_FIELD_NUMBER: _ClassVar[int]
    SORTINO_RATIO_FIELD_NUMBER: _ClassVar[int]
    PROFIT_PCT_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_PCT_FIELD_NUMBER: _ClassVar[int]
    TOTAL_TRADES_FIELD_NUMBER: _ClassVar[int]
    WIN_RATE_FIELD_NUMBER: _ClassVar[int]
    PROFIT_FACTOR_FIELD_NUMBER: _ClassVar[int]
    sharpe_ratio: float
    sortino_ratio: float
    profit_pct: float
    max_drawdown_pct: float
    total_trades: int
    win_rate: float
    profit_factor: float
    def __init__(self, sharpe_ratio: _Optional[float] = ..., sortino_ratio: _Optional[float] = ..., profit_pct: _Optional[float] = ..., max_drawdown_pct: _Optional[float] = ..., total_trades: _Optional[int] = ..., win_rate: _Optional[float] = ..., profit_factor: _Optional[float] = ...) -> None: ...

class CreateStrategyRequest(_message.Message):
    __slots__ = ("name", "code", "parent_id", "description")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    name: str
    code: str
    parent_id: str
    description: str
    def __init__(self, name: _Optional[str] = ..., code: _Optional[str] = ..., parent_id: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class CreateStrategyResponse(_message.Message):
    __slots__ = ("strategy",)
    STRATEGY_FIELD_NUMBER: _ClassVar[int]
    strategy: Strategy
    def __init__(self, strategy: _Optional[_Union[Strategy, _Mapping]] = ...) -> None: ...

class GetStrategyRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetStrategyResponse(_message.Message):
    __slots__ = ("strategy",)
    STRATEGY_FIELD_NUMBER: _ClassVar[int]
    strategy: Strategy
    def __init__(self, strategy: _Optional[_Union[Strategy, _Mapping]] = ...) -> None: ...

class SearchStrategiesRequest(_message.Message):
    __slots__ = ("name_pattern", "min_sharpe", "min_profit_pct", "min_trades", "max_drawdown_pct", "pagination", "order_by", "ascending")
    NAME_PATTERN_FIELD_NUMBER: _ClassVar[int]
    MIN_SHARPE_FIELD_NUMBER: _ClassVar[int]
    MIN_PROFIT_PCT_FIELD_NUMBER: _ClassVar[int]
    MIN_TRADES_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_PCT_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    ORDER_BY_FIELD_NUMBER: _ClassVar[int]
    ASCENDING_FIELD_NUMBER: _ClassVar[int]
    name_pattern: str
    min_sharpe: float
    min_profit_pct: float
    min_trades: int
    max_drawdown_pct: float
    pagination: _common_pb2.PaginationRequest
    order_by: str
    ascending: bool
    def __init__(self, name_pattern: _Optional[str] = ..., min_sharpe: _Optional[float] = ..., min_profit_pct: _Optional[float] = ..., min_trades: _Optional[int] = ..., max_drawdown_pct: _Optional[float] = ..., pagination: _Optional[_Union[_common_pb2.PaginationRequest, _Mapping]] = ..., order_by: _Optional[str] = ..., ascending: bool = ...) -> None: ...

class SearchStrategiesResponse(_message.Message):
    __slots__ = ("strategies", "pagination")
    STRATEGIES_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    strategies: _containers.RepeatedCompositeFieldContainer[StrategyWithMetrics]
    pagination: _common_pb2.PaginationResponse
    def __init__(self, strategies: _Optional[_Iterable[_Union[StrategyWithMetrics, _Mapping]]] = ..., pagination: _Optional[_Union[_common_pb2.PaginationResponse, _Mapping]] = ...) -> None: ...

class GetStrategyLineageRequest(_message.Message):
    __slots__ = ("strategy_id", "depth")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    DEPTH_FIELD_NUMBER: _ClassVar[int]
    strategy_id: str
    depth: int
    def __init__(self, strategy_id: _Optional[str] = ..., depth: _Optional[int] = ...) -> None: ...

class GetStrategyLineageResponse(_message.Message):
    __slots__ = ("lineage",)
    LINEAGE_FIELD_NUMBER: _ClassVar[int]
    lineage: _containers.RepeatedCompositeFieldContainer[StrategyLineageNode]
    def __init__(self, lineage: _Optional[_Iterable[_Union[StrategyLineageNode, _Mapping]]] = ...) -> None: ...

class StrategyLineageNode(_message.Message):
    __slots__ = ("strategy", "metrics", "children")
    STRATEGY_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    CHILDREN_FIELD_NUMBER: _ClassVar[int]
    strategy: Strategy
    metrics: StrategyPerformanceMetrics
    children: _containers.RepeatedCompositeFieldContainer[StrategyLineageNode]
    def __init__(self, strategy: _Optional[_Union[Strategy, _Mapping]] = ..., metrics: _Optional[_Union[StrategyPerformanceMetrics, _Mapping]] = ..., children: _Optional[_Iterable[_Union[StrategyLineageNode, _Mapping]]] = ...) -> None: ...

class DeleteStrategyRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class DeleteStrategyResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...
