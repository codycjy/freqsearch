# Scout Schedule Management

This module provides Scout scheduling functionality for the FreqSearch frontend application.

## Components

### ScoutScheduleList

The main list view component for managing Scout schedules.

**Features:**
- Display all Scout schedules in a table
- Inline toggle for enable/disable status
- Create new schedules via modal
- Edit existing schedules
- Delete schedules with confirmation
- Human-readable cron descriptions
- Filter by source and enabled status
- Sortable columns

**Usage in routing:**

```tsx
import { ScoutScheduleList } from '@resources/scout';

// In your resource configuration
{
  name: 'agents/scout/schedules',
  list: '/scout/schedules',
  // ... other routes
}

// In your route component
<Route path="/scout/schedules" element={<ScoutScheduleList />} />
```

### ScheduleModal

A reusable modal component for creating and editing Scout schedules.

**Features:**
- Cron expression presets (hourly, daily, weekly, etc.)
- Custom cron expression support with validation
- Data source selection (StratNinja, GitHub, FreqAI Gym)
- Max strategies configuration
- Enable/disable toggle
- Real-time cron description preview

**Props:**

```typescript
interface ScheduleModalProps {
  visible: boolean;           // Control modal visibility
  mode: 'create' | 'edit';   // Create or edit mode
  schedule?: ScoutSchedule;   // Schedule data for edit mode
  loading?: boolean;          // Loading state for submit button
  onSubmit: (values: CreateScoutSchedulePayload | UpdateScoutSchedulePayload) => void;
  onCancel: () => void;       // Cancel handler
}
```

**Standalone usage:**

```tsx
import { ScheduleModal } from '@resources/scout';

function MyComponent() {
  const [visible, setVisible] = useState(false);

  const handleSubmit = (values) => {
    // Handle creation/update
    console.log('Schedule values:', values);
  };

  return (
    <ScheduleModal
      visible={visible}
      mode="create"
      onSubmit={handleSubmit}
      onCancel={() => setVisible(false)}
    />
  );
}
```

## API Integration

The components expect the following API endpoints:

### List Schedules
```
GET /api/v1/agents/scout/schedules
Response: { schedules: ScoutSchedule[], pagination: PaginationResponse }
```

### Create Schedule
```
POST /api/v1/agents/scout/schedules
Body: CreateScoutSchedulePayload
Response: ScoutSchedule
```

### Update Schedule
```
PUT /api/v1/agents/scout/schedules/:id
Body: UpdateScoutSchedulePayload
Response: ScoutSchedule
```

### Delete Schedule
```
DELETE /api/v1/agents/scout/schedules/:id
Response: { success: boolean }
```

### Toggle Schedule Status
```
POST /api/v1/agents/scout/schedules/:id/toggle
Body: { enabled: boolean }
Response: ScoutSchedule
```

## Types

All TypeScript types are defined in `/providers/types.ts`:

```typescript
export type ScoutSource = "stratninja" | "github" | "freqai_gym";

export interface ScoutSchedule {
  id: string;
  name: string;
  cron_expression: string;
  source: ScoutSource;
  max_strategies: number;
  enabled: boolean;
  last_run_at?: string;
  next_run_at?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateScoutSchedulePayload {
  name: string;
  cron_expression: string;
  source: ScoutSource;
  max_strategies?: number;  // defaults to 100
  enabled?: boolean;        // defaults to true
}

export interface UpdateScoutSchedulePayload {
  name?: string;
  cron_expression?: string;
  source?: ScoutSource;
  max_strategies?: number;
  enabled?: boolean;
}
```

## Cron Expression Presets

The ScheduleModal provides the following presets:

- **Every hour**: `0 * * * *`
- **Every 2 hours**: `0 */2 * * *`
- **Every 6 hours**: `0 */6 * * *`
- **Daily at 2:00 AM**: `0 2 * * *`
- **Daily at 8:00 AM**: `0 8 * * *`
- **Every Monday at 9:00 AM**: `0 9 * * 1`
- **Every weekday at 9:00 AM**: `0 9 * * 1-5`
- **Custom**: User-defined cron expression

## Data Sources

Three data sources are supported:

1. **StratNinja** (`stratninja`): Import strategies from StratNinja marketplace
2. **GitHub** (`github`): Search and import strategies from GitHub repositories
3. **FreqAI Gym** (`freqai_gym`): Import strategies from FreqAI Gym collection

## Accessibility

- All interactive elements have proper ARIA labels
- Keyboard navigation fully supported
- Form validation with clear error messages
- Tooltips for additional context
- Color-coded tags with sufficient contrast

## Performance Considerations

- Uses Refine's `useCustomMutation` for optimized API calls
- Implements cache invalidation to keep data fresh
- Table supports pagination and sorting
- Modal form validation prevents unnecessary API calls
- Loading states prevent duplicate submissions

## Testing Recommendations

1. **Unit Tests**: Test cron description generation, form validation
2. **Integration Tests**: Test CRUD operations with mocked API
3. **E2E Tests**: Test complete user flows (create, edit, delete, toggle)
4. **Accessibility Tests**: Ensure WCAG 2.1 AA compliance

## Future Enhancements

- [ ] Schedule preview showing next 5 run times
- [ ] Run history for each schedule
- [ ] Bulk enable/disable operations
- [ ] Schedule templates
- [ ] Import/export schedules as JSON
- [ ] Duplicate schedule functionality
- [ ] Advanced cron builder UI
