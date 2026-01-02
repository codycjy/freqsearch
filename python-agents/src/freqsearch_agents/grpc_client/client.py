"""
FreqSearch gRPC Client - Async wrapper for all FreqSearchService RPC methods.

This module provides a comprehensive async gRPC client that simplifies interaction
with the FreqSearch backend. All proto messages are converted to Python dicts for ease of use.

Example:
    async with FreqSearchClient() as client:
        # Create a strategy
        strategy = await client.create_strategy(
            name="MyStrategy",
            code="# strategy code here"
        )

        # Submit a backtest (exchange/pairs/timeframe from base_config.json if empty)
        config = BacktestConfig(
            exchange="",  # Uses base_config.json (OKX by default)
            pairs=[],     # Uses base_config.json pairs
            timeframe="", # Uses base_config.json timeframe
            timerange_start="20230101",
            timerange_end="20230131"
        )
        job = await client.submit_backtest(strategy["id"], config)
"""

import grpc
from grpc import aio
import structlog
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from google.protobuf.json_format import MessageToDict
from google.protobuf.timestamp_pb2 import Timestamp

from .pb.freqsearch.v1 import (
    freqsearch_pb2,
    freqsearch_pb2_grpc,
    strategy_pb2,
    backtest_pb2,
    common_pb2,
)

logger = structlog.get_logger(__name__)


# ===== Custom Exceptions =====


class FreqSearchClientError(Exception):
    """Base exception for FreqSearch client errors."""

    def __init__(self, message: str, code: Optional[grpc.StatusCode] = None):
        super().__init__(message)
        self.code = code


class ConnectionError(FreqSearchClientError):
    """Connection-related errors."""
    pass


class NotFoundError(FreqSearchClientError):
    """Resource not found errors."""
    pass


class ValidationError(FreqSearchClientError):
    """Invalid request validation errors."""
    pass


class InternalError(FreqSearchClientError):
    """Internal server errors."""
    pass


class CancelledError(FreqSearchClientError):
    """Operation cancelled errors."""
    pass


class TimeoutError(FreqSearchClientError):
    """Operation timeout errors."""
    pass


def _map_grpc_error(exc: grpc.RpcError) -> FreqSearchClientError:
    """Map gRPC status codes to custom exceptions."""
    code = exc.code()
    details = exc.details() if hasattr(exc, "details") else str(exc)

    error_map = {
        grpc.StatusCode.NOT_FOUND: NotFoundError,
        grpc.StatusCode.INVALID_ARGUMENT: ValidationError,
        grpc.StatusCode.FAILED_PRECONDITION: ValidationError,
        grpc.StatusCode.OUT_OF_RANGE: ValidationError,
        grpc.StatusCode.INTERNAL: InternalError,
        grpc.StatusCode.UNKNOWN: InternalError,
        grpc.StatusCode.DATA_LOSS: InternalError,
        grpc.StatusCode.UNAVAILABLE: ConnectionError,
        grpc.StatusCode.DEADLINE_EXCEEDED: TimeoutError,
        grpc.StatusCode.CANCELLED: CancelledError,
    }

    error_class = error_map.get(code, FreqSearchClientError)
    return error_class(f"{code.name}: {details}", code)


# ===== Configuration Dataclasses =====


@dataclass
class BacktestConfig:
    """Configuration for a single backtest run."""

    exchange: str
    pairs: List[str]
    timeframe: str
    timerange_start: str
    timerange_end: str
    dry_run_wallet: float = 1000.0
    max_open_trades: int = 3
    stake_amount: str = "unlimited"

    def to_proto(self) -> backtest_pb2.BacktestConfig:
        """Convert to protobuf message."""
        return backtest_pb2.BacktestConfig(
            exchange=self.exchange,
            pairs=self.pairs,
            timeframe=self.timeframe,
            timerange_start=self.timerange_start,
            timerange_end=self.timerange_end,
            dry_run_wallet=self.dry_run_wallet,
            max_open_trades=self.max_open_trades,
            stake_amount=self.stake_amount,
        )


@dataclass
class OptimizationCriteria:
    """Optimization criteria for filtering results."""

    min_sharpe: float = 0.0
    min_profit_pct: float = 0.0
    max_drawdown_pct: float = 100.0
    min_trades: int = 1
    min_win_rate: float = 0.0

    def to_proto(self) -> freqsearch_pb2.OptimizationCriteria:
        """Convert to protobuf message."""
        return freqsearch_pb2.OptimizationCriteria(
            min_sharpe=self.min_sharpe,
            min_profit_pct=self.min_profit_pct,
            max_drawdown_pct=self.max_drawdown_pct,
            min_trades=self.min_trades,
            min_win_rate=self.min_win_rate,
        )


@dataclass
class OptimizationConfig:
    """Configuration for optimization runs."""

    backtest_config: BacktestConfig
    max_iterations: int = 10
    criteria: OptimizationCriteria = field(default_factory=OptimizationCriteria)
    mode: str = "balanced"  # maximize_sharpe, maximize_profit, minimize_drawdown, balanced

    def to_proto(self) -> freqsearch_pb2.OptimizationConfig:
        """Convert to protobuf message."""
        mode_map = {
            "maximize_sharpe": freqsearch_pb2.OPTIMIZATION_MODE_MAXIMIZE_SHARPE,
            "maximize_profit": freqsearch_pb2.OPTIMIZATION_MODE_MAXIMIZE_PROFIT,
            "minimize_drawdown": freqsearch_pb2.OPTIMIZATION_MODE_MINIMIZE_DRAWDOWN,
            "balanced": freqsearch_pb2.OPTIMIZATION_MODE_BALANCED,
        }

        return freqsearch_pb2.OptimizationConfig(
            backtest_config=self.backtest_config.to_proto(),
            max_iterations=self.max_iterations,
            criteria=self.criteria.to_proto(),
            mode=mode_map.get(self.mode, freqsearch_pb2.OPTIMIZATION_MODE_BALANCED),
        )


# ===== Main Client =====


class FreqSearchClient:
    """
    Async gRPC client for FreqSearch backend.

    Provides pythonic async/await interface to all FreqSearchService RPC methods.
    Automatically handles connection management, retries, and error mapping.

    Example:
        async with FreqSearchClient("localhost:50051") as client:
            strategies = await client.search_strategies(min_sharpe=1.0)
            for strategy in strategies["strategies"]:
                print(f"{strategy['name']}: {strategy['metrics']['sharpe_ratio']}")
    """

    def __init__(
        self,
        address: str = "localhost:50051",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize FreqSearch client.

        Args:
            address: gRPC server address (host:port)
            timeout: Default RPC timeout in seconds
            max_retries: Maximum number of retry attempts for failed RPCs
            retry_delay: Delay between retries in seconds
        """
        self.address = address
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._channel: Optional[aio.Channel] = None
        self._stub: Optional[freqsearch_pb2_grpc.FreqSearchServiceStub] = None

        logger.debug("FreqSearchClient initialized", address=address, timeout=timeout)

    async def connect(self) -> None:
        """Establish connection to gRPC server."""
        if self._channel is not None:
            logger.warning("Already connected, skipping connect")
            return

        try:
            self._channel = aio.insecure_channel(self.address)
            self._stub = freqsearch_pb2_grpc.FreqSearchServiceStub(self._channel)

            # Test connection with health check
            await self.health_check()

            logger.info("Connected to FreqSearch backend", address=self.address)
        except Exception as e:
            logger.error("Failed to connect", address=self.address, error=str(e))
            raise ConnectionError(f"Failed to connect to {self.address}: {e}")

    async def close(self) -> None:
        """Close the gRPC channel."""
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None
            logger.info("Disconnected from FreqSearch backend")

    async def __aenter__(self) -> "FreqSearchClient":
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        await self.close()

    def _ensure_connected(self) -> None:
        """Ensure client is connected."""
        if self._stub is None:
            raise ConnectionError("Not connected. Call connect() or use context manager.")

    # ===== Strategy Operations =====

    async def create_strategy(
        self,
        name: str,
        code: str,
        description: str = "",
        parent_id: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new strategy.

        Args:
            name: Strategy name
            code: Strategy Python code
            description: Strategy description
            parent_id: Optional parent strategy ID for lineage tracking
            tags: Optional strategy tags (strategy_type, risk_level, etc.)

        Returns:
            Strategy dict with id, name, code, metadata, etc.

        Raises:
            ValidationError: Invalid strategy code or parameters
            InternalError: Backend processing error

        Example:
            strategy = await client.create_strategy(
                name="RSI Strategy",
                code="# strategy code...",
                description="Simple RSI strategy",
                tags={"strategy_type": ["trend_following"], "risk_level": "medium"}
            )
        """
        self._ensure_connected()

        request = strategy_pb2.CreateStrategyRequest(
            name=name,
            code=code,
            description=description,
        )

        if parent_id:
            request.parent_id = parent_id

        if tags:
            request.tags.CopyFrom(strategy_pb2.StrategyTags(**tags))

        try:
            response = await self._stub.CreateStrategy(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.info("Strategy created", strategy_id=result["strategy"]["id"], name=name)
            return result
        except grpc.RpcError as e:
            logger.error("Failed to create strategy", name=name, error=str(e))
            raise _map_grpc_error(e)

    async def get_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """
        Get strategy by ID.

        Args:
            strategy_id: Strategy ID

        Returns:
            Strategy dict

        Raises:
            NotFoundError: Strategy not found
        """
        self._ensure_connected()

        request = strategy_pb2.GetStrategyRequest(id=strategy_id)

        try:
            response = await self._stub.GetStrategy(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.debug("Strategy retrieved", strategy_id=strategy_id)
            return result
        except grpc.RpcError as e:
            logger.error("Failed to get strategy", strategy_id=strategy_id, error=str(e))
            raise _map_grpc_error(e)

    async def search_strategies(
        self,
        name_pattern: Optional[str] = None,
        min_sharpe: Optional[float] = None,
        min_profit_pct: Optional[float] = None,
        min_trades: Optional[int] = None,
        max_drawdown_pct: Optional[float] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "sharpe",
        ascending: bool = False,
    ) -> Dict[str, Any]:
        """
        Search strategies with filters.

        Args:
            name_pattern: SQL LIKE pattern for strategy name
            min_sharpe: Minimum Sharpe ratio filter
            min_profit_pct: Minimum profit percentage filter
            min_trades: Minimum number of trades filter
            max_drawdown_pct: Maximum drawdown percentage filter
            page: Page number (1-indexed)
            page_size: Results per page
            order_by: Sort field (sharpe, profit_pct, trades, etc.)
            ascending: Sort order (False = descending)

        Returns:
            Dict with "strategies" list and "pagination" info

        Example:
            results = await client.search_strategies(
                min_sharpe=1.5,
                min_profit_pct=10.0,
                page=1,
                page_size=10,
                order_by="sharpe"
            )
            for strategy in results["strategies"]:
                print(strategy["strategy"]["name"])
        """
        self._ensure_connected()

        request = strategy_pb2.SearchStrategiesRequest(
            pagination=common_pb2.PaginationRequest(page=page, page_size=page_size),
            order_by=order_by,
            ascending=ascending,
        )

        if name_pattern:
            request.name_pattern = name_pattern
        if min_sharpe is not None:
            request.min_sharpe = min_sharpe
        if min_profit_pct is not None:
            request.min_profit_pct = min_profit_pct
        if min_trades is not None:
            request.min_trades = min_trades
        if max_drawdown_pct is not None:
            request.max_drawdown_pct = max_drawdown_pct

        try:
            response = await self._stub.SearchStrategies(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.debug("Strategies searched", count=len(result.get("strategies", [])))
            return result
        except grpc.RpcError as e:
            logger.error("Failed to search strategies", error=str(e))
            raise _map_grpc_error(e)

    async def get_strategy_lineage(self, strategy_id: str, depth: int = 5) -> Dict[str, Any]:
        """
        Get strategy evolution lineage (ancestors and descendants).

        Args:
            strategy_id: Strategy ID
            depth: Maximum depth to traverse

        Returns:
            Dict with "lineage" tree structure

        Example:
            lineage = await client.get_strategy_lineage("strategy-123", depth=3)
            for node in lineage["lineage"]:
                print(f"{node['strategy']['name']} -> {len(node['children'])} children")
        """
        self._ensure_connected()

        request = strategy_pb2.GetStrategyLineageRequest(
            strategy_id=strategy_id,
            depth=depth,
        )

        try:
            response = await self._stub.GetStrategyLineage(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.debug("Strategy lineage retrieved", strategy_id=strategy_id, depth=depth)
            return result
        except grpc.RpcError as e:
            logger.error("Failed to get strategy lineage", strategy_id=strategy_id, error=str(e))
            raise _map_grpc_error(e)

    async def delete_strategy(self, strategy_id: str) -> bool:
        """
        Delete a strategy.

        Args:
            strategy_id: Strategy ID to delete

        Returns:
            True if successful

        Raises:
            NotFoundError: Strategy not found
        """
        self._ensure_connected()

        request = strategy_pb2.DeleteStrategyRequest(id=strategy_id)

        try:
            response = await self._stub.DeleteStrategy(request, timeout=self.timeout)
            logger.info("Strategy deleted", strategy_id=strategy_id)
            return response.success
        except grpc.RpcError as e:
            logger.error("Failed to delete strategy", strategy_id=strategy_id, error=str(e))
            raise _map_grpc_error(e)

    async def validate_strategy(self, code: str, name: str = "ValidatedStrategy") -> Dict[str, Any]:
        """
        Validate strategy code using Docker container.

        Fast validation that checks:
        - Python syntax
        - Import availability
        - IStrategy class presence
        - Required methods

        Args:
            code: Python source code of the strategy
            name: Strategy class name (optional)

        Returns:
            Dict with:
                - valid: bool - whether validation passed
                - errors: List[str] - validation errors
                - warnings: List[str] - non-fatal warnings
                - class_name: str - detected strategy class name

        Example:
            result = await client.validate_strategy(strategy_code)
            if not result["valid"]:
                print("Errors:", result["errors"])
        """
        self._ensure_connected()

        request = strategy_pb2.ValidateStrategyRequest(
            code=code,
            name=name,
        )

        try:
            response = await self._stub.ValidateStrategy(request, timeout=60.0)  # Validation may take time on first run (building image)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.info(
                "Strategy validated",
                valid=result.get("valid", False),
                errors=result.get("errors", []),
            )
            return result
        except grpc.RpcError as e:
            logger.error("Failed to validate strategy", error=str(e))
            raise _map_grpc_error(e)

    # ===== Backtest Operations =====

    async def submit_backtest(
        self,
        strategy_id: str,
        config: BacktestConfig,
        optimization_run_id: Optional[str] = None,
        priority: int = 0,
    ) -> Dict[str, Any]:
        """
        Submit a backtest job.

        Args:
            strategy_id: Strategy to backtest
            config: Backtest configuration
            optimization_run_id: Optional optimization run ID
            priority: Job priority (higher = more priority)

        Returns:
            BacktestJob dict with job_id, status, etc.

        Example:
            config = BacktestConfig(
                exchange="binance",
                pairs=["BTC/USDT", "ETH/USDT"],
                timeframe="1h",
                timerange_start="20230101",
                timerange_end="20230131",
                dry_run_wallet=1000.0,
                max_open_trades=3
            )
            job = await client.submit_backtest("strategy-123", config)
            print(f"Job ID: {job['job']['id']}")
        """
        self._ensure_connected()

        request = backtest_pb2.SubmitBacktestRequest(
            strategy_id=strategy_id,
            config=config.to_proto(),
            priority=priority,
        )

        if optimization_run_id:
            request.optimization_run_id = optimization_run_id

        try:
            response = await self._stub.SubmitBacktest(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.info("Backtest submitted", job_id=result["job"]["id"], strategy_id=strategy_id)
            return result
        except grpc.RpcError as e:
            logger.error("Failed to submit backtest", strategy_id=strategy_id, error=str(e))
            raise _map_grpc_error(e)

    async def submit_batch_backtest(
        self,
        backtests: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Submit multiple backtest jobs in batch.

        Args:
            backtests: List of dicts with keys: strategy_id, config, priority

        Returns:
            List of BacktestJob dicts

        Example:
            config = BacktestConfig(...)
            jobs = await client.submit_batch_backtest([
                {"strategy_id": "s1", "config": config, "priority": 1},
                {"strategy_id": "s2", "config": config, "priority": 2},
            ])
        """
        self._ensure_connected()

        backtest_requests = []
        for bt in backtests:
            req = backtest_pb2.SubmitBacktestRequest(
                strategy_id=bt["strategy_id"],
                config=bt["config"].to_proto(),
                priority=bt.get("priority", 0),
            )
            if "optimization_run_id" in bt:
                req.optimization_run_id = bt["optimization_run_id"]
            backtest_requests.append(req)

        request = backtest_pb2.SubmitBatchBacktestRequest(backtests=backtest_requests)

        try:
            response = await self._stub.SubmitBatchBacktest(request, timeout=self.timeout * 2)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.info("Batch backtest submitted", count=len(result.get("jobs", [])))
            return result.get("jobs", [])
        except grpc.RpcError as e:
            logger.error("Failed to submit batch backtest", error=str(e))
            raise _map_grpc_error(e)

    async def get_backtest_job(self, job_id: str) -> Dict[str, Any]:
        """
        Get backtest job status and result.

        Args:
            job_id: Backtest job ID

        Returns:
            Dict with "job" and optionally "result" (if completed)

        Example:
            job_data = await client.get_backtest_job("job-123")
            if job_data["job"]["status"] == "JOB_STATUS_COMPLETED":
                print(f"Profit: {job_data['result']['profit_pct']}%")
        """
        self._ensure_connected()

        request = backtest_pb2.GetBacktestJobRequest(job_id=job_id)

        try:
            response = await self._stub.GetBacktestJob(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.debug("Backtest job retrieved", job_id=job_id, status=result["job"]["status"])
            return result
        except grpc.RpcError as e:
            logger.error("Failed to get backtest job", job_id=job_id, error=str(e))
            raise _map_grpc_error(e)

    async def get_backtest_result(self, job_id: str) -> Dict[str, Any]:
        """
        Get backtest result only (waits for completion).

        Args:
            job_id: Backtest job ID

        Returns:
            BacktestResult dict

        Raises:
            NotFoundError: Result not found (job not completed)
        """
        self._ensure_connected()

        request = backtest_pb2.GetBacktestResultRequest(job_id=job_id)

        try:
            response = await self._stub.GetBacktestResult(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.debug("Backtest result retrieved", job_id=job_id)
            return result
        except grpc.RpcError as e:
            logger.error("Failed to get backtest result", job_id=job_id, error=str(e))
            raise _map_grpc_error(e)

    async def query_backtest_results(
        self,
        strategy_id: Optional[str] = None,
        optimization_run_id: Optional[str] = None,
        min_sharpe: Optional[float] = None,
        min_profit_pct: Optional[float] = None,
        max_drawdown_pct: Optional[float] = None,
        min_trades: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "sharpe",
        ascending: bool = False,
    ) -> Dict[str, Any]:
        """
        Query backtest results with filters.

        Args:
            strategy_id: Filter by strategy ID
            optimization_run_id: Filter by optimization run ID
            min_sharpe: Minimum Sharpe ratio
            min_profit_pct: Minimum profit percentage
            max_drawdown_pct: Maximum drawdown percentage
            min_trades: Minimum number of trades
            page: Page number
            page_size: Results per page
            order_by: Sort field
            ascending: Sort order

        Returns:
            Dict with "results" list and "pagination" info
        """
        self._ensure_connected()

        request = backtest_pb2.QueryBacktestResultsRequest(
            pagination=common_pb2.PaginationRequest(page=page, page_size=page_size),
            order_by=order_by,
            ascending=ascending,
        )

        if strategy_id:
            request.strategy_id = strategy_id
        if optimization_run_id:
            request.optimization_run_id = optimization_run_id
        if min_sharpe is not None:
            request.min_sharpe = min_sharpe
        if min_profit_pct is not None:
            request.min_profit_pct = min_profit_pct
        if max_drawdown_pct is not None:
            request.max_drawdown_pct = max_drawdown_pct
        if min_trades is not None:
            request.min_trades = min_trades

        try:
            response = await self._stub.QueryBacktestResults(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.debug("Backtest results queried", count=len(result.get("results", [])))
            return result
        except grpc.RpcError as e:
            logger.error("Failed to query backtest results", error=str(e))
            raise _map_grpc_error(e)

    async def cancel_backtest(self, job_id: str) -> bool:
        """
        Cancel a backtest job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if successful
        """
        self._ensure_connected()

        request = backtest_pb2.CancelBacktestRequest(job_id=job_id)

        try:
            response = await self._stub.CancelBacktest(request, timeout=self.timeout)
            logger.info("Backtest cancelled", job_id=job_id, success=response.success)
            return response.success
        except grpc.RpcError as e:
            logger.error("Failed to cancel backtest", job_id=job_id, error=str(e))
            raise _map_grpc_error(e)

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dict with pending_jobs, running_jobs, completed_today, etc.

        Example:
            stats = await client.get_queue_stats()
            print(f"Pending: {stats['pending_jobs']}, Running: {stats['running_jobs']}")
        """
        self._ensure_connected()

        request = backtest_pb2.GetQueueStatsRequest()

        try:
            response = await self._stub.GetQueueStats(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.debug("Queue stats retrieved", **result)
            return result
        except grpc.RpcError as e:
            logger.error("Failed to get queue stats", error=str(e))
            raise _map_grpc_error(e)

    # ===== Optimization Operations =====

    async def start_optimization(
        self,
        name: str,
        base_strategy_id: str,
        config: OptimizationConfig,
    ) -> Dict[str, Any]:
        """
        Start a new optimization run.

        Args:
            name: Optimization run name
            base_strategy_id: Base strategy to optimize from
            config: Optimization configuration

        Returns:
            OptimizationRun dict with run_id, status, etc.

        Example:
            opt_config = OptimizationConfig(
                backtest_config=BacktestConfig(...),
                max_iterations=20,
                criteria=OptimizationCriteria(min_sharpe=1.0, min_profit_pct=5.0),
                mode="maximize_sharpe"
            )
            run = await client.start_optimization(
                "Optimize RSI Strategy",
                "strategy-123",
                opt_config
            )
        """
        self._ensure_connected()

        request = freqsearch_pb2.StartOptimizationRequest(
            name=name,
            base_strategy_id=base_strategy_id,
            config=config.to_proto(),
        )

        try:
            response = await self._stub.StartOptimization(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.info("Optimization started", run_id=result["run"]["id"], name=name)
            return result
        except grpc.RpcError as e:
            logger.error("Failed to start optimization", name=name, error=str(e))
            raise _map_grpc_error(e)

    async def get_optimization_run(self, run_id: str) -> Dict[str, Any]:
        """
        Get optimization run with iterations.

        Args:
            run_id: Optimization run ID

        Returns:
            Dict with "run" and "iterations" list

        Example:
            data = await client.get_optimization_run("run-123")
            run = data["run"]
            print(f"Status: {run['status']}, Iteration: {run['current_iteration']}")
            for iteration in data["iterations"]:
                print(f"  Iter {iteration['iteration_number']}: {iteration['result']['sharpe_ratio']}")
        """
        self._ensure_connected()

        request = freqsearch_pb2.GetOptimizationRunRequest(run_id=run_id)

        try:
            response = await self._stub.GetOptimizationRun(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.debug("Optimization run retrieved", run_id=run_id)
            return result
        except grpc.RpcError as e:
            logger.error("Failed to get optimization run", run_id=run_id, error=str(e))
            raise _map_grpc_error(e)

    async def control_optimization(
        self,
        run_id: str,
        action: str,  # "pause", "resume", "cancel", "complete", "fail"
        termination_reason: Optional[str] = None,
        best_strategy_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Control an optimization run (pause, resume, cancel, complete, fail).

        Args:
            run_id: Optimization run ID
            action: Control action ("pause", "resume", "cancel", "complete", "fail")
            termination_reason: Optional reason for termination (for complete/fail actions)
            best_strategy_id: Optional best strategy ID (for complete action)

        Returns:
            Dict with "success" and updated "run"

        Example:
            result = await client.control_optimization("run-123", "pause")
            if result["success"]:
                print(f"Run paused: {result['run']['status']}")

            # Complete with metadata
            result = await client.control_optimization(
                "run-123", "complete",
                termination_reason="max_iterations",
                best_strategy_id="strategy-456"
            )
        """
        self._ensure_connected()

        action_map = {
            "pause": freqsearch_pb2.OPTIMIZATION_ACTION_PAUSE,
            "resume": freqsearch_pb2.OPTIMIZATION_ACTION_RESUME,
            "cancel": freqsearch_pb2.OPTIMIZATION_ACTION_CANCEL,
            "complete": freqsearch_pb2.OPTIMIZATION_ACTION_COMPLETE,
            "fail": freqsearch_pb2.OPTIMIZATION_ACTION_FAIL,
        }

        if action not in action_map:
            raise ValidationError(f"Invalid action: {action}. Must be one of: pause, resume, cancel, complete, fail")

        # Build request with optional fields
        request_kwargs = {
            "run_id": run_id,
            "action": action_map[action],
        }
        if termination_reason:
            request_kwargs["termination_reason"] = termination_reason
        if best_strategy_id:
            request_kwargs["best_strategy_id"] = best_strategy_id

        request = freqsearch_pb2.ControlOptimizationRequest(**request_kwargs)

        try:
            response = await self._stub.ControlOptimization(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.info("Optimization controlled", run_id=run_id, action=action, success=result["success"])
            return result
        except grpc.RpcError as e:
            logger.error("Failed to control optimization", run_id=run_id, action=action, error=str(e))
            raise _map_grpc_error(e)

    async def list_optimization_runs(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        List optimization runs.

        Args:
            status: Filter by status (pending, running, paused, completed, failed, cancelled)
            page: Page number
            page_size: Results per page

        Returns:
            Dict with "runs" list and "pagination" info
        """
        self._ensure_connected()

        request = freqsearch_pb2.ListOptimizationRunsRequest(
            pagination=common_pb2.PaginationRequest(page=page, page_size=page_size),
        )

        if status:
            status_map = {
                "pending": freqsearch_pb2.OPTIMIZATION_STATUS_PENDING,
                "running": freqsearch_pb2.OPTIMIZATION_STATUS_RUNNING,
                "paused": freqsearch_pb2.OPTIMIZATION_STATUS_PAUSED,
                "completed": freqsearch_pb2.OPTIMIZATION_STATUS_COMPLETED,
                "failed": freqsearch_pb2.OPTIMIZATION_STATUS_FAILED,
                "cancelled": freqsearch_pb2.OPTIMIZATION_STATUS_CANCELLED,
            }
            if status in status_map:
                request.status = status_map[status]

        try:
            response = await self._stub.ListOptimizationRuns(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.debug("Optimization runs listed", count=len(result.get("runs", [])))
            return result
        except grpc.RpcError as e:
            logger.error("Failed to list optimization runs", error=str(e))
            raise _map_grpc_error(e)

    # ===== Health =====

    async def health_check(self) -> Dict[str, Any]:
        """
        Check backend health.

        Returns:
            Dict with "healthy", "version", and "services" status

        Example:
            health = await client.health_check()
            if health["healthy"]:
                print(f"Backend version: {health['version']}")
                for service, status in health["services"].items():
                    print(f"  {service}: {'OK' if status else 'DOWN'}")
        """
        self._ensure_connected()

        request = common_pb2.HealthCheckRequest()

        try:
            response = await self._stub.HealthCheck(request, timeout=self.timeout)
            result = MessageToDict(response, preserving_proto_field_name=True)
            logger.debug("Health check completed", healthy=result["healthy"])
            return result
        except grpc.RpcError as e:
            logger.error("Health check failed", error=str(e))
            raise _map_grpc_error(e)
