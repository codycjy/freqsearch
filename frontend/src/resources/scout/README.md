# Scout Resources

This directory contains components related to the Scout agent functionality in FreqSearch.

## Components

### ScoutList

Main list view component for displaying Scout agent runs with real-time updates.

**Features:**
- Real-time status updates via WebSocket live provider
- Status filtering (pending, running, completed, failed, cancelled)
- Trigger type display (manual, scheduled, event)
- Metrics summary (fetched, validated, submitted strategies)
- Duration calculation for running/completed jobs
- Actions: View details, Cancel run
- Manual trigger button with modal

**Status Colors:**
- `pending`: blue
- `running`: orange
- `completed`: green
- `failed`: red
- `cancelled`: default (gray)

**Table Columns:**
1. **ID** - Short ID (8 chars) with copy functionality
2. **Trigger Type** - Manual, Scheduled, or Event with colored tag
3. **Source** - Data source name (e.g., stratninja, github)
4. **Status** - Colored status tag
5. **Metrics Summary** - "Fetched: X | Validated: Y | Submitted: Z"
6. **Created** - Creation timestamp (YYYY-MM-DD HH:mm:ss)
7. **Duration** - Time elapsed or total duration
8. **Actions** - View and Cancel (for pending/running only)

**Usage:**
```tsx
import { ScoutList } from '@resources/scout';

// In your routes
<Route path="/scout-runs" element={<ScoutList />} />
```

**API Endpoints:**
- GET `/api/v1/agents/scout/runs` - List scout runs
- DELETE `/api/v1/agents/scout/runs/:id` - Cancel a run

### TriggerScoutModal

Modal dialog for manually triggering the Scout agent to fetch strategies from external sources.

**Props:**
```typescript
interface TriggerScoutModalProps {
  open: boolean;           // Controls modal visibility
  onClose: () => void;     // Called when modal is closed
  onSuccess?: () => void;  // Optional callback after successful trigger
}
```

**Features:**
- Select data source (stratninja, github, freqai_gym)
- Configure max strategies limit (1-500, default 100)
- Form validation
- Success/error notifications
- Auto-refresh strategy list on success

**Usage Example:**

```tsx
import React, { useState } from 'react';
import { Button } from 'antd';
import { RocketOutlined } from '@ant-design/icons';
import { TriggerScoutModal } from '@resources/scout';

export const MyComponent: React.FC = () => {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <Button
        type="primary"
        icon={<RocketOutlined />}
        onClick={() => setModalOpen(true)}
      >
        Trigger Scout
      </Button>

      <TriggerScoutModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={() => {
          console.log('Scout triggered successfully!');
        }}
      />
    </>
  );
};
```

## API Endpoint

The modal sends a POST request to:
- **Endpoint:** `/api/v1/agents/scout/trigger`
- **Method:** `POST`
- **Payload:**
  ```json
  {
    "source": "stratninja" | "github" | "freqai_gym",
    "max_strategies": 100  // Optional, default 100, range 1-500
  }
  ```

## Integration with Strategy List

The modal automatically invalidates the strategy list after successful trigger, so any component displaying strategies will refresh automatically thanks to Refine's cache invalidation.

## Accessibility

- Keyboard navigation supported
- Form field labels with proper aria attributes
- Focus management on modal open/close
- Screen reader friendly error messages

## Type Definitions

All Scout-related types are defined in `/src/types/api.ts`:

```typescript
export type ScoutRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type ScoutTriggerType = 'manual' | 'scheduled' | 'event';

export interface ScoutMetrics {
  total_fetched: number;
  validated: number;
  validation_failed: number;
  duplicates_removed: number;
  submitted: number;
}

export interface ScoutRun {
  id: string;
  trigger_type: ScoutTriggerType;
  triggered_by?: string;
  source: string;
  max_strategies: number;
  status: ScoutRunStatus;
  error_message?: string;
  metrics?: ScoutMetrics;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}
```

## Navigation Setup

The Scout Runs resource is registered in `App.tsx`:

```typescript
{
  name: 'scout-runs',
  list: '/scout-runs',
  meta: {
    label: 'Scout Runs',
    icon: <SearchOutlined />,
  },
}
```

URL: `http://localhost:3000/scout-runs`

## Data Provider Configuration

The `scout-runs` resource is configured in `/src/providers/dataProvider.ts`:

```typescript
const endpoints = {
  "scout-runs": "/agents/scout/runs",
};

const listKeys = {
  "scout-runs": "runs",  // API response key
};
```

## Performance Considerations

- Pagination enabled (default 10 items per page)
- Live updates only refetch on actual changes
- Modal content destroyed on close to free memory
- Form reset on close/success
- Optimistic UI updates with proper error handling
- Debounced API calls (handled by useCustomMutation)

## File Structure

```
scout/
├── index.tsx              # Component exports
├── list.tsx               # ScoutList component (NEW)
├── TriggerScoutModal.tsx  # Trigger modal
├── ScheduleModal.tsx      # Schedule management
├── USAGE_EXAMPLE.tsx      # Usage examples
└── README.md              # This file
```
