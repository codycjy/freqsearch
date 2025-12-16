/**
 * DataProvider Usage Examples
 *
 * This file demonstrates how to use the FreqSearch data provider
 * for various operations.
 */

import { useList, useOne, useCreate, useDelete, useCustom } from "@refinedev/core";
import type {
  CreateStrategyPayload,
  CreateBacktestPayload,
  CreateOptimizationPayload,
  StrategyWithMetrics,
  BacktestJob,
  OptimizationRun,
} from "@providers";
import {
  getOptimizationWithIterations,
  controlOptimization,
  getStrategyLineage,
  getQueueStats,
} from "@providers";

// ============================================================================
// Example 1: List Strategies with Filters
// ============================================================================

export function StrategyListExample() {
  const { data, isLoading } = useList<StrategyWithMetrics>({
    resource: "strategies",
    pagination: {
      current: 1,
      pageSize: 20,
    },
    sorters: [
      { field: "sharpe_ratio", order: "desc" }, // Best strategies first
    ],
    filters: [
      { field: "min_sharpe", operator: "gte", value: 1.5 }, // Sharpe >= 1.5
      { field: "min_profit_pct", operator: "gte", value: 10 }, // Profit >= 10%
      { field: "name", operator: "contains", value: "momentum" }, // Name contains "momentum"
    ],
  });

  if (isLoading) return <div>Loading strategies...</div>;

  return (
    <div>
      <h2>Top Strategies</h2>
      <div>Total: {data?.total}</div>
      {data?.data.map((item) => (
        <div key={item.strategy.id}>
          <h3>{item.strategy.name}</h3>
          <p>Sharpe: {item.best_result?.sharpe_ratio.toFixed(2)}</p>
          <p>Profit: {item.best_result?.profit_pct.toFixed(2)}%</p>
          <p>Backtests: {item.backtest_count}</p>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Example 2: Get Strategy Details
// ============================================================================

export function StrategyDetailExample({ id }: { id: string }) {
  const { data, isLoading } = useOne({
    resource: "strategies",
    id,
  });

  if (isLoading) return <div>Loading strategy...</div>;

  const strategy = data?.data;

  return (
    <div>
      <h1>{strategy?.name}</h1>
      <p>{strategy?.description}</p>
      <div>
        <h3>Metadata</h3>
        <pre>{JSON.stringify(strategy?.metadata, null, 2)}</pre>
      </div>
      <div>
        <h3>Tags</h3>
        <div>Type: {strategy?.tags.strategy_type.join(", ")}</div>
        <div>Risk: {strategy?.tags.risk_level}</div>
        <div>Style: {strategy?.tags.trading_style}</div>
      </div>
      <div>
        <h3>Code</h3>
        <pre>{strategy?.code}</pre>
      </div>
    </div>
  );
}

// ============================================================================
// Example 3: Create Strategy
// ============================================================================

export function CreateStrategyExample() {
  const { mutate, isLoading } = useCreate();

  const handleCreate = () => {
    const payload: CreateStrategyPayload = {
      name: "RSI Momentum Strategy",
      code: `
# RSI Momentum Strategy
class RSIMomentumStrategy(IStrategy):
    def populate_indicators(self, dataframe, metadata):
        dataframe['rsi'] = ta.RSI(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        dataframe.loc[
            (dataframe['rsi'] < 30),
            'enter_long'] = 1
        return dataframe
      `,
      description: "Simple RSI-based momentum strategy for testing",
      tags: {
        strategy_type: ["momentum", "mean_reversion"],
        risk_level: "medium",
        trading_style: "intraday",
        indicators: ["RSI"],
        market_regime: ["ranging"],
      },
    };

    mutate(
      {
        resource: "strategies",
        values: payload,
      },
      {
        onSuccess: (data) => {
          console.log("Strategy created:", data.data);
        },
        onError: (error) => {
          console.error("Failed to create strategy:", error);
        },
      }
    );
  };

  return (
    <button onClick={handleCreate} disabled={isLoading}>
      {isLoading ? "Creating..." : "Create Strategy"}
    </button>
  );
}

// ============================================================================
// Example 4: List Backtests
// ============================================================================

export function BacktestListExample() {
  const { data, isLoading } = useList<BacktestJob>({
    resource: "backtests",
    pagination: { current: 1, pageSize: 10 },
    sorters: [{ field: "created_at", order: "desc" }],
    filters: [
      { field: "status", operator: "in", value: ["JOB_STATUS_RUNNING", "JOB_STATUS_PENDING"] },
    ],
  });

  if (isLoading) return <div>Loading backtests...</div>;

  return (
    <div>
      <h2>Active Backtests</h2>
      {data?.data.map((job) => (
        <div key={job.id}>
          <div>Job ID: {job.id}</div>
          <div>Status: {job.status}</div>
          <div>Priority: {job.priority}</div>
          <div>Created: {new Date(job.created_at).toLocaleString()}</div>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Example 5: Submit Backtest
// ============================================================================

export function SubmitBacktestExample({ strategyId }: { strategyId: string }) {
  const { mutate, isLoading } = useCreate();

  const handleSubmit = () => {
    const payload: CreateBacktestPayload = {
      strategy_id: strategyId,
      config: {
        exchange: "binance",
        pairs: ["BTC/USDT", "ETH/USDT"],
        timeframe: "5m",
        timerange_start: "20240101",
        timerange_end: "20240201",
        dry_run_wallet: 10000,
        max_open_trades: 3,
        stake_amount: "unlimited",
      },
      priority: 5,
    };

    mutate(
      {
        resource: "backtests",
        values: payload,
      },
      {
        onSuccess: (data) => {
          console.log("Backtest submitted:", data.data);
        },
      }
    );
  };

  return (
    <button onClick={handleSubmit} disabled={isLoading}>
      {isLoading ? "Submitting..." : "Submit Backtest"}
    </button>
  );
}

// ============================================================================
// Example 6: Cancel Backtest
// ============================================================================

export function CancelBacktestExample({ id }: { id: string }) {
  const { mutate, isLoading } = useDelete();

  const handleCancel = () => {
    mutate(
      {
        resource: "backtests",
        id,
      },
      {
        onSuccess: () => {
          console.log("Backtest cancelled");
        },
      }
    );
  };

  return (
    <button onClick={handleCancel} disabled={isLoading}>
      {isLoading ? "Cancelling..." : "Cancel Backtest"}
    </button>
  );
}

// ============================================================================
// Example 7: List Optimizations
// ============================================================================

export function OptimizationListExample() {
  const { data, isLoading } = useList<OptimizationRun>({
    resource: "optimizations",
    pagination: { current: 1, pageSize: 10 },
    sorters: [{ field: "created_at", order: "desc" }],
    filters: [
      { field: "status", operator: "eq", value: "OPTIMIZATION_STATUS_RUNNING" },
    ],
  });

  if (isLoading) return <div>Loading optimizations...</div>;

  return (
    <div>
      <h2>Running Optimizations</h2>
      {data?.data.map((run) => (
        <div key={run.id}>
          <h3>{run.name}</h3>
          <div>Status: {run.status}</div>
          <div>Iteration: {run.current_iteration} / {run.max_iterations}</div>
          {run.best_result && (
            <div>Best Sharpe: {run.best_result.sharpe_ratio.toFixed(2)}</div>
          )}
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Example 8: Create Optimization
// ============================================================================

export function CreateOptimizationExample({ strategyId }: { strategyId: string }) {
  const { mutate, isLoading } = useCreate();

  const handleCreate = () => {
    const payload: CreateOptimizationPayload = {
      name: "RSI Parameter Optimization",
      base_strategy_id: strategyId,
      config: {
        backtest_config: {
          exchange: "binance",
          pairs: ["BTC/USDT"],
          timeframe: "5m",
          timerange_start: "20240101",
          timerange_end: "20240201",
          dry_run_wallet: 10000,
          max_open_trades: 3,
          stake_amount: "unlimited",
        },
        max_iterations: 20,
        criteria: {
          min_sharpe: 1.5,
          min_profit_pct: 10,
          max_drawdown_pct: 20,
          min_trades: 50,
          min_win_rate: 0.45,
        },
        mode: "OPTIMIZATION_MODE_MAXIMIZE_SHARPE",
      },
    };

    mutate(
      {
        resource: "optimizations",
        values: payload,
      },
      {
        onSuccess: (data) => {
          console.log("Optimization started:", data.data);
        },
      }
    );
  };

  return (
    <button onClick={handleCreate} disabled={isLoading}>
      {isLoading ? "Starting..." : "Start Optimization"}
    </button>
  );
}

// ============================================================================
// Example 9: Control Optimization (using helper)
// ============================================================================

export function ControlOptimizationExample({ id }: { id: string }) {
  const handlePause = async () => {
    const run = await controlOptimization(id, "OPTIMIZATION_ACTION_PAUSE");
    console.log("Optimization paused:", run);
  };

  const handleResume = async () => {
    const run = await controlOptimization(id, "OPTIMIZATION_ACTION_RESUME");
    console.log("Optimization resumed:", run);
  };

  const handleCancel = async () => {
    const run = await controlOptimization(id, "OPTIMIZATION_ACTION_CANCEL");
    console.log("Optimization cancelled:", run);
  };

  return (
    <div>
      <button onClick={handlePause}>Pause</button>
      <button onClick={handleResume}>Resume</button>
      <button onClick={handleCancel}>Cancel</button>
    </div>
  );
}

// ============================================================================
// Example 10: Get Optimization with Iterations (using helper)
// ============================================================================

export function OptimizationDetailExample({ id }: { id: string }) {
  const [data, setData] = React.useState<{
    run: OptimizationRun;
    iterations: any[];
  } | null>(null);

  React.useEffect(() => {
    getOptimizationWithIterations(id).then(setData);
  }, [id]);

  if (!data) return <div>Loading...</div>;

  return (
    <div>
      <h2>{data.run.name}</h2>
      <div>Status: {data.run.status}</div>
      <div>Current Iteration: {data.run.current_iteration}</div>
      <div>
        <h3>Iterations</h3>
        {data.iterations.map((iter) => (
          <div key={iter.iteration_number}>
            <div>Iteration {iter.iteration_number}</div>
            <div>Approval: {iter.approval}</div>
            {iter.result && (
              <div>Sharpe: {iter.result.sharpe_ratio.toFixed(2)}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Example 11: Get Queue Statistics (using helper)
// ============================================================================

export function QueueStatsExample() {
  const [stats, setStats] = React.useState<any>(null);

  React.useEffect(() => {
    const fetchStats = async () => {
      const data = await getQueueStats();
      setStats(data);
    };

    fetchStats();
    const interval = setInterval(fetchStats, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, []);

  if (!stats) return <div>Loading stats...</div>;

  return (
    <div>
      <h2>Queue Statistics</h2>
      <div>Pending Jobs: {stats.pending_jobs}</div>
      <div>Running Jobs: {stats.running_jobs}</div>
      <div>Completed Today: {stats.completed_today}</div>
      <div>Failed Today: {stats.failed_today}</div>
      <div>Max Concurrent: {stats.max_concurrent}</div>
    </div>
  );
}

// ============================================================================
// Example 12: Get Strategy Lineage (using helper)
// ============================================================================

export function StrategyLineageExample({ id }: { id: string }) {
  const [lineage, setLineage] = React.useState<any>(null);

  React.useEffect(() => {
    getStrategyLineage(id, 5).then(setLineage);
  }, [id]);

  if (!lineage) return <div>Loading lineage...</div>;

  return (
    <div>
      <h2>Strategy Lineage</h2>
      <pre>{JSON.stringify(lineage, null, 2)}</pre>
    </div>
  );
}

// ============================================================================
// Example 13: Custom Endpoint Usage
// ============================================================================

export function CustomEndpointExample() {
  const { data, refetch } = useCustom({
    url: "/backtests/queue/stats",
    method: "get",
  });

  return (
    <div>
      <h2>Custom Endpoint</h2>
      <button onClick={() => refetch()}>Refresh</button>
      <pre>{JSON.stringify(data?.data, null, 2)}</pre>
    </div>
  );
}

// Add React import
import React from "react";
