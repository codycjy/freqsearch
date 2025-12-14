import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from freqsearch.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BacktestConfig(_message.Message):
    __slots__ = ("exchange", "pairs", "timeframe", "timerange_start", "timerange_end", "dry_run_wallet", "max_open_trades", "stake_amount")
    EXCHANGE_FIELD_NUMBER: _ClassVar[int]
    PAIRS_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    TIMERANGE_START_FIELD_NUMBER: _ClassVar[int]
    TIMERANGE_END_FIELD_NUMBER: _ClassVar[int]
    DRY_RUN_WALLET_FIELD_NUMBER: _ClassVar[int]
    MAX_OPEN_TRADES_FIELD_NUMBER: _ClassVar[int]
    STAKE_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    exchange: str
    pairs: _containers.RepeatedScalarFieldContainer[str]
    timeframe: str
    timerange_start: str
    timerange_end: str
    dry_run_wallet: float
    max_open_trades: int
    stake_amount: str
    def __init__(self, exchange: _Optional[str] = ..., pairs: _Optional[_Iterable[str]] = ..., timeframe: _Optional[str] = ..., timerange_start: _Optional[str] = ..., timerange_end: _Optional[str] = ..., dry_run_wallet: _Optional[float] = ..., max_open_trades: _Optional[int] = ..., stake_amount: _Optional[str] = ...) -> None: ...

class BacktestJob(_message.Message):
    __slots__ = ("id", "strategy_id", "optimization_run_id", "config", "status", "container_id", "error_message", "priority", "created_at", "started_at", "completed_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    OPTIMIZATION_RUN_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    strategy_id: str
    optimization_run_id: str
    config: BacktestConfig
    status: _common_pb2.JobStatus
    container_id: str
    error_message: str
    priority: int
    created_at: _timestamp_pb2.Timestamp
    started_at: _timestamp_pb2.Timestamp
    completed_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., strategy_id: _Optional[str] = ..., optimization_run_id: _Optional[str] = ..., config: _Optional[_Union[BacktestConfig, _Mapping]] = ..., status: _Optional[_Union[_common_pb2.JobStatus, str]] = ..., container_id: _Optional[str] = ..., error_message: _Optional[str] = ..., priority: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., started_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., completed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class BacktestResult(_message.Message):
    __slots__ = ("id", "job_id", "strategy_id", "total_trades", "winning_trades", "losing_trades", "win_rate", "profit_total", "profit_pct", "profit_factor", "max_drawdown", "max_drawdown_pct", "sharpe_ratio", "sortino_ratio", "calmar_ratio", "avg_trade_duration_minutes", "avg_profit_per_trade", "best_trade_pct", "worst_trade_pct", "pair_results", "raw_log", "trades_json", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    TOTAL_TRADES_FIELD_NUMBER: _ClassVar[int]
    WINNING_TRADES_FIELD_NUMBER: _ClassVar[int]
    LOSING_TRADES_FIELD_NUMBER: _ClassVar[int]
    WIN_RATE_FIELD_NUMBER: _ClassVar[int]
    PROFIT_TOTAL_FIELD_NUMBER: _ClassVar[int]
    PROFIT_PCT_FIELD_NUMBER: _ClassVar[int]
    PROFIT_FACTOR_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_PCT_FIELD_NUMBER: _ClassVar[int]
    SHARPE_RATIO_FIELD_NUMBER: _ClassVar[int]
    SORTINO_RATIO_FIELD_NUMBER: _ClassVar[int]
    CALMAR_RATIO_FIELD_NUMBER: _ClassVar[int]
    AVG_TRADE_DURATION_MINUTES_FIELD_NUMBER: _ClassVar[int]
    AVG_PROFIT_PER_TRADE_FIELD_NUMBER: _ClassVar[int]
    BEST_TRADE_PCT_FIELD_NUMBER: _ClassVar[int]
    WORST_TRADE_PCT_FIELD_NUMBER: _ClassVar[int]
    PAIR_RESULTS_FIELD_NUMBER: _ClassVar[int]
    RAW_LOG_FIELD_NUMBER: _ClassVar[int]
    TRADES_JSON_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    job_id: str
    strategy_id: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_total: float
    profit_pct: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    avg_trade_duration_minutes: float
    avg_profit_per_trade: float
    best_trade_pct: float
    worst_trade_pct: float
    pair_results: _containers.RepeatedCompositeFieldContainer[PairResult]
    raw_log: str
    trades_json: str
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., job_id: _Optional[str] = ..., strategy_id: _Optional[str] = ..., total_trades: _Optional[int] = ..., winning_trades: _Optional[int] = ..., losing_trades: _Optional[int] = ..., win_rate: _Optional[float] = ..., profit_total: _Optional[float] = ..., profit_pct: _Optional[float] = ..., profit_factor: _Optional[float] = ..., max_drawdown: _Optional[float] = ..., max_drawdown_pct: _Optional[float] = ..., sharpe_ratio: _Optional[float] = ..., sortino_ratio: _Optional[float] = ..., calmar_ratio: _Optional[float] = ..., avg_trade_duration_minutes: _Optional[float] = ..., avg_profit_per_trade: _Optional[float] = ..., best_trade_pct: _Optional[float] = ..., worst_trade_pct: _Optional[float] = ..., pair_results: _Optional[_Iterable[_Union[PairResult, _Mapping]]] = ..., raw_log: _Optional[str] = ..., trades_json: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class PairResult(_message.Message):
    __slots__ = ("pair", "trades", "profit_pct", "win_rate", "avg_duration_minutes")
    PAIR_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    PROFIT_PCT_FIELD_NUMBER: _ClassVar[int]
    WIN_RATE_FIELD_NUMBER: _ClassVar[int]
    AVG_DURATION_MINUTES_FIELD_NUMBER: _ClassVar[int]
    pair: str
    trades: int
    profit_pct: float
    win_rate: float
    avg_duration_minutes: float
    def __init__(self, pair: _Optional[str] = ..., trades: _Optional[int] = ..., profit_pct: _Optional[float] = ..., win_rate: _Optional[float] = ..., avg_duration_minutes: _Optional[float] = ...) -> None: ...

class SubmitBacktestRequest(_message.Message):
    __slots__ = ("strategy_id", "config", "optimization_run_id", "priority")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    OPTIMIZATION_RUN_ID_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    strategy_id: str
    config: BacktestConfig
    optimization_run_id: str
    priority: int
    def __init__(self, strategy_id: _Optional[str] = ..., config: _Optional[_Union[BacktestConfig, _Mapping]] = ..., optimization_run_id: _Optional[str] = ..., priority: _Optional[int] = ...) -> None: ...

class SubmitBacktestResponse(_message.Message):
    __slots__ = ("job",)
    JOB_FIELD_NUMBER: _ClassVar[int]
    job: BacktestJob
    def __init__(self, job: _Optional[_Union[BacktestJob, _Mapping]] = ...) -> None: ...

class SubmitBatchBacktestRequest(_message.Message):
    __slots__ = ("backtests",)
    BACKTESTS_FIELD_NUMBER: _ClassVar[int]
    backtests: _containers.RepeatedCompositeFieldContainer[SubmitBacktestRequest]
    def __init__(self, backtests: _Optional[_Iterable[_Union[SubmitBacktestRequest, _Mapping]]] = ...) -> None: ...

class SubmitBatchBacktestResponse(_message.Message):
    __slots__ = ("jobs",)
    JOBS_FIELD_NUMBER: _ClassVar[int]
    jobs: _containers.RepeatedCompositeFieldContainer[BacktestJob]
    def __init__(self, jobs: _Optional[_Iterable[_Union[BacktestJob, _Mapping]]] = ...) -> None: ...

class GetBacktestJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class GetBacktestJobResponse(_message.Message):
    __slots__ = ("job", "result")
    JOB_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    job: BacktestJob
    result: BacktestResult
    def __init__(self, job: _Optional[_Union[BacktestJob, _Mapping]] = ..., result: _Optional[_Union[BacktestResult, _Mapping]] = ...) -> None: ...

class GetBacktestResultRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class GetBacktestResultResponse(_message.Message):
    __slots__ = ("result",)
    RESULT_FIELD_NUMBER: _ClassVar[int]
    result: BacktestResult
    def __init__(self, result: _Optional[_Union[BacktestResult, _Mapping]] = ...) -> None: ...

class QueryBacktestResultsRequest(_message.Message):
    __slots__ = ("strategy_id", "optimization_run_id", "min_sharpe", "min_profit_pct", "max_drawdown_pct", "min_trades", "time_range", "pagination", "order_by", "ascending")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    OPTIMIZATION_RUN_ID_FIELD_NUMBER: _ClassVar[int]
    MIN_SHARPE_FIELD_NUMBER: _ClassVar[int]
    MIN_PROFIT_PCT_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_PCT_FIELD_NUMBER: _ClassVar[int]
    MIN_TRADES_FIELD_NUMBER: _ClassVar[int]
    TIME_RANGE_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    ORDER_BY_FIELD_NUMBER: _ClassVar[int]
    ASCENDING_FIELD_NUMBER: _ClassVar[int]
    strategy_id: str
    optimization_run_id: str
    min_sharpe: float
    min_profit_pct: float
    max_drawdown_pct: float
    min_trades: int
    time_range: _common_pb2.TimeRange
    pagination: _common_pb2.PaginationRequest
    order_by: str
    ascending: bool
    def __init__(self, strategy_id: _Optional[str] = ..., optimization_run_id: _Optional[str] = ..., min_sharpe: _Optional[float] = ..., min_profit_pct: _Optional[float] = ..., max_drawdown_pct: _Optional[float] = ..., min_trades: _Optional[int] = ..., time_range: _Optional[_Union[_common_pb2.TimeRange, _Mapping]] = ..., pagination: _Optional[_Union[_common_pb2.PaginationRequest, _Mapping]] = ..., order_by: _Optional[str] = ..., ascending: bool = ...) -> None: ...

class QueryBacktestResultsResponse(_message.Message):
    __slots__ = ("results", "pagination")
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[BacktestResultSummary]
    pagination: _common_pb2.PaginationResponse
    def __init__(self, results: _Optional[_Iterable[_Union[BacktestResultSummary, _Mapping]]] = ..., pagination: _Optional[_Union[_common_pb2.PaginationResponse, _Mapping]] = ...) -> None: ...

class BacktestResultSummary(_message.Message):
    __slots__ = ("id", "job_id", "strategy_id", "strategy_name", "profit_pct", "sharpe_ratio", "max_drawdown_pct", "total_trades", "win_rate", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    STRATEGY_NAME_FIELD_NUMBER: _ClassVar[int]
    PROFIT_PCT_FIELD_NUMBER: _ClassVar[int]
    SHARPE_RATIO_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_PCT_FIELD_NUMBER: _ClassVar[int]
    TOTAL_TRADES_FIELD_NUMBER: _ClassVar[int]
    WIN_RATE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    job_id: str
    strategy_id: str
    strategy_name: str
    profit_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    total_trades: int
    win_rate: float
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., job_id: _Optional[str] = ..., strategy_id: _Optional[str] = ..., strategy_name: _Optional[str] = ..., profit_pct: _Optional[float] = ..., sharpe_ratio: _Optional[float] = ..., max_drawdown_pct: _Optional[float] = ..., total_trades: _Optional[int] = ..., win_rate: _Optional[float] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CancelBacktestRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class CancelBacktestResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...

class GetQueueStatsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetQueueStatsResponse(_message.Message):
    __slots__ = ("pending_jobs", "running_jobs", "completed_today", "failed_today", "max_concurrent")
    PENDING_JOBS_FIELD_NUMBER: _ClassVar[int]
    RUNNING_JOBS_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_TODAY_FIELD_NUMBER: _ClassVar[int]
    FAILED_TODAY_FIELD_NUMBER: _ClassVar[int]
    MAX_CONCURRENT_FIELD_NUMBER: _ClassVar[int]
    pending_jobs: int
    running_jobs: int
    completed_today: int
    failed_today: int
    max_concurrent: int
    def __init__(self, pending_jobs: _Optional[int] = ..., running_jobs: _Optional[int] = ..., completed_today: _Optional[int] = ..., failed_today: _Optional[int] = ..., max_concurrent: _Optional[int] = ...) -> None: ...
