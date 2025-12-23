# TriggerScoutModal - Integration Guide

## Complete Integration Example

This guide shows how to integrate the TriggerScoutModal into your existing FreqSearch pages.

## Component Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      Parent Component                        │
│  (e.g., StrategyList, Dashboard, etc.)                      │
│                                                              │
│  ┌──────────────┐                                           │
│  │ Trigger      │  onClick                                  │
│  │ Button       │────────────┐                              │
│  └──────────────┘            │                              │
│                               ▼                              │
│                        setModalOpen(true)                    │
│                                                              │
│  ┌──────────────────────────────────────────────────┐       │
│  │         TriggerScoutModal                        │       │
│  │  ┌────────────────────────────────────┐          │       │
│  │  │  Form                              │          │       │
│  │  │  ┌──────────────┐                 │          │       │
│  │  │  │ Source       │ (required)       │          │       │
│  │  │  └──────────────┘                 │          │       │
│  │  │  ┌──────────────┐                 │          │       │
│  │  │  │ Max Strats   │ (optional)       │          │       │
│  │  │  └──────────────┘                 │          │       │
│  │  └────────────────────────────────────┘          │       │
│  │                     │                             │       │
│  │                     │ onFinish                    │       │
│  │                     ▼                             │       │
│  │            useCustomMutation                      │       │
│  │                     │                             │       │
│  │                     ▼                             │       │
│  │    POST /api/v1/agents/scout/trigger             │       │
│  │              { source, max_strategies }           │       │
│  │                     │                             │       │
│  │         ┌───────────┴────────────┐                │       │
│  │         ▼                        ▼                │       │
│  │     Success                   Error               │       │
│  │         │                        │                │       │
│  │         ├─ message.success       ├─ message.error│       │
│  │         ├─ form.reset           └─ keep open     │       │
│  │         ├─ onClose()                             │       │
│  │         ├─ invalidate('strategies')              │       │
│  │         └─ onSuccess() callback                  │       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Step-by-Step Integration

### Step 1: Import the Component

```tsx
// In your page file (e.g., src/resources/strategies/list.tsx)
import { useState } from 'react';
import { TriggerScoutModal } from '@/resources/scout';
```

### Step 2: Add State Management

```tsx
export const StrategyList: React.FC = () => {
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);

  // ... rest of your component
};
```

### Step 3: Add Trigger Button

Choose one of these locations:

#### Option A: In Page Header (Recommended)

```tsx
import { List } from '@refinedev/antd';
import { Button } from 'antd';
import { RocketOutlined, PlusOutlined } from '@ant-design/icons';

export const StrategyList: React.FC = () => {
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);

  return (
    <List
      headerButtons={({ defaultButtons }) => (
        <>
          {defaultButtons}
          <Button
            type="primary"
            icon={<RocketOutlined />}
            onClick={() => setTriggerModalOpen(true)}
          >
            Trigger Scout
          </Button>
        </>
      )}
    >
      {/* Your list content */}
    </List>
  );
};
```

#### Option B: In Empty State

```tsx
import { Empty, Button } from 'antd';
import { RocketOutlined } from '@ant-design/icons';

// When no strategies exist
if (data?.data?.length === 0) {
  return (
    <Empty
      description="No strategies found"
      image={Empty.PRESENTED_IMAGE_SIMPLE}
    >
      <Button
        type="primary"
        icon={<RocketOutlined />}
        onClick={() => setTriggerModalOpen(true)}
      >
        Fetch Strategies with Scout
      </Button>
    </Empty>
  );
}
```

#### Option C: In Toolbar

```tsx
import { Space, Button } from 'antd';

<Space style={{ marginBottom: 16 }}>
  <Button
    type="primary"
    icon={<PlusOutlined />}
    onClick={() => navigate('/strategies/create')}
  >
    Create Strategy
  </Button>
  <Button
    icon={<RocketOutlined />}
    onClick={() => setTriggerModalOpen(true)}
  >
    Trigger Scout
  </Button>
</Space>
```

### Step 4: Add Modal Component

```tsx
export const StrategyList: React.FC = () => {
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);

  return (
    <>
      {/* Your page content */}

      <TriggerScoutModal
        open={triggerModalOpen}
        onClose={() => setTriggerModalOpen(false)}
        onSuccess={() => {
          // Optional: Add custom success handling
          console.log('Scout triggered successfully!');
        }}
      />
    </>
  );
};
```

## Complete Example: Strategy List Integration

```tsx
// src/resources/strategies/list.tsx
import React, { useState } from 'react';
import { List, useTable } from '@refinedev/antd';
import { Table, Space, Button, Tag } from 'antd';
import { RocketOutlined, EyeOutlined } from '@ant-design/icons';
import { TriggerScoutModal } from '@/resources/scout';
import type { Strategy } from '@/providers/types';

export const StrategyList: React.FC = () => {
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);

  const { tableProps } = useTable<Strategy>({
    syncWithLocation: true,
  });

  return (
    <>
      <List
        headerButtons={({ defaultButtons }) => (
          <>
            {defaultButtons}
            <Button
              type="primary"
              icon={<RocketOutlined />}
              onClick={() => setTriggerModalOpen(true)}
            >
              Trigger Scout
            </Button>
          </>
        )}
      >
        <Table {...tableProps} rowKey="id">
          <Table.Column dataIndex="name" title="Name" />
          <Table.Column
            dataIndex="generation"
            title="Generation"
            render={(value) => <Tag color="blue">Gen {value}</Tag>}
          />
          <Table.Column
            dataIndex="created_at"
            title="Created"
            render={(value) => new Date(value).toLocaleDateString()}
          />
          <Table.Column
            title="Actions"
            render={(_, record: Strategy) => (
              <Space>
                <Button
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => navigate(`/strategies/show/${record.id}`)}
                >
                  View
                </Button>
              </Space>
            )}
          />
        </Table>
      </List>

      <TriggerScoutModal
        open={triggerModalOpen}
        onClose={() => setTriggerModalOpen(false)}
        onSuccess={() => {
          console.log('Scout triggered - strategies will be refreshed');
        }}
      />
    </>
  );
};
```

## Advanced Integration Examples

### Example 1: Auto-trigger on Mount (Conditional)

```tsx
export const StrategyList: React.FC = () => {
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);
  const { data } = useList<Strategy>({ resource: 'strategies' });

  // Auto-open if no strategies and user hasn't dismissed
  useEffect(() => {
    const dismissed = localStorage.getItem('scout-auto-trigger-dismissed');
    if (!dismissed && data?.data?.length === 0) {
      setTriggerModalOpen(true);
    }
  }, [data]);

  const handleModalClose = () => {
    localStorage.setItem('scout-auto-trigger-dismissed', 'true');
    setTriggerModalOpen(false);
  };

  return (
    <>
      {/* Your content */}

      <TriggerScoutModal
        open={triggerModalOpen}
        onClose={handleModalClose}
      />
    </>
  );
};
```

### Example 2: With Loading Indicator

```tsx
export const StrategyList: React.FC = () => {
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);
  const [isScoutRunning, setIsScoutRunning] = useState(false);

  const handleSuccess = () => {
    setIsScoutRunning(true);
    // Optionally poll for completion
    setTimeout(() => setIsScoutRunning(false), 5000);
  };

  return (
    <>
      <List
        headerButtons={
          <>
            <Button
              type="primary"
              icon={<RocketOutlined />}
              onClick={() => setTriggerModalOpen(true)}
              loading={isScoutRunning}
            >
              {isScoutRunning ? 'Scout Running...' : 'Trigger Scout'}
            </Button>
          </>
        }
      >
        {isScoutRunning && (
          <Alert
            message="Scout is running"
            description="Fetching strategies from external sources..."
            type="info"
            showIcon
            closable
            style={{ marginBottom: 16 }}
          />
        )}

        {/* Your content */}
      </List>

      <TriggerScoutModal
        open={triggerModalOpen}
        onClose={() => setTriggerModalOpen(false)}
        onSuccess={handleSuccess}
      />
    </>
  );
};
```

### Example 3: With Confirmation Dialog

```tsx
import { Modal } from 'antd';

export const StrategyList: React.FC = () => {
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);

  const showConfirmation = () => {
    Modal.confirm({
      title: 'Trigger Scout Agent?',
      content: 'This will fetch new strategies from external sources. Continue?',
      onOk: () => setTriggerModalOpen(true),
    });
  };

  return (
    <>
      <Button
        type="primary"
        icon={<RocketOutlined />}
        onClick={showConfirmation}
      >
        Trigger Scout
      </Button>

      <TriggerScoutModal
        open={triggerModalOpen}
        onClose={() => setTriggerModalOpen(false)}
      />
    </>
  );
};
```

### Example 4: Multiple Integration Points

```tsx
export const Dashboard: React.FC = () => {
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);

  const openScoutModal = () => setTriggerModalOpen(true);

  return (
    <>
      {/* Header Action */}
      <PageHeader
        extra={
          <Button icon={<RocketOutlined />} onClick={openScoutModal}>
            Trigger Scout
          </Button>
        }
      />

      {/* Quick Actions Card */}
      <Card title="Quick Actions">
        <Space>
          <Button onClick={openScoutModal}>Fetch Strategies</Button>
          {/* Other actions */}
        </Space>
      </Card>

      {/* Empty State in Statistics */}
      {strategyCount === 0 && (
        <Empty description="No strategies">
          <Button type="link" onClick={openScoutModal}>
            Fetch from Scout
          </Button>
        </Empty>
      )}

      {/* Single modal instance */}
      <TriggerScoutModal
        open={triggerModalOpen}
        onClose={() => setTriggerModalOpen(false)}
      />
    </>
  );
};
```

## Error Handling Best Practices

```tsx
const handleSuccess = () => {
  notification.success({
    message: 'Scout Triggered',
    description: 'Strategies will be fetched in the background. Check back soon!',
    duration: 5,
  });
};

const handleError = (error: Error) => {
  notification.error({
    message: 'Scout Trigger Failed',
    description: error.message,
    duration: 10,
  });
};
```

## TypeScript Tips

```tsx
// Type the modal state
const [triggerModalOpen, setTriggerModalOpen] = useState<boolean>(false);

// Type the success callback
const handleSuccess = (): void => {
  console.log('Success');
};

// Use with Refine types
import type { Strategy } from '@/providers/types';
```

## Common Issues and Solutions

### Issue: Modal doesn't trigger data refresh

**Solution:** Ensure Refine resource is named correctly:
```tsx
// In your data provider setup
resources={[
  {
    name: 'strategies',  // Must match the invalidate call
    // ...
  }
]}
```

### Issue: Form doesn't reset after submit

**Solution:** The component handles this automatically. If you need custom reset:
```tsx
<TriggerScoutModal
  open={triggerModalOpen}
  onClose={() => {
    setTriggerModalOpen(false);
    // Add custom cleanup here
  }}
/>
```

### Issue: Multiple modals conflict

**Solution:** Use unique state for each modal:
```tsx
const [triggerModalOpen, setTriggerModalOpen] = useState(false);
const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
```

## Performance Tips

1. **Lazy Loading**: Keep modal closed by default
2. **Single Instance**: Reuse one modal for multiple triggers
3. **Cleanup**: Modal uses `destroyOnClose` automatically
4. **Memoization**: For expensive trigger button renders:
   ```tsx
   const triggerButton = useMemo(
     () => (
       <Button onClick={() => setTriggerModalOpen(true)}>
         Trigger Scout
       </Button>
     ),
     []
   );
   ```

## Accessibility Checklist

- [ ] Button has descriptive text or aria-label
- [ ] Modal can be closed with Esc key
- [ ] Form fields have labels
- [ ] Error messages are announced
- [ ] Focus returns to trigger button on close

## Next Steps

1. Choose integration location (header, toolbar, empty state)
2. Add trigger button
3. Add modal component
4. Test with your API endpoint
5. Add custom success handling if needed
6. Style to match your design system

## Questions?

- Check README.md for component API
- Review USAGE_EXAMPLE.tsx for patterns
- See IMPLEMENTATION_SUMMARY.md for details
