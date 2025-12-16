# Dashboard Code Examples

Quick reference for common patterns used in the dashboard components.

## 1. Data Fetching with Refine

### Using useCustom for Custom Endpoints

```typescript
import { useCustom } from '@refinedev/core';
import { QueueStats } from '../../types/api';

const { data, isLoading, refetch } = useCustom<QueueStats>({
  url: '/backtests/queue/stats',
  method: 'get',
});

// Access data
const stats = data?.data;
```

### Using useList with Filters

```typescript
import { useList } from '@refinedev/core';
import { OptimizationRun } from '../../types/api';

const { data, isLoading } = useList<OptimizationRun>({
  resource: 'optimizations',
  filters: [
    {
      field: 'status',
      operator: 'eq',
      value: 'running',
    },
  ],
  pagination: {
    pageSize: 10,
  },
  liveMode: 'auto', // Enable real-time updates
});

const optimizations = data?.data || [];
```

### Using useCustom with Query Parameters

```typescript
const { data } = useCustom<PerformanceDataPoint[]>({
  url: '/optimizations/performance',
  method: 'get',
  config: {
    query: {
      period: '24h',
      limit: 100,
    },
  },
});
```

## 2. Tremor Components

### Card with Metric

```typescript
import { Card, Metric, Text } from '@tremor/react';

<Card decoration="top" decorationColor="blue">
  <Text>Pending Jobs</Text>
  <Metric className="mt-2">12</Metric>
</Card>
```

### Progress Bar

```typescript
import { ProgressBar, Flex, Text } from '@tremor/react';

const progress = (current / total) * 100;

<div>
  <Flex justifyContent="between" className="mb-1">
    <Text>Iteration: {current}/{total}</Text>
    <Text className="text-gray-500">{Math.round(progress)}%</Text>
  </Flex>
  <ProgressBar value={progress} color="emerald" />
</div>
```

### Status Badges

```typescript
import { Badge } from '@tremor/react';

// Status-based color
const getStatusColor = (status: string) => {
  switch (status) {
    case 'active': return 'emerald';
    case 'idle': return 'yellow';
    case 'offline': return 'gray';
    default: return 'blue';
  }
};

<Badge color={getStatusColor(status)} size="sm">
  {status}
</Badge>
```

### Flex Layout

```typescript
import { Flex } from '@tremor/react';

<Flex alignItems="center" justifyContent="between">
  <div>Left content</div>
  <div>Right content</div>
</Flex>
```

## 3. Ant Design Components

### Responsive Grid

```typescript
import { Row, Col } from 'antd';

<Row gutter={[16, 16]}>
  <Col xs={24} sm={12} lg={6}>
    {/* Full width mobile, half width tablet, quarter desktop */}
  </Col>
  <Col xs={24} lg={16}>
    {/* Full width mobile, 2/3 width desktop */}
  </Col>
  <Col xs={24} lg={8}>
    {/* Full width mobile, 1/3 width desktop */}
  </Col>
</Row>
```

### Buttons with Icons

```typescript
import { Button, Tooltip } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons';

<Tooltip title="Pause">
  <Button
    type="text"
    icon={<PauseCircleOutlined />}
    onClick={handlePause}
    loading={loading}
    size="small"
  />
</Tooltip>
```

### Space for Vertical/Horizontal Layouts

```typescript
import { Space } from 'antd';

// Vertical spacing
<Space direction="vertical" size="large" style={{ width: '100%' }}>
  <Component1 />
  <Component2 />
</Space>

// Horizontal spacing
<Space size="small">
  <Button>Action 1</Button>
  <Button>Action 2</Button>
</Space>
```

## 4. Recharts Implementation

### Area Chart with Gradient

```typescript
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

<ResponsiveContainer width="100%" height={320}>
  <AreaChart data={chartData}>
    <defs>
      <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
      </linearGradient>
    </defs>
    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
    <XAxis dataKey="timestamp" stroke="#6b7280" />
    <YAxis stroke="#6b7280" />
    <Tooltip content={<CustomTooltip />} />
    <Area
      type="monotone"
      dataKey="value"
      stroke="#3b82f6"
      fillOpacity={1}
      fill="url(#colorValue)"
    />
  </AreaChart>
</ResponsiveContainer>
```

### Custom Tooltip

```typescript
const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 border border-gray-200 rounded shadow-lg">
        <p className="text-sm font-medium">{payload[0].payload.label}</p>
        <p className="text-sm" style={{ color: payload[0].color }}>
          Value: {payload[0].value.toFixed(2)}
        </p>
      </div>
    );
  }
  return null;
};
```

## 5. TypeScript Patterns

### Component Props Interface

```typescript
import { OptimizationRun } from '../../types/api';

interface OptimizationCardProps {
  optimization: OptimizationRun;
  onPause?: (id: string) => void;
  onResume?: (id: string) => void;
  onCancel?: (id: string) => void;
  loading?: boolean;
}

export const OptimizationCard: React.FC<OptimizationCardProps> = ({
  optimization,
  onPause,
  onResume,
  onCancel,
  loading = false,
}) => {
  // Component implementation
};
```

### Type Guards

```typescript
const getStatusColor = (
  status: 'active' | 'idle' | 'offline'
): 'emerald' | 'yellow' | 'gray' => {
  switch (status) {
    case 'active':
      return 'emerald';
    case 'idle':
      return 'yellow';
    case 'offline':
      return 'gray';
  }
};
```

### Optional Chaining for Safe Data Access

```typescript
// Safe access to nested properties
const stats = queueStatsData?.data;
const optimizations = optimizationsData?.data || [];
const bestSharpe = optimization?.best_sharpe_ratio ?? 0;
```

## 6. Loading States

### Skeleton Loaders

```typescript
if (loading) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      {[1, 2, 3, 4].map((i) => (
        <Card key={i} className="animate-pulse">
          <Flex alignItems="start">
            <div className="h-4 w-24 rounded bg-gray-200" />
          </Flex>
          <Flex className="mt-4">
            <div className="h-8 w-16 rounded bg-gray-200" />
          </Flex>
        </Card>
      ))}
    </div>
  );
}
```

### Conditional Rendering

```typescript
{loading ? (
  <SkeletonComponent />
) : data.length > 0 ? (
  <DataComponent data={data} />
) : (
  <EmptyState />
)}
```

## 7. Empty States

### With SVG Icon

```typescript
<div className="p-8 text-center bg-gray-50 rounded border-2 border-dashed border-gray-200">
  <svg
    className="mx-auto h-12 w-12 text-gray-400"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
    />
  </svg>
  <p className="mt-2 text-gray-600">No active optimizations</p>
  <p className="text-sm text-gray-500">
    Start a new optimization to see progress here
  </p>
</div>
```

## 8. Utility Functions

### Date Formatting

```typescript
const formatLastSeen = (lastSeen?: string): string => {
  if (!lastSeen) return '';

  const date = new Date(lastSeen);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  return `${Math.floor(hours / 24)}d ago`;
};
```

### Number Formatting

```typescript
const formatSharpeRatio = (ratio: number): string => {
  return ratio.toFixed(2);
};

const formatPercentage = (current: number, total: number): number => {
  return Math.round((current / total) * 100);
};
```

### String Capitalization

```typescript
const formatAgentName = (type: string): string => {
  return type.charAt(0).toUpperCase() + type.slice(1);
};
```

## 9. Event Handlers

### Async Handlers with TODO

```typescript
const handlePause = async (id: string) => {
  console.log('Pausing optimization:', id);

  // TODO: Implement with useUpdate hook
  // try {
  //   await update({
  //     resource: 'optimizations',
  //     id,
  //     values: { action: 'pause' },
  //   });
  // } catch (error) {
  //   console.error('Failed to pause optimization:', error);
  // }
};
```

### With Loading State

```typescript
const [actionLoading, setActionLoading] = useState(false);

const handleAction = async (id: string) => {
  setActionLoading(true);
  try {
    await performAction(id);
  } catch (error) {
    console.error('Action failed:', error);
  } finally {
    setActionLoading(false);
  }
};
```

## 10. Tailwind CSS Patterns

### Grid Layouts

```typescript
// Responsive grid
<div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">

// Space between items
<div className="space-y-4">
<div className="space-x-2">

// Centered content
<div className="flex items-center justify-center">
```

### Typography

```typescript
// Headings
<h2 className="text-2xl font-semibold text-gray-900">
<h4 className="text-lg font-medium text-gray-800">

// Body text
<p className="text-gray-600">
<span className="text-sm text-gray-500">

// Truncate
<p className="truncate max-w-[200px]">
```

### Hover Effects

```typescript
<div className="hover:bg-gray-50 transition-colors">
<div className="hover:shadow-md transition-shadow">
<button className="hover:text-blue-600">
```

### Backgrounds and Borders

```typescript
<div className="bg-gray-50 rounded p-3">
<div className="border border-gray-200 rounded-lg">
<div className="border-2 border-dashed border-gray-200">
```

## 11. Real-time Updates

### WebSocket Integration (Future)

```typescript
// In liveProvider configuration
const liveProvider = {
  subscribe: ({ channel, types, params, callback }) => {
    const ws = new WebSocket('ws://localhost:8080/api/v1/ws/events');

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (types.includes(data.type)) {
        callback({
          channel,
          type: data.type,
          date: new Date(data.timestamp),
          payload: data.payload,
        });
      }
    };

    return ws;
  },
  unsubscribe: (ws) => {
    ws.close();
  },
};
```

### Using liveMode in Components

```typescript
const { data } = useList({
  resource: 'optimizations',
  liveMode: 'auto', // 'auto' | 'manual' | 'off'
});

// Manual refresh
const { refetch } = useCustom({
  url: '/stats',
  method: 'get',
});

// Trigger manual refresh
refetch();
```

## 12. Component Composition

### Reusable Patterns

```typescript
// Higher-order component for loading states
const withLoading = <P extends object>(
  Component: React.ComponentType<P>,
  LoadingComponent: React.ComponentType
) => {
  return ({ loading, ...props }: P & { loading: boolean }) => {
    if (loading) return <LoadingComponent />;
    return <Component {...(props as P)} />;
  };
};

// Usage
const EnhancedOptimizationCard = withLoading(
  OptimizationCard,
  OptimizationCardSkeleton
);
```

## 13. Accessibility

### Keyboard Navigation

```typescript
<div
  role="button"
  tabIndex={0}
  onClick={handleClick}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      handleClick();
    }
  }}
>
  Clickable element
</div>
```

### ARIA Labels

```typescript
<Button
  aria-label="Pause optimization"
  icon={<PauseCircleOutlined />}
  onClick={handlePause}
/>

<div role="status" aria-live="polite">
  {statusMessage}
</div>
```

## 14. Testing Patterns (Future)

### Component Test Structure

```typescript
import { render, screen } from '@testing-library/react';
import { QueueStats } from './QueueStats';

describe('QueueStats', () => {
  it('renders queue statistics correctly', () => {
    const stats = {
      pending: 12,
      running: 3,
      completed: 156,
      failed: 2,
    };

    render(<QueueStats stats={stats} />);

    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('Pending Jobs')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(<QueueStats loading />);
    expect(screen.getAllByRole('status')).toHaveLength(4);
  });
});
```

## 15. Performance Optimization

### Memoization

```typescript
import { useMemo, useCallback } from 'react';

// Memoize expensive calculations
const chartData = useMemo(() => {
  return data.map(point => ({
    x: point.timestamp,
    y: point.value,
  }));
}, [data]);

// Memoize callbacks
const handleClick = useCallback((id: string) => {
  console.log('Clicked:', id);
}, []);
```

### Lazy Loading

```typescript
import { lazy, Suspense } from 'react';

const PerformanceChart = lazy(() => import('./PerformanceChart'));

<Suspense fallback={<ChartSkeleton />}>
  <PerformanceChart data={data} />
</Suspense>
```

---

These patterns are used throughout the dashboard implementation and can be reused for other components in the application.
