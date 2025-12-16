# Live Provider Integration Guide

This guide shows how to integrate the WebSocket live provider into your FreqSearch Refine application.

## Step 1: Configure Environment

Add the WebSocket URL to your `.env` file:

```env
VITE_API_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/api/v1/ws/events
```

## Step 2: Update Refine Configuration

Modify your `App.tsx` to include the live provider:

```tsx
import { Refine } from "@refinedev/core";
import { RefineThemes, ThemedLayoutV2 } from "@refinedev/antd";
import { ConfigProvider } from "antd";
import routerProvider from "@refinedev/react-router-v6";
import { BrowserRouter, Routes, Route } from "react-router-dom";

// Import providers
import { dataProvider, liveProvider } from "@providers";

// Import your pages
import {
  OptimizationList,
  OptimizationShow,
  BacktestList,
  BacktestShow,
  StrategyList,
  StrategyShow,
} from "@pages";

function App() {
  return (
    <BrowserRouter>
      <ConfigProvider theme={RefineThemes.Blue}>
        <Refine
          // Data provider for REST API
          dataProvider={dataProvider}

          // Live provider for WebSocket updates
          liveProvider={liveProvider}

          // Live mode: "auto" | "manual" | "off"
          // "auto": Automatically subscribe to resources when using hooks
          // "manual": Only subscribe when explicitly requested
          liveMode="auto"

          // Router provider
          routerProvider={routerProvider}

          // Resource configuration
          resources={[
            {
              name: "optimizations",
              list: "/optimizations",
              show: "/optimizations/:id",
              create: "/optimizations/create",
            },
            {
              name: "backtests",
              list: "/backtests",
              show: "/backtests/:id",
              create: "/backtests/create",
            },
            {
              name: "strategies",
              list: "/strategies",
              show: "/strategies/:id",
              create: "/strategies/create",
            },
            {
              name: "agents",
              list: "/agents",
              show: "/agents/:id",
            },
          ]}
        >
          <Routes>
            <Route
              element={
                <ThemedLayoutV2>
                  <Outlet />
                </ThemedLayoutV2>
              }
            >
              <Route path="/optimizations">
                <Route index element={<OptimizationList />} />
                <Route path=":id" element={<OptimizationShow />} />
              </Route>
              <Route path="/backtests">
                <Route index element={<BacktestList />} />
                <Route path=":id" element={<BacktestShow />} />
              </Route>
              <Route path="/strategies">
                <Route index element={<StrategyList />} />
                <Route path=":id" element={<StrategyShow />} />
              </Route>
            </Route>
          </Routes>
        </Refine>
      </ConfigProvider>
    </BrowserRouter>
  );
}

export default App;
```

## Step 3: Use in Components

### Option A: Automatic Updates (Recommended)

When `liveMode="auto"`, resources are automatically subscribed when using hooks:

```tsx
import { useOne, useList } from "@refinedev/core";

function OptimizationShow({ id }: { id: string }) {
  // Automatically subscribes to "optimizations" resource
  // Will refetch when updates are received
  const { data, isLoading } = useOne({
    resource: "optimizations",
    id,
    // Optional: configure live updates
    liveMode: "auto", // or "manual" or "off"
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      <h1>Optimization {data?.data.id}</h1>
      <p>Status: {data?.data.status}</p>
      <p>Iteration: {data?.data.current_iteration}</p>
    </div>
  );
}
```

### Option B: Manual Subscription with Custom Handlers

For more control, use the `useLiveUpdates` hook:

```tsx
import { useOne } from "@refinedev/core";
import { useLiveUpdates } from "@providers";
import { notification } from "antd";

function OptimizationShow({ id }: { id: string }) {
  const { data, isLoading } = useOne({
    resource: "optimizations",
    id,
    liveMode: "off", // Disable automatic subscription
  });

  // Manual subscription with custom event handling
  useLiveUpdates({
    resource: "optimizations",
    ids: [id],
    types: ["updated"],
    onEvent: (event) => {
      // Custom logic before/after refetch
      console.log("Optimization updated:", event.payload);

      // Show notification
      notification.info({
        message: "Optimization Updated",
        description: `Iteration ${event.payload.iteration} completed`,
      });
    },
  });

  // ... render component
}
```

### Option C: Specialized Hooks

Use resource-specific hooks for typed event handlers:

```tsx
import { useOptimizationUpdates } from "@providers";
import { notification, Progress } from "antd";
import { useState } from "react";

function OptimizationProgress({ id }: { id: string }) {
  const [progress, setProgress] = useState(0);

  useOptimizationUpdates({
    ids: [id],
    onIterationComplete: (data) => {
      const iteration = data.iteration as number;
      const total = data.total_iterations as number;
      setProgress((iteration / total) * 100);
    },
    onNewBest: (data) => {
      notification.success({
        message: "New Best Found!",
        description: `Sharpe: ${data.sharpe_ratio}`,
      });
    },
    onComplete: () => {
      notification.success({
        message: "Optimization Complete!",
      });
    },
    onFailed: (data) => {
      notification.error({
        message: "Optimization Failed",
        description: data.error as string,
      });
    },
  });

  return <Progress percent={progress} />;
}
```

## Step 4: List Pages with Real-time Updates

Enable live updates for list pages:

```tsx
import { useList } from "@refinedev/core";
import { useLiveUpdates } from "@providers";
import { Table } from "antd";

function OptimizationList() {
  const { data, isLoading } = useList({
    resource: "optimizations",
    pagination: { current: 1, pageSize: 10 },
    liveMode: "auto", // Auto-refetch on updates
  });

  // Optional: Custom handling for new optimizations
  useLiveUpdates({
    resource: "optimizations",
    types: ["created"],
    onEvent: (event) => {
      if (event.type === "created") {
        notification.info({
          message: "New Optimization Started",
        });
      }
    },
    autoInvalidate: false, // Already handled by liveMode="auto"
  });

  return (
    <Table
      dataSource={data?.data}
      loading={isLoading}
      // ... columns configuration
    />
  );
}
```

## Step 5: Dashboard with Multiple Resources

Monitor multiple resources simultaneously:

```tsx
import { useLiveUpdates } from "@providers";
import { Card, Statistic, Row, Col } from "antd";
import { useState } from "react";

function Dashboard() {
  const [optimizationCount, setOptimizationCount] = useState(0);
  const [backtestCount, setBacktestCount] = useState(0);

  // Monitor optimizations
  useLiveUpdates({
    resource: "optimizations",
    types: ["created"],
    onEvent: () => {
      setOptimizationCount((count) => count + 1);
    },
  });

  // Monitor backtests
  useLiveUpdates({
    resource: "backtests",
    types: ["created"],
    onEvent: () => {
      setBacktestCount((count) => count + 1);
    },
  });

  return (
    <Row gutter={16}>
      <Col span={12}>
        <Card>
          <Statistic title="New Optimizations" value={optimizationCount} />
        </Card>
      </Col>
      <Col span={12}>
        <Card>
          <Statistic title="New Backtests" value={backtestCount} />
        </Card>
      </Col>
    </Row>
  );
}
```

## Step 6: Conditional Subscriptions

Enable/disable subscriptions based on user interaction:

```tsx
import { useLiveUpdates } from "@providers";
import { Switch } from "antd";
import { useState } from "react";

function OptimizationMonitor({ id }: { id: string }) {
  const [isMonitoring, setIsMonitoring] = useState(false);

  useLiveUpdates({
    resource: "optimizations",
    ids: [id],
    enabled: isMonitoring, // Only subscribe when enabled
    onEvent: (event) => {
      console.log("Event received:", event);
    },
  });

  return (
    <div>
      <Switch
        checked={isMonitoring}
        onChange={setIsMonitoring}
        checkedChildren="Monitoring"
        unCheckedChildren="Paused"
      />
    </div>
  );
}
```

## Step 7: Custom Live Provider Configuration

Create a custom live provider with different settings:

```tsx
import { createLiveProvider } from "@providers";

// Production configuration
const productionLiveProvider = createLiveProvider({
  wsUrl: import.meta.env.VITE_WS_URL,
  reconnectInterval: 2000,
  maxReconnectInterval: 60000,
  pingInterval: 45000,
  debug: false,
});

// Development configuration
const developmentLiveProvider = createLiveProvider({
  wsUrl: "ws://localhost:8080/api/v1/ws/events",
  reconnectInterval: 1000,
  pingInterval: 30000,
  debug: true,
});

// Use in Refine
<Refine
  liveProvider={
    import.meta.env.PROD
      ? productionLiveProvider
      : developmentLiveProvider
  }
  // ...
/>
```

## Best Practices

### 1. Use Appropriate Live Modes

```tsx
// List pages: Auto-update to show new items
<useList liveMode="auto" />

// Detail pages: Manual for custom handling
<useOne liveMode="manual" />

// Static pages: Turn off to save resources
<useOne liveMode="off" />
```

### 2. Debounce High-Frequency Updates

```tsx
useLiveUpdates({
  resource: "optimizations",
  debounceMs: 1000, // Wait 1s before invalidating
});
```

### 3. Scope Subscriptions

```tsx
// Good: Specific IDs
useLiveUpdates({
  resource: "optimizations",
  ids: [currentId],
});

// Avoid: Too broad (unless needed)
useLiveUpdates({
  resource: "optimizations",
  // No IDs = all items
});
```

### 4. Handle Errors

```tsx
import { useOne } from "@refinedev/core";

const { data, isLoading, isError, error } = useOne({
  resource: "optimizations",
  id,
});

if (isError) {
  return <div>Error: {error?.message}</div>;
}
```

### 5. Clean Up Subscriptions

Subscriptions are automatically cleaned up when components unmount:

```tsx
function MyComponent() {
  // Automatically unsubscribes on unmount
  useLiveUpdates({
    resource: "optimizations",
  });

  return <div>Content</div>;
}
```

## Troubleshooting

### Connection Issues

If WebSocket fails to connect:

1. Verify `VITE_WS_URL` in `.env`
2. Check backend WebSocket server is running
3. Check browser console for errors
4. Enable debug mode:

```tsx
const liveProvider = createLiveProvider({
  debug: true,
});
```

### Updates Not Appearing

1. Check `liveMode` is not `"off"`
2. Verify event types match backend events
3. Check resource names match exactly
4. Enable debug logging to see incoming messages

### Performance Issues

1. Reduce subscription scope (use `ids` parameter)
2. Increase `debounceMs`
3. Use `liveMode="manual"` for more control
4. Disable auto-invalidation if not needed:

```tsx
useLiveUpdates({
  resource: "optimizations",
  autoInvalidate: false,
  onEvent: handleEventManually,
});
```

## Testing

### Test WebSocket in Development

```tsx
// Test component
function WebSocketTest() {
  useLiveUpdates({
    resource: "optimizations",
    onEvent: (event) => {
      console.log("Event received:", event);
    },
  });

  return <div>Check console for events</div>;
}
```

### Mock WebSocket in Tests

See `liveProvider.test.ts` for examples of mocking WebSocket connections in unit tests.

## Advanced Usage

### Multiple Live Providers

Use different providers for different purposes:

```tsx
import { createLiveProvider } from "@providers";

const mainLiveProvider = createLiveProvider({
  wsUrl: "ws://localhost:8080/api/v1/ws/events",
});

const metricsLiveProvider = createLiveProvider({
  wsUrl: "ws://localhost:8080/api/v1/ws/metrics",
});

// Use in separate Refine instances or contexts
```

### Custom Event Routing

Extend the live provider for custom event handling:

```tsx
import { createLiveProvider } from "@providers";

const customLiveProvider = createLiveProvider({
  debug: true,
});

// Add custom publish method
customLiveProvider.publish = (event) => {
  console.log("Publishing event:", event);
  // Custom publish logic
};
```

## Complete Example

See the `examples/` directory for complete working examples:

- `OptimizationMonitor.tsx` - Real-time optimization monitoring
- `BacktestTracker.tsx` - Backtest progress tracking with notifications
- `AgentDashboard.tsx` - Multi-resource dashboard

## Next Steps

1. Review the [Live Provider README](./README.md) for detailed API documentation
2. Check the [examples](./examples/) for complete working code
3. Explore the [test file](./liveProvider.test.ts) for testing strategies
4. Read the [TypeScript types](./types.ts) for full type definitions
