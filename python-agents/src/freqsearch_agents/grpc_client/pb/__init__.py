"""Generated protobuf and gRPC code for FreqSearch."""

from .freqsearch.v1.common_pb2 import (
    PaginationRequest,
    PaginationResponse,
    TimeRange,
    JobStatus,
    ApprovalStatus,
    HealthCheckRequest,
    HealthCheckResponse,
)
from .freqsearch.v1.strategy_pb2 import (
    Strategy,
    StrategyMetadata,
    StrategyWithMetrics,
    StrategyPerformanceMetrics,
    CreateStrategyRequest,
    CreateStrategyResponse,
    GetStrategyRequest,
    GetStrategyResponse,
    SearchStrategiesRequest,
    SearchStrategiesResponse,
)
from .freqsearch.v1.backtest_pb2 import (
    BacktestConfig,
    BacktestJob,
    BacktestResult,
    PairResult,
    SubmitBacktestRequest,
    SubmitBacktestResponse,
    GetBacktestJobRequest,
    GetBacktestJobResponse,
    GetBacktestResultRequest,
    GetBacktestResultResponse,
    QueryBacktestResultsRequest,
    QueryBacktestResultsResponse,
)
from .freqsearch.v1.freqsearch_pb2 import (
    OptimizationRun,
    OptimizationConfig,
    OptimizationCriteria,
    OptimizationMode,
    OptimizationStatus,
    OptimizationIteration,
    StartOptimizationRequest,
    StartOptimizationResponse,
    GetOptimizationRunRequest,
    GetOptimizationRunResponse,
)
from .freqsearch.v1.freqsearch_pb2_grpc import (
    FreqSearchServiceStub,
    FreqSearchServiceServicer,
    add_FreqSearchServiceServicer_to_server,
)

__all__ = [
    # Common
    "PaginationRequest",
    "PaginationResponse",
    "TimeRange",
    "JobStatus",
    "ApprovalStatus",
    "HealthCheckRequest",
    "HealthCheckResponse",
    # Strategy
    "Strategy",
    "StrategyMetadata",
    "StrategyWithMetrics",
    "StrategyPerformanceMetrics",
    "CreateStrategyRequest",
    "CreateStrategyResponse",
    "GetStrategyRequest",
    "GetStrategyResponse",
    "SearchStrategiesRequest",
    "SearchStrategiesResponse",
    # Backtest
    "BacktestConfig",
    "BacktestJob",
    "BacktestResult",
    "PairResult",
    "SubmitBacktestRequest",
    "SubmitBacktestResponse",
    "GetBacktestJobRequest",
    "GetBacktestJobResponse",
    "GetBacktestResultRequest",
    "GetBacktestResultResponse",
    "QueryBacktestResultsRequest",
    "QueryBacktestResultsResponse",
    # Optimization
    "OptimizationRun",
    "OptimizationConfig",
    "OptimizationCriteria",
    "OptimizationMode",
    "OptimizationStatus",
    "OptimizationIteration",
    "StartOptimizationRequest",
    "StartOptimizationResponse",
    "GetOptimizationRunRequest",
    "GetOptimizationRunResponse",
    # gRPC
    "FreqSearchServiceStub",
    "FreqSearchServiceServicer",
    "add_FreqSearchServiceServicer_to_server",
]
