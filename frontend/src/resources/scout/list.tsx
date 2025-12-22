import React, { useState } from 'react';
import { useNavigation, useCustomMutation, useInvalidate } from '@refinedev/core';
import { List, useTable as useAntdTable, DateField } from '@refinedev/antd';
import { Table, Space, Tag, Button, Select, Typography, message } from 'antd';
import { EyeOutlined, StopOutlined, RocketOutlined } from '@ant-design/icons';
import type { ScoutRun, ScoutRunStatus } from '@/types/api';
import { TriggerScoutModal } from './TriggerScoutModal';

const { Text } = Typography;

/**
 * Status color mapping for Scout runs
 */
const STATUS_COLORS: Record<ScoutRunStatus, string> = {
  pending: 'blue',
  running: 'orange',
  completed: 'green',
  failed: 'red',
  cancelled: 'default',
};

/**
 * Status display text
 */
const STATUS_TEXT: Record<ScoutRunStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

/**
 * Calculate duration between two dates
 */
const calculateDuration = (start?: string, end?: string): string => {
  if (!start) return '-';

  const startTime = new Date(start).getTime();
  const endTime = end ? new Date(end).getTime() : Date.now();
  const diffMs = endTime - startTime;

  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  } else {
    return `${seconds}s`;
  }
};

/**
 * Format metrics summary
 */
const formatMetricsSummary = (run: ScoutRun): string => {
  if (!run.metrics) {
    return '-';
  }

  const { total_fetched, validated, submitted } = run.metrics;
  return `Fetched: ${total_fetched || 0} | Validated: ${validated || 0} | Submitted: ${submitted || 0}`;
};

/**
 * ScoutList Component
 *
 * Displays a list of Scout agent runs with:
 * - Real-time status updates via live provider
 * - Filtering by status
 * - Actions to view details and cancel runs
 * - Manual trigger button
 * - Metrics summary display
 *
 * Features:
 * - Short ID display with copy functionality
 * - Status tags with color coding
 * - Duration calculation for running/completed jobs
 * - Metrics summary (fetched, validated, submitted)
 * - Cancel action for pending/running jobs
 * - Manual trigger via modal
 */
export const ScoutList: React.FC = () => {
  const { show } = useNavigation();
  const invalidate = useInvalidate();
  const [modalOpen, setModalOpen] = useState(false);

  const { tableProps, setFilters } = useAntdTable<ScoutRun>({
    resource: 'scout-runs',
    syncWithLocation: true,
    liveMode: 'auto', // Enable real-time updates
    onLiveEvent: (event) => {
      // Refetch when scout run events occur
      if (event.type === 'created' || event.type === 'updated') {
        if (tableProps.onChange) {
          tableProps.onChange({} as any, {}, {}, {} as any);
        }
      }
    },
  });

  // Cancel mutation
  const { mutate: cancelRun, isLoading: isCancelling } = useCustomMutation();

  /**
   * Handle cancel action
   */
  const handleCancel = async (id: string) => {
    cancelRun(
      {
        url: `/agents/scout/runs/${id}`,
        method: 'delete',
        values: {},
      },
      {
        onSuccess: () => {
          message.success('Scout run cancelled successfully');
          invalidate({
            resource: 'scout-runs',
            invalidates: ['list'],
          });
        },
        onError: (error: any) => {
          const errorMessage = error?.message || 'Failed to cancel Scout run';
          message.error(errorMessage);
        },
      }
    );
  };

  return (
    <List
      headerButtons={({ defaultButtons }) => (
        <>
          {defaultButtons}
          <Button
            type="primary"
            icon={<RocketOutlined />}
            onClick={() => setModalOpen(true)}
          >
            Trigger Scout
          </Button>
        </>
      )}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {/* Filters */}
        <Space>
          <Select
            placeholder="Filter by status"
            style={{ width: 200 }}
            allowClear
            onChange={(value) => {
              setFilters([
                {
                  field: 'status',
                  operator: 'eq',
                  value,
                },
              ]);
            }}
            options={[
              { label: 'Pending', value: 'pending' },
              { label: 'Running', value: 'running' },
              { label: 'Completed', value: 'completed' },
              { label: 'Failed', value: 'failed' },
              { label: 'Cancelled', value: 'cancelled' },
            ]}
          />
        </Space>

        {/* Table */}
        <Table<ScoutRun>
          {...tableProps}
          rowKey="id"
          pagination={{
            ...tableProps.pagination,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} scout runs`,
          }}
        >
          <Table.Column
            dataIndex="id"
            title="ID"
            width={100}
            render={(value: string) => (
              <Text code copyable={{ text: value }}>
                {value.slice(0, 8)}
              </Text>
            )}
          />

          <Table.Column
            dataIndex="trigger_type"
            title="Trigger Type"
            width={120}
            render={(value: string) => {
              const colorMap: Record<string, string> = {
                manual: 'blue',
                scheduled: 'green',
                event: 'orange',
              };
              return (
                <Tag color={colorMap[value] || 'default'}>
                  {value.charAt(0).toUpperCase() + value.slice(1)}
                </Tag>
              );
            }}
            filters={[
              { text: 'Manual', value: 'manual' },
              { text: 'Scheduled', value: 'scheduled' },
              { text: 'Event', value: 'event' },
            ]}
          />

          <Table.Column
            dataIndex="source"
            title="Source"
            width={150}
            render={(value: string) => <Text strong>{value}</Text>}
          />

          <Table.Column
            dataIndex="status"
            title="Status"
            width={120}
            render={(value: ScoutRunStatus) => (
              <Tag color={STATUS_COLORS[value]}>
                {STATUS_TEXT[value]}
              </Tag>
            )}
            filters={[
              { text: 'Pending', value: 'pending' },
              { text: 'Running', value: 'running' },
              { text: 'Completed', value: 'completed' },
              { text: 'Failed', value: 'failed' },
              { text: 'Cancelled', value: 'cancelled' },
            ]}
          />

          <Table.Column
            key="metrics"
            title="Metrics Summary"
            width={300}
            render={(_, record: ScoutRun) => (
              <Text type={record.metrics ? undefined : 'secondary'}>
                {formatMetricsSummary(record)}
              </Text>
            )}
          />

          <Table.Column
            dataIndex="created_at"
            title="Created"
            sorter
            width={180}
            render={(value: string) => <DateField value={value} format="YYYY-MM-DD HH:mm:ss" />}
          />

          <Table.Column
            key="duration"
            title="Duration"
            width={120}
            render={(_, record: ScoutRun) => {
              const duration = calculateDuration(
                record.started_at,
                record.completed_at
              );
              return <Text>{duration}</Text>;
            }}
          />

          <Table.Column
            title="Actions"
            fixed="right"
            width={150}
            render={(_, record: ScoutRun) => (
              <Space>
                <Button
                  type="link"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => show('scout-runs', record.id)}
                >
                  View
                </Button>
                {(record.status === 'pending' || record.status === 'running') && (
                  <Button
                    type="link"
                    danger
                    size="small"
                    icon={<StopOutlined />}
                    onClick={() => handleCancel(record.id)}
                    loading={isCancelling}
                  >
                    Cancel
                  </Button>
                )}
              </Space>
            )}
          />
        </Table>
      </Space>

      {/* Trigger Scout Modal */}
      <TriggerScoutModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={() => {
          // Refresh the list when a new scout run is triggered
          invalidate({
            resource: 'scout-runs',
            invalidates: ['list'],
          });
        }}
      />
    </List>
  );
};
