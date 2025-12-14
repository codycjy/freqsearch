import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from freqsearch.v1 import common_pb2 as _common_pb2
from freqsearch.v1 import strategy_pb2 as _strategy_pb2
from freqsearch.v1 import backtest_pb2 as _backtest_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OptimizationMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OPTIMIZATION_MODE_UNSPECIFIED: _ClassVar[OptimizationMode]
    OPTIMIZATION_MODE_MAXIMIZE_SHARPE: _ClassVar[OptimizationMode]
    OPTIMIZATION_MODE_MAXIMIZE_PROFIT: _ClassVar[OptimizationMode]
    OPTIMIZATION_MODE_MINIMIZE_DRAWDOWN: _ClassVar[OptimizationMode]
    OPTIMIZATION_MODE_BALANCED: _ClassVar[OptimizationMode]

class OptimizationStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OPTIMIZATION_STATUS_UNSPECIFIED: _ClassVar[OptimizationStatus]
    OPTIMIZATION_STATUS_PENDING: _ClassVar[OptimizationStatus]
    OPTIMIZATION_STATUS_RUNNING: _ClassVar[OptimizationStatus]
    OPTIMIZATION_STATUS_PAUSED: _ClassVar[OptimizationStatus]
    OPTIMIZATION_STATUS_COMPLETED: _ClassVar[OptimizationStatus]
    OPTIMIZATION_STATUS_FAILED: _ClassVar[OptimizationStatus]
    OPTIMIZATION_STATUS_CANCELLED: _ClassVar[OptimizationStatus]

class OptimizationAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OPTIMIZATION_ACTION_UNSPECIFIED: _ClassVar[OptimizationAction]
    OPTIMIZATION_ACTION_PAUSE: _ClassVar[OptimizationAction]
    OPTIMIZATION_ACTION_RESUME: _ClassVar[OptimizationAction]
    OPTIMIZATION_ACTION_CANCEL: _ClassVar[OptimizationAction]
OPTIMIZATION_MODE_UNSPECIFIED: OptimizationMode
OPTIMIZATION_MODE_MAXIMIZE_SHARPE: OptimizationMode
OPTIMIZATION_MODE_MAXIMIZE_PROFIT: OptimizationMode
OPTIMIZATION_MODE_MINIMIZE_DRAWDOWN: OptimizationMode
OPTIMIZATION_MODE_BALANCED: OptimizationMode
OPTIMIZATION_STATUS_UNSPECIFIED: OptimizationStatus
OPTIMIZATION_STATUS_PENDING: OptimizationStatus
OPTIMIZATION_STATUS_RUNNING: OptimizationStatus
OPTIMIZATION_STATUS_PAUSED: OptimizationStatus
OPTIMIZATION_STATUS_COMPLETED: OptimizationStatus
OPTIMIZATION_STATUS_FAILED: OptimizationStatus
OPTIMIZATION_STATUS_CANCELLED: OptimizationStatus
OPTIMIZATION_ACTION_UNSPECIFIED: OptimizationAction
OPTIMIZATION_ACTION_PAUSE: OptimizationAction
OPTIMIZATION_ACTION_RESUME: OptimizationAction
OPTIMIZATION_ACTION_CANCEL: OptimizationAction

class OptimizationRun(_message.Message):
    __slots__ = ("id", "name", "base_strategy_id", "config", "status", "current_iteration", "max_iterations", "best_strategy_id", "best_result", "termination_reason", "created_at", "updated_at", "completed_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    BASE_STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_ITERATION_FIELD_NUMBER: _ClassVar[int]
    MAX_ITERATIONS_FIELD_NUMBER: _ClassVar[int]
    BEST_STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    BEST_RESULT_FIELD_NUMBER: _ClassVar[int]
    TERMINATION_REASON_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    base_strategy_id: str
    config: OptimizationConfig
    status: OptimizationStatus
    current_iteration: int
    max_iterations: int
    best_strategy_id: str
    best_result: _backtest_pb2.BacktestResult
    termination_reason: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    completed_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., base_strategy_id: _Optional[str] = ..., config: _Optional[_Union[OptimizationConfig, _Mapping]] = ..., status: _Optional[_Union[OptimizationStatus, str]] = ..., current_iteration: _Optional[int] = ..., max_iterations: _Optional[int] = ..., best_strategy_id: _Optional[str] = ..., best_result: _Optional[_Union[_backtest_pb2.BacktestResult, _Mapping]] = ..., termination_reason: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., completed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class OptimizationConfig(_message.Message):
    __slots__ = ("backtest_config", "max_iterations", "criteria", "mode")
    BACKTEST_CONFIG_FIELD_NUMBER: _ClassVar[int]
    MAX_ITERATIONS_FIELD_NUMBER: _ClassVar[int]
    CRITERIA_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    backtest_config: _backtest_pb2.BacktestConfig
    max_iterations: int
    criteria: OptimizationCriteria
    mode: OptimizationMode
    def __init__(self, backtest_config: _Optional[_Union[_backtest_pb2.BacktestConfig, _Mapping]] = ..., max_iterations: _Optional[int] = ..., criteria: _Optional[_Union[OptimizationCriteria, _Mapping]] = ..., mode: _Optional[_Union[OptimizationMode, str]] = ...) -> None: ...

class OptimizationCriteria(_message.Message):
    __slots__ = ("min_sharpe", "min_profit_pct", "max_drawdown_pct", "min_trades", "min_win_rate")
    MIN_SHARPE_FIELD_NUMBER: _ClassVar[int]
    MIN_PROFIT_PCT_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_PCT_FIELD_NUMBER: _ClassVar[int]
    MIN_TRADES_FIELD_NUMBER: _ClassVar[int]
    MIN_WIN_RATE_FIELD_NUMBER: _ClassVar[int]
    min_sharpe: float
    min_profit_pct: float
    max_drawdown_pct: float
    min_trades: int
    min_win_rate: float
    def __init__(self, min_sharpe: _Optional[float] = ..., min_profit_pct: _Optional[float] = ..., max_drawdown_pct: _Optional[float] = ..., min_trades: _Optional[int] = ..., min_win_rate: _Optional[float] = ...) -> None: ...

class OptimizationIteration(_message.Message):
    __slots__ = ("iteration_number", "strategy_id", "backtest_job_id", "result", "engineer_changes", "analyst_feedback", "approval", "timestamp")
    ITERATION_NUMBER_FIELD_NUMBER: _ClassVar[int]
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    BACKTEST_JOB_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    ENGINEER_CHANGES_FIELD_NUMBER: _ClassVar[int]
    ANALYST_FEEDBACK_FIELD_NUMBER: _ClassVar[int]
    APPROVAL_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    iteration_number: int
    strategy_id: str
    backtest_job_id: str
    result: _backtest_pb2.BacktestResult
    engineer_changes: str
    analyst_feedback: str
    approval: _common_pb2.ApprovalStatus
    timestamp: _timestamp_pb2.Timestamp
    def __init__(self, iteration_number: _Optional[int] = ..., strategy_id: _Optional[str] = ..., backtest_job_id: _Optional[str] = ..., result: _Optional[_Union[_backtest_pb2.BacktestResult, _Mapping]] = ..., engineer_changes: _Optional[str] = ..., analyst_feedback: _Optional[str] = ..., approval: _Optional[_Union[_common_pb2.ApprovalStatus, str]] = ..., timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class StartOptimizationRequest(_message.Message):
    __slots__ = ("name", "base_strategy_id", "config")
    NAME_FIELD_NUMBER: _ClassVar[int]
    BASE_STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    name: str
    base_strategy_id: str
    config: OptimizationConfig
    def __init__(self, name: _Optional[str] = ..., base_strategy_id: _Optional[str] = ..., config: _Optional[_Union[OptimizationConfig, _Mapping]] = ...) -> None: ...

class StartOptimizationResponse(_message.Message):
    __slots__ = ("run",)
    RUN_FIELD_NUMBER: _ClassVar[int]
    run: OptimizationRun
    def __init__(self, run: _Optional[_Union[OptimizationRun, _Mapping]] = ...) -> None: ...

class GetOptimizationRunRequest(_message.Message):
    __slots__ = ("run_id",)
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    def __init__(self, run_id: _Optional[str] = ...) -> None: ...

class GetOptimizationRunResponse(_message.Message):
    __slots__ = ("run", "iterations")
    RUN_FIELD_NUMBER: _ClassVar[int]
    ITERATIONS_FIELD_NUMBER: _ClassVar[int]
    run: OptimizationRun
    iterations: _containers.RepeatedCompositeFieldContainer[OptimizationIteration]
    def __init__(self, run: _Optional[_Union[OptimizationRun, _Mapping]] = ..., iterations: _Optional[_Iterable[_Union[OptimizationIteration, _Mapping]]] = ...) -> None: ...

class ControlOptimizationRequest(_message.Message):
    __slots__ = ("run_id", "action")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    action: OptimizationAction
    def __init__(self, run_id: _Optional[str] = ..., action: _Optional[_Union[OptimizationAction, str]] = ...) -> None: ...

class ControlOptimizationResponse(_message.Message):
    __slots__ = ("success", "run")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    RUN_FIELD_NUMBER: _ClassVar[int]
    success: bool
    run: OptimizationRun
    def __init__(self, success: bool = ..., run: _Optional[_Union[OptimizationRun, _Mapping]] = ...) -> None: ...

class ListOptimizationRunsRequest(_message.Message):
    __slots__ = ("status", "time_range", "pagination")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TIME_RANGE_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    status: OptimizationStatus
    time_range: _common_pb2.TimeRange
    pagination: _common_pb2.PaginationRequest
    def __init__(self, status: _Optional[_Union[OptimizationStatus, str]] = ..., time_range: _Optional[_Union[_common_pb2.TimeRange, _Mapping]] = ..., pagination: _Optional[_Union[_common_pb2.PaginationRequest, _Mapping]] = ...) -> None: ...

class ListOptimizationRunsResponse(_message.Message):
    __slots__ = ("runs", "pagination")
    RUNS_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    runs: _containers.RepeatedCompositeFieldContainer[OptimizationRun]
    pagination: _common_pb2.PaginationResponse
    def __init__(self, runs: _Optional[_Iterable[_Union[OptimizationRun, _Mapping]]] = ..., pagination: _Optional[_Union[_common_pb2.PaginationResponse, _Mapping]] = ...) -> None: ...
