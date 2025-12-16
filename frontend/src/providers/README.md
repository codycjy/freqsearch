# FreqSearch Providers

This directory contains the Refine providers for the FreqSearch application, enabling data fetching and real-time updates.

## Components

- **dataProvider.ts** - REST API data provider for CRUD operations
- **liveProvider.ts** - WebSocket-based live provider for real-time updates
- **types.ts** - TypeScript type definitions for API data structures
- **useLiveUpdates.ts** - React hooks for convenient live update subscriptions

---

# FreqSearch Data Provider

A type-safe Refine data provider for the FreqSearch REST API. Handles strategies, backtests, and optimization runs with full TypeScript support.

## Features

- **Complete CRUD Operations**: Full support for all Refine data provider methods
- **Type Safety**: Comprehensive TypeScript types based on proto definitions
- **Smart Filter Mapping**: Automatic conversion of Refine filters to API query params
- **Pagination Support**: 1-indexed pagination matching the API
- **Sorting Support**: Single-column sorting with ascending/descending order
- **Resource Mapping**: Automatic endpoint resolution for all resource types
- **Helper Functions**: Type-safe wrappers for common operations

## API Endpoints

The data provider supports the following resources:

| Resource | Endpoints | Operations |
|----------|-----------|------------|
| `strategies` | `/api/v1/strategies` | list, get, create, delete |
| `backtests` | `/api/v1/backtests` | list, get, create, delete (cancel) |
| `optimizations` | `/api/v1/optimizations` | list, get, create, control |
| `backtest-results` | `/api/v1/backtest-results` | list, get |

## Configuration

Set the API base URL in your `.env` file:

```env
VITE_API_URL=http://localhost:8080
```

The data provider will use this URL for all API requests. If not set, it defaults to `http://localhost:8080`.

## Basic Usage

### Setup in Refine App

```tsx
import { Refine } from "@refinedev/core";
import { dataProvider } from "@providers";

function App() {
  return (
    <Refine
      dataProvider={dataProvider}
      resources={[
        { name: "strategies", list: "/strategies" },
        { name: "backtests", list: "/backtests" },
        { name: "optimizations", list: "/optimizations" },
      ]}
    >
      {/* Your app components */}
    </Refine>
  );
}
```

### List Resources

```tsx
import { useList } from "@refinedev/core";

function StrategyList() {
  const { data, isLoading } = useList({
    resource: "strategies",
    pagination: { current: 1, pageSize: 10 },
    sorters: [{ field: "created_at", order: "desc" }],
    filters: [
      { field: "min_sharpe", operator: "gte", value: 1.5 },
      { field: "name", operator: "contains", value: "momentum" },
    ],
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      {data?.data.map((strategy) => (
        <div key={strategy.id}>{strategy.name}</div>
      ))}
      <div>Total: {data?.total}</div>
    </div>
  );
}
```

### Get Single Resource

```tsx
import { useOne } from "@refinedev/core";

function StrategyDetail({ id }: { id: string }) {
  const { data, isLoading } = useOne({
    resource: "strategies",
    id,
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      <h1>{data?.data.name}</h1>
      <pre>{data?.data.code}</pre>
    </div>
  );
}
```

### Create Resource

```tsx
import { useCreate } from "@refinedev/core";
import type { CreateStrategyPayload } from "@providers";

function CreateStrategy() {
  const { mutate, isLoading } = useCreate();

  const handleCreate = () => {
    const payload: CreateStrategyPayload = {
      name: "My Strategy",
      code: "# Strategy code here",
      description: "A test strategy",
      parent_id: "parent_strategy_id",
    };

    mutate({
      resource: "strategies",
      values: payload,
    });
  };

  return <button onClick={handleCreate}>Create Strategy</button>;
}
```

### Delete Resource

```tsx
import { useDelete } from "@refinedev/core";

function DeleteStrategy({ id }: { id: string }) {
  const { mutate, isLoading } = useDelete();

  const handleDelete = () => {
    mutate({
      resource: "strategies",
      id,
    });
  };

  return <button onClick={handleDelete}>Delete</button>;
}
```

## Advanced Usage

### Filter Operators

The data provider maps Refine filter operators to API query parameters:

| Operator | API Param | Example |
|----------|-----------|---------|
| `eq` | `field=value` | `{ field: "status", operator: "eq", value: "running" }` |
| `gte` | `min_field=value` | `{ field: "sharpe", operator: "gte", value: 1.5 }` |
| `lte` | `max_field=value` | `{ field: "drawdown", operator: "lte", value: 0.2 }` |
| `contains` | `field_pattern=%value%` | `{ field: "name", operator: "contains", value: "trend" }` |
| `startswith` | `field_pattern=value%` | `{ field: "name", operator: "startswith", value: "RSI" }` |
| `in` | `field=val1,val2` | `{ field: "status", operator: "in", value: ["running", "pending"] }` |

### Sorting

```tsx
const { data } = useList({
  resource: "strategies",
  sorters: [
    { field: "sharpe_ratio", order: "desc" }, // Best Sharpe first
  ],
});
```

API receives: `order_by=sharpe_ratio&ascending=false`

### Pagination

```tsx
const { data } = useList({
  resource: "backtests",
  pagination: {
    current: 2,    // Page 2
    pageSize: 20,  // 20 items per page
  },
});
```

API receives: `page=2&page_size=20`

### Custom Operations

For operations not covered by standard CRUD, use the `custom` method:

```tsx
import { useCustom } from "@refinedev/core";

// Get optimization with iterations
function OptimizationDetail({ id }: { id: string }) {
  const { data } = useCustom({
    url: `/api/v1/optimizations/${id}`,
    method: "get",
  });

  return (
    <div>
      <h1>{data?.data.run.name}</h1>
      <p>Iterations: {data?.data.iterations.length}</p>
    </div>
  );
}

// Control optimization
function OptimizationControls({ id }: { id: string }) {
  const { mutate } = useCustom();

  const handlePause = () => {
    mutate({
      url: `/api/v1/optimizations/${id}/control`,
      method: "post",
      values: { action: "OPTIMIZATION_ACTION_PAUSE" },
    });
  };

  return <button onClick={handlePause}>Pause</button>;
}
```

## Helper Functions

The data provider exports type-safe helper functions for common operations:

### Get Optimization with Iterations

```tsx
import { getOptimizationWithIterations } from "@providers";

const { run, iterations } = await getOptimizationWithIterations("opt_123");
console.log(`Current iteration: ${run.current_iteration}`);
console.log(`Total iterations: ${iterations.length}`);
```

### Control Optimization

```tsx
import { controlOptimization } from "@providers";

// Pause optimization
await controlOptimization("opt_123", "OPTIMIZATION_ACTION_PAUSE");

// Resume optimization
await controlOptimization("opt_123", "OPTIMIZATION_ACTION_RESUME");

// Cancel optimization
await controlOptimization("opt_123", "OPTIMIZATION_ACTION_CANCEL");
```

### Get Backtest with Result

```tsx
import { getBacktestWithResult } from "@providers";

const { job, result } = await getBacktestWithResult("bt_123");
console.log(`Status: ${job.status}`);
if (result) {
  console.log(`Sharpe Ratio: ${result.sharpe_ratio}`);
}
```

### Get Strategy Lineage

```tsx
import { getStrategyLineage } from "@providers";

const lineage = await getStrategyLineage("strat_123", 5); // 5 generations deep
console.log("Strategy ancestry:", lineage);
```

### Get Queue Statistics

```tsx
import { getQueueStats } from "@providers";

const stats = await getQueueStats();
console.log(`Pending jobs: ${stats.pending_jobs}`);
console.log(`Running jobs: ${stats.running_jobs}`);
```

## TypeScript Types

All API types are exported from the `types.ts` file:

```tsx
import type {
  Strategy,
  StrategyWithMetrics,
  CreateStrategyPayload,
  BacktestJob,
  BacktestResult,
  CreateBacktestPayload,
  OptimizationRun,
  OptimizationIteration,
  CreateOptimizationPayload,
  ControlOptimizationPayload,
} from "@providers";
```

## Error Handling

The data provider uses axios for HTTP requests and will throw errors for:

- Network errors
- HTTP 4xx/5xx responses
- Invalid resource names

Handle errors using Refine's error handling:

```tsx
import { useCreate } from "@refinedev/core";
import { notification } from "antd";

function CreateStrategy() {
  const { mutate } = useCreate({
    resource: "strategies",
    onSuccess: () => {
      notification.success({ message: "Strategy created!" });
    },
    onError: (error) => {
      notification.error({
        message: "Failed to create strategy",
        description: error.message,
      });
    },
  });

  // ...
}
```

---

# FreqSearch Live Provider

A robust WebSocket-based live provider for Refine that enables real-time updates for optimizations, backtests, and agent status changes.

## Features

- **Auto-reconnection**: Exponential backoff strategy for resilient connections
- **Keep-alive**: Ping/pong mechanism to maintain connection health
- **Event Routing**: Automatic mapping of backend events to Refine resources
- **Type-safe**: Full TypeScript support with comprehensive type definitions
- **Debounced Updates**: Prevents excessive query invalidations
- **React Hooks**: Convenient hooks for common use cases

## Architecture

### WebSocket Events

The backend emits the following event types:

| Event Type | Resource | Description |
|------------|----------|-------------|
| `optimization.iteration.started` | optimizations | New iteration begins |
| `optimization.iteration.completed` | optimizations | Iteration completes |
| `optimization.new_best` | optimizations | New best parameters found |
| `optimization.completed` | optimizations | Optimization run completes |
| `optimization.failed` | optimizations | Optimization run fails |
| `backtest.submitted` | backtests | Backtest submitted |
| `backtest.completed` | backtests | Backtest completes |
| `agent.status.changed` | agents | Agent status changes |

### Message Format

```json
{
  "type": "optimization.iteration.completed",
  "data": {
    "optimization_run_id": "opt_123",
    "iteration": 5,
    "sharpe_ratio": 1.85,
    "parameters": {
      "fast_period": 12,
      "slow_period": 26
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Installation

The live provider is already configured in the project. No additional installation required.

## Basic Usage

### 1. Configure in Refine App

```tsx
import { Refine } from "@refinedev/core";
import { dataProvider, liveProvider } from "@providers";

function App() {
  return (
    <Refine
      dataProvider={dataProvider}
      liveProvider={liveProvider}
      liveMode="auto" // or "manual" or "off"
      // ... other props
    >
      {/* Your app components */}
    </Refine>
  );
}
```

### 2. Use in Components

#### Automatic Updates (Recommended)

Using the `useLiveUpdates` hook for automatic query invalidation:

```tsx
import { useOne } from "@refinedev/core";
import { useLiveUpdates } from "@providers";

function OptimizationDetail({ id }: { id: string }) {
  const { data, isLoading } = useOne({
    resource: "optimizations",
    id,
  });

  // Automatically refetch when optimization updates
  useLiveUpdates({
    resource: "optimizations",
    ids: [id],
    types: ["updated"],
  });

  return <div>Current iteration: {data?.data.current_iteration}</div>;
}
```

#### Custom Event Handlers

Using hooks with custom callbacks:

```tsx
import { useOptimizationUpdates } from "@providers";
import { notification } from "antd";

function OptimizationMonitor({ id }: { id: string }) {
  useOptimizationUpdates({
    ids: [id],
    onIterationComplete: (data) => {
      console.log(`Iteration ${data.iteration} completed`);
      console.log(`Sharpe Ratio: ${data.sharpe_ratio}`);
    },
    onNewBest: (data) => {
      notification.success({
        message: "New Best Found!",
        description: `Sharpe Ratio: ${data.sharpe_ratio}`,
      });
    },
    onComplete: (data) => {
      notification.success({
        message: "Optimization Completed",
        description: `Total iterations: ${data.total_iterations}`,
      });
    },
    onFailed: (data) => {
      notification.error({
        message: "Optimization Failed",
        description: data.error,
      });
    },
  });

  return <div>Monitoring optimization {id}...</div>;
}
```

### 3. Advanced Usage

#### Monitor All Resources

```tsx
import { useLiveUpdates } from "@providers";

function GlobalMonitor() {
  // Monitor all optimizations
  useLiveUpdates({
    resource: "optimizations",
    onEvent: (event) => {
      console.log("Optimization event:", event.type, event.payload);
    },
  });

  // Monitor all backtests
  useLiveUpdates({
    resource: "backtests",
    onEvent: (event) => {
      console.log("Backtest event:", event.type, event.payload);
    },
  });

  return <div>Global monitoring active</div>;
}
```

#### Conditional Subscriptions

```tsx
import { useLiveUpdates } from "@providers";

function ConditionalMonitor({ enabled, id }: { enabled: boolean; id: string }) {
  useLiveUpdates({
    resource: "optimizations",
    ids: [id],
    enabled, // Only subscribe when enabled is true
  });

  return <div>Conditional monitoring</div>;
}
```

#### Custom Debounce

```tsx
import { useLiveUpdates } from "@providers";

function HighFrequencyMonitor({ id }: { id: string }) {
  useLiveUpdates({
    resource: "optimizations",
    ids: [id],
    debounceMs: 1000, // Debounce invalidations by 1 second
  });

  return <div>High-frequency monitoring with debouncing</div>;
}
```

## API Reference

### `createLiveProvider(config?)`

Factory function to create a custom live provider instance.

**Parameters:**
- `config` (optional): Configuration object
  - `wsUrl?: string` - WebSocket URL (default: `VITE_WS_URL` env var)
  - `reconnectInterval?: number` - Initial reconnect delay in ms (default: 1000)
  - `maxReconnectInterval?: number` - Max reconnect delay in ms (default: 30000)
  - `reconnectDecay?: number` - Exponential backoff multiplier (default: 1.5)
  - `pingInterval?: number` - Ping interval in ms (default: 30000)
  - `pongTimeout?: number` - Pong timeout in ms (default: 5000)
  - `debug?: boolean` - Enable debug logging (default: `import.meta.env.DEV`)

**Returns:** `LiveProvider` instance

**Example:**
```tsx
import { createLiveProvider } from "@providers";

const customLiveProvider = createLiveProvider({
  wsUrl: "ws://custom-server:8080/ws",
  reconnectInterval: 2000,
  debug: true,
});
```

### `useLiveUpdates(options)`

Hook for subscribing to live updates with automatic query invalidation.

**Parameters:**
- `options`: Configuration object
  - `resource: string` - Resource name to subscribe to
  - `types?: Array<"created" | "updated" | "deleted" | "*">` - Event types (default: `["*"]`)
  - `ids?: BaseKey[]` - Specific IDs to watch
  - `onEvent?: (event) => void` - Custom event handler
  - `autoInvalidate?: boolean` - Auto-invalidate queries (default: `true`)
  - `enabled?: boolean` - Enable subscription (default: `true`)
  - `debounceMs?: number` - Debounce time in ms (default: 300)

**Example:**
```tsx
useLiveUpdates({
  resource: "optimizations",
  types: ["updated"],
  ids: ["opt_123"],
  onEvent: (event) => {
    console.log(event);
  },
  debounceMs: 500,
});
```

### `useOptimizationUpdates(options)`

Hook for subscribing to optimization-specific events.

**Parameters:**
- `options`: Configuration object
  - `ids?: BaseKey[]` - Specific optimization IDs
  - `enabled?: boolean` - Enable subscription
  - `onIterationStart?: (data) => void`
  - `onIterationComplete?: (data) => void`
  - `onNewBest?: (data) => void`
  - `onComplete?: (data) => void`
  - `onFailed?: (data) => void`

### `useBacktestUpdates(options)`

Hook for subscribing to backtest-specific events.

**Parameters:**
- `options`: Configuration object
  - `ids?: BaseKey[]` - Specific backtest IDs
  - `enabled?: boolean` - Enable subscription
  - `onSubmitted?: (data) => void`
  - `onComplete?: (data) => void`

### `useAgentUpdates(options)`

Hook for subscribing to agent status changes.

**Parameters:**
- `options`: Configuration object
  - `ids?: BaseKey[]` - Specific agent IDs
  - `enabled?: boolean` - Enable subscription
  - `onStatusChange?: (data) => void`

## Environment Variables

Configure the WebSocket URL in your `.env` file:

```env
VITE_WS_URL=ws://localhost:8080/api/v1/ws/events
```

## Connection Management

### Auto-Reconnection

The live provider automatically reconnects on connection loss using exponential backoff:

1. First retry: 1 second
2. Second retry: 1.5 seconds
3. Third retry: 2.25 seconds
4. ... up to 30 seconds (configurable)

### Keep-Alive

The provider sends ping messages every 30 seconds and expects pong responses within 5 seconds. If no pong is received, the connection is closed and reconnected.

### Subscription Management

- WebSocket connects on first subscription
- Connection maintained while subscriptions exist
- Automatic disconnect when no subscriptions remain
- Subscriptions persist across reconnections

## Performance Considerations

### Debouncing

Query invalidations are debounced by default (300ms) to prevent excessive refetches:

```tsx
useLiveUpdates({
  resource: "optimizations",
  debounceMs: 500, // Adjust based on your needs
});
```

### Selective Subscriptions

Subscribe only to what you need:

```tsx
// Good: Specific resource and IDs
useLiveUpdates({
  resource: "optimizations",
  ids: [currentOptimizationId],
  types: ["updated"],
});

// Avoid: Too broad (unless necessary)
useLiveUpdates({
  resource: "optimizations",
  types: ["*"], // All event types
  // No IDs = all items
});
```

### Conditional Subscriptions

Disable subscriptions when not needed:

```tsx
function OptimizationDetail({ id }: { id: string }) {
  const [isMonitoring, setIsMonitoring] = useState(false);

  useLiveUpdates({
    resource: "optimizations",
    ids: [id],
    enabled: isMonitoring, // Only subscribe when monitoring
  });

  return (
    <button onClick={() => setIsMonitoring(!isMonitoring)}>
      {isMonitoring ? "Stop" : "Start"} Monitoring
    </button>
  );
}
```

## Debugging

Enable debug logging in development:

```tsx
const liveProvider = createLiveProvider({
  debug: true, // Logs connection events and messages
});
```

Debug logs include:
- Connection state changes
- Reconnection attempts
- Incoming messages
- Subscription events
- Ping/pong messages

## Error Handling

The live provider handles errors gracefully:

1. **Connection Errors**: Automatic reconnection with exponential backoff
2. **Message Parse Errors**: Logged but don't break the connection
3. **Callback Errors**: Logged but don't affect other subscriptions
4. **Unknown Event Types**: Logged and ignored

## Testing

### Mock WebSocket Server

For testing, you can mock the WebSocket server:

```tsx
// Mock data for testing
const mockWebSocketServer = {
  send: (message: WebSocketMessage) => {
    // Simulate server messages
  },
};

// Use in tests
const testLiveProvider = createLiveProvider({
  wsUrl: "ws://localhost:8080/test",
  debug: true,
});
```

## Best Practices

1. **Use Specific Subscriptions**: Subscribe to specific resources and IDs when possible
2. **Debounce Updates**: Use appropriate debounce times for your use case
3. **Conditional Subscriptions**: Disable subscriptions when not needed
4. **Custom Handlers**: Use `onEvent` for side effects, not data fetching
5. **Error Boundaries**: Wrap components using live updates in error boundaries
6. **Testing**: Test components with and without live updates enabled

## Troubleshooting

### Connection Issues

If the WebSocket fails to connect:

1. Check `VITE_WS_URL` environment variable
2. Verify backend WebSocket server is running
3. Check browser console for connection errors
4. Enable debug mode to see detailed logs

### Updates Not Received

If updates aren't triggering:

1. Verify subscription resource matches backend event
2. Check event types in subscription
3. Enable debug mode to see incoming messages
4. Verify backend is sending events

### Performance Issues

If experiencing performance issues:

1. Increase debounce time
2. Use more specific subscriptions (resource + IDs)
3. Disable auto-invalidation and use custom handlers
4. Monitor subscription count with `getSubscriptionsCount()`

## Examples

See the `examples/` directory for complete working examples:

- `OptimizationMonitor.tsx` - Real-time optimization monitoring
- `BacktestTracker.tsx` - Backtest progress tracking
- `AgentDashboard.tsx` - Agent status dashboard
- `GlobalMonitor.tsx` - System-wide monitoring

## License

MIT
