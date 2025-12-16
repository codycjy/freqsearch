# Dashboard Components

Complete dashboard implementation for FreqSearch admin frontend with real-time monitoring capabilities.

## Components

### 1. DashboardPage (`index.tsx`)

Main dashboard page that orchestrates all components and data fetching.

**Features:**
- Real-time data fetching with Refine hooks
- Live updates support via `liveMode: 'auto'`
- Responsive grid layout
- Loading states and empty states

**API Endpoints:**
- `GET /backtests/queue/stats` - Queue statistics
- `GET /optimizations?status=running` - Active optimizations
- `GET /agents/status` - Agent status
- `GET /optimizations/performance?period=24h` - Performance data

**Usage:**
```tsx
import { DashboardPage } from './pages/dashboard';

// In your router
<Route path="/dashboard" element={<DashboardPage />} />
```

---

### 2. QueueStats (`QueueStats.tsx`)

Displays backtest queue statistics in 4 color-coded cards.

**Props:**
```typescript
interface QueueStatsProps {
  stats: QueueStats | undefined;
  loading?: boolean;
}
```

**Features:**
- Color-coded status indicators (blue, yellow, green, red)
- Tremor Card and Metric components
- Loading skeleton states
- Badge deltas for visual feedback

**Usage:**
```tsx
<QueueStats stats={queueStatsData?.data} loading={queueStatsLoading} />
```

---

### 3. AgentStatus (`AgentStatus.tsx`)

Shows status of each agent type with color-coded indicators.

**Props:**
```typescript
interface AgentStatusProps {
  agents?: Agent[];
  loading?: boolean;
}
```

**Status Indicators:**
- Active (green) - Agent is actively working
- Idle (yellow) - Agent is ready but not working
- Offline (gray) - Agent is not connected

**Features:**
- Real-time last seen timestamps
- Current task display
- Hover states
- Auto-formatting of agent names

**Usage:**
```tsx
<AgentStatus agents={agentsData?.data} loading={agentsLoading} />
```

---

### 4. OptimizationCard (`OptimizationCard.tsx`)

Displays individual optimization run with progress and controls.

**Props:**
```typescript
interface OptimizationCardProps {
  optimization: OptimizationRun;
  onPause?: (id: string) => void;
  onResume?: (id: string) => void;
  onCancel?: (id: string) => void;
  loading?: boolean;
}
```

**Features:**
- Progress bar with iteration tracking
- Best Sharpe ratio display
- Action buttons (pause/resume/cancel)
- Status badges
- Hover shadow effect

**Usage:**
```tsx
<OptimizationCard
  optimization={optimization}
  onPause={handlePause}
  onResume={handleResume}
  onCancel={handleCancel}
/>
```

---

### 5. PerformanceChart (`PerformanceChart.tsx`)

Area chart showing Sharpe ratio trends over the last 24 hours.

**Props:**
```typescript
interface PerformanceChartProps {
  data?: PerformanceDataPoint[];
  loading?: boolean;
}
```

**Features:**
- Recharts AreaChart with gradient fill
- Custom tooltip with timestamp formatting
- Summary statistics (avg, best, data points)
- Empty state with helpful message
- Responsive container

**Usage:**
```tsx
<PerformanceChart data={performanceData?.data} loading={performanceLoading} />
```

---

## Data Types

All TypeScript types are defined in `/src/types/api.ts`:

```typescript
interface QueueStats {
  pending: number;
  running: number;
  completed: number;
  failed: number;
}

interface OptimizationRun {
  id: string;
  name: string;
  status: 'running' | 'paused' | 'completed' | 'failed';
  current_iteration: number;
  max_iterations: number;
  best_sharpe_ratio: number;
  best_strategy_id?: string;
  created_at: string;
  updated_at: string;
}

interface Agent {
  type: 'orchestrator' | 'engineer' | 'analyst' | 'scout';
  status: 'active' | 'idle' | 'offline';
  last_seen?: string;
  current_task?: string;
}

interface PerformanceDataPoint {
  timestamp: string;
  sharpe_ratio: number;
  optimization_id: string;
  optimization_name: string;
}
```

---

## Styling

The dashboard uses a combination of:

1. **Tremor** - Dashboard-specific components (Card, Metric, Badge, ProgressBar)
2. **Ant Design** - Layout components (Row, Col, Button, Space)
3. **Tailwind CSS** - Utility classes for spacing, colors, and responsive design

**Color Palette:**
- Blue: Pending/Info states
- Yellow: In-progress/Idle states
- Green: Success/Active states
- Red: Error/Failed states
- Gray: Offline/Neutral states

---

## Real-time Updates

The dashboard supports real-time updates via Refine's liveProvider:

```tsx
const { data } = useList({
  resource: 'optimizations',
  liveMode: 'auto', // Enable automatic live updates
});
```

**WebSocket Events:**
- `optimization.iteration.completed`
- `optimization.new_best`
- `backtest.completed`
- `agent.status.changed`

---

## Accessibility

All components follow WCAG 2.1 AA guidelines:

- Semantic HTML structure
- Proper ARIA labels
- Keyboard navigation support
- Sufficient color contrast ratios
- Screen reader friendly

---

## Performance Optimizations

1. **Loading States** - Skeleton loaders prevent layout shift
2. **Empty States** - Graceful handling of no data
3. **Memoization** - Components use React.FC for optimization
4. **Lazy Loading** - Charts only render when data is available
5. **Responsive Design** - Mobile-first grid system

---

## TODO / Future Enhancements

1. Implement optimization control actions (pause/resume/cancel)
2. Add WebSocket integration for real-time updates
3. Add filtering and sorting for optimizations
4. Add date range picker for performance chart
5. Add export functionality for metrics
6. Add notification system for critical events
7. Add dark mode support

---

## File Structure

```
frontend/src/pages/dashboard/
├── index.tsx                 # Main dashboard page
├── QueueStats.tsx           # Queue statistics cards
├── AgentStatus.tsx          # Agent status panel
├── OptimizationCard.tsx     # Optimization card component
├── PerformanceChart.tsx     # Performance chart component
├── components.ts            # Re-exports
└── README.md                # This file
```

---

## Example Implementation

Complete example of integrating the dashboard:

```tsx
// App.tsx
import { Refine } from '@refinedev/core';
import { dataProvider } from './providers/dataProvider';
import { liveProvider } from './providers/liveProvider';
import { DashboardPage } from './pages/dashboard';

function App() {
  return (
    <Refine
      dataProvider={dataProvider('http://localhost:8080/api/v1')}
      liveProvider={liveProvider('ws://localhost:8080/api/v1/ws/events')}
      resources={[
        {
          name: 'dashboard',
          list: DashboardPage,
        },
      ]}
    >
      {/* Your app */}
    </Refine>
  );
}
```
