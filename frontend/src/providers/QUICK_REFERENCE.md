# FreqSearch Data Provider Quick Reference

## Import

```tsx
import { dataProvider } from "@providers";
import type { Strategy, BacktestJob, OptimizationRun } from "@providers";
import {
  getOptimizationWithIterations,
  controlOptimization,
  getBacktestWithResult,
  getStrategyLineage,
  getQueueStats,
} from "@providers";
```

## Resources

- `strategies` - Trading strategies
- `backtests` - Backtest jobs
- `optimizations` - Optimization runs
- `backtest-results` - Backtest results

## Common Operations

### List Resources

```tsx
const { data } = useList({
  resource: "strategies",
  pagination: { current: 1, pageSize: 10 },
  sorters: [{ field: "created_at", order: "desc" }],
  filters: [
    { field: "min_sharpe", operator: "gte", value: 1.5 },
  ],
});
```

### Get Single Resource

```tsx
const { data } = useOne({
  resource: "strategies",
  id: "strat_123",
});
```

### Create Resource

```tsx
const { mutate } = useCreate();
mutate({
  resource: "strategies",
  values: { name: "...", code: "...", description: "..." },
});
```

### Delete Resource

```tsx
const { mutate } = useDelete();
mutate({ resource: "strategies", id: "strat_123" });
```

## Filter Operators

| Operator | Maps To | Example |
|----------|---------|---------|
| `eq` | `field=value` | `{ field: "status", operator: "eq", value: "running" }` |
| `gte` | `min_field=value` | `{ field: "sharpe", operator: "gte", value: 1.5 }` |
| `lte` | `max_field=value` | `{ field: "drawdown", operator: "lte", value: 0.2 }` |
| `contains` | `field_pattern=%value%` | `{ field: "name", operator: "contains", value: "RSI" }` |

## Helper Functions

```tsx
// Get optimization with iterations
const { run, iterations } = await getOptimizationWithIterations("opt_123");

// Control optimization
await controlOptimization("opt_123", "OPTIMIZATION_ACTION_PAUSE");
await controlOptimization("opt_123", "OPTIMIZATION_ACTION_RESUME");
await controlOptimization("opt_123", "OPTIMIZATION_ACTION_CANCEL");

// Get backtest with result
const { job, result } = await getBacktestWithResult("bt_123");

// Get strategy lineage
const lineage = await getStrategyLineage("strat_123", 5);

// Get queue stats
const stats = await getQueueStats();
```

## Custom Endpoints

```tsx
const { data } = useCustom({
  url: "/api/v1/optimizations/opt_123",
  method: "get",
});
```

## Common Filters

### Strategies
- `name_pattern` - Search by name
- `min_sharpe` - Minimum Sharpe ratio
- `min_profit_pct` - Minimum profit %
- `max_drawdown_pct` - Maximum drawdown %
- `min_trades` - Minimum number of trades

### Backtests
- `strategy_id` - Filter by strategy
- `status` - Job status
- `optimization_run_id` - Filter by optimization run

### Optimizations
- `status` - Run status
- `base_strategy_id` - Filter by base strategy

## TypeScript Types

```tsx
// Payloads
CreateStrategyPayload
CreateBacktestPayload
CreateOptimizationPayload
ControlOptimizationPayload

// Entities
Strategy
StrategyWithMetrics
BacktestJob
BacktestResult
OptimizationRun
OptimizationIteration

// Enums
JobStatus
OptimizationStatus
OptimizationMode
OptimizationAction
```

## API Endpoints

| Resource | List | Get | Create | Delete |
|----------|------|-----|--------|--------|
| strategies | GET /api/v1/strategies | GET /api/v1/strategies/:id | POST /api/v1/strategies | DELETE /api/v1/strategies/:id |
| backtests | GET /api/v1/backtests | GET /api/v1/backtests/:id | POST /api/v1/backtests | DELETE /api/v1/backtests/:id |
| optimizations | GET /api/v1/optimizations | GET /api/v1/optimizations/:id | POST /api/v1/optimizations | - |

Special endpoints:
- POST /api/v1/optimizations/:id/control - Control optimization
- GET /api/v1/strategies/:id/lineage - Get strategy lineage
- GET /api/v1/backtests/queue/stats - Get queue statistics

## Environment

```env
VITE_API_URL=http://localhost:8080
```

---

# Live Provider Quick Reference

## Setup

```typescript
// App.tsx
import { liveProvider } from "@providers";

<Refine
  dataProvider={dataProvider}
  liveProvider={liveProvider}
  liveMode="auto"
/>
```

## Basic Usage

### Auto-Updates in List/Detail Pages

```typescript
// Automatically subscribes and refetches on updates
const { data } = useOne({
  resource: "optimizations",
  id,
  liveMode: "auto", // or "manual" or "off"
});
```

### Manual Subscription

```typescript
import { useLiveUpdates } from "@providers";

useLiveUpdates({
  resource: "optimizations",
  ids: [id], // Optional: specific IDs
  types: ["updated"], // Optional: event types
  onEvent: (event) => {
    console.log("Update received:", event);
  },
});
```

### Optimization Updates

```typescript
import { useOptimizationUpdates } from "@providers";

useOptimizationUpdates({
  ids: [optimizationId],
  onIterationComplete: (data) => {
    console.log(`Iteration ${data.iteration} done`);
  },
  onNewBest: (data) => {
    notification.success({
      message: `New best: ${data.sharpe_ratio}`,
    });
  },
  onComplete: () => {
    notification.success({ message: "Optimization complete!" });
  },
});
```

### Backtest Updates

```typescript
import { useBacktestUpdates } from "@providers";

useBacktestUpdates({
  ids: [backtestId],
  onSubmitted: (data) => {
    console.log("Backtest submitted:", data.backtest_id);
  },
  onComplete: (data) => {
    console.log("Sharpe:", data.sharpe_ratio);
  },
});
```

## Configuration

### Environment Variable

```env
VITE_WS_URL=ws://localhost:8080/api/v1/ws/events
```

### Custom Configuration

```typescript
import { createLiveProvider } from "@providers";

const customLiveProvider = createLiveProvider({
  wsUrl: "ws://custom-url:8080/ws",
  reconnectInterval: 2000,
  debug: true,
});
```

## Common Patterns

### Conditional Subscription

```typescript
const [monitoring, setMonitoring] = useState(false);

useLiveUpdates({
  resource: "optimizations",
  enabled: monitoring, // Only subscribe when true
});
```

### Debounced Updates

```typescript
useLiveUpdates({
  resource: "optimizations",
  debounceMs: 1000, // Wait 1s before invalidating
});
```

### Multiple Resources

```typescript
// Monitor optimizations
useLiveUpdates({ resource: "optimizations" });

// Monitor backtests
useLiveUpdates({ resource: "backtests" });
```

## Event Types

| Event | Description |
|-------|-------------|
| `optimization.iteration.started` | Iteration begins |
| `optimization.iteration.completed` | Iteration completes |
| `optimization.new_best` | New best found |
| `optimization.completed` | Run completes |
| `optimization.failed` | Run fails |
| `backtest.submitted` | Backtest queued |
| `backtest.completed` | Backtest finishes |
| `agent.status.changed` | Agent status changes |

## Debugging

```typescript
// Enable debug mode
const liveProvider = createLiveProvider({ debug: true });

// Check state in console
liveProvider.getState();
liveProvider.getSubscriptionsCount();
```
