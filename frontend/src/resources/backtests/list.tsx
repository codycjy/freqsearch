import React from 'react';
import { useNavigation } from '@refinedev/core';
import { List, useTable as useAntdTable, DateField } from '@refinedev/antd';
import { Table, Space, Tag, Button, Select, Typography } from 'antd';
import { EyeOutlined, StopOutlined } from '@ant-design/icons';
import type { BacktestJob, JobStatus } from '@providers/types';

const { Text } = Typography;

/**
 * Status color mapping for backtest jobs
 */
const STATUS_COLORS: Record<JobStatus, string> = {
  JOB_STATUS_UNSPECIFIED: 'default',
  JOB_STATUS_PENDING: 'blue',
  JOB_STATUS_RUNNING: 'orange',
  JOB_STATUS_COMPLETED: 'green',
  JOB_STATUS_FAILED: 'red',
  JOB_STATUS_CANCELLED: 'default',
};

/**
 * Status display text
 */
const STATUS_TEXT: Record<JobStatus, string> = {
  JOB_STATUS_UNSPECIFIED: 'Unknown',
  JOB_STATUS_PENDING: 'Pending',
  JOB_STATUS_RUNNING: 'Running',
  JOB_STATUS_COMPLETED: 'Completed',
  JOB_STATUS_FAILED: 'Failed',
  JOB_STATUS_CANCELLED: 'Cancelled',
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
 * BacktestList Component
 *
 * Displays a list of backtest jobs with:
 * - Filtering by status and strategy
 * - Real-time status updates via live provider
 * - Actions to view details and cancel jobs
 * - Duration calculation
 */
export const BacktestList: React.FC = () => {
  const { show } = useNavigation();

  const { tableProps, setFilters } = useAntdTable<BacktestJob>({
    resource: 'backtests',
    syncWithLocation: true,
    liveMode: 'auto', // Enable real-time updates
    onLiveEvent: (event) => {
      // Refetch when backtest events occur
      if (event.type === 'created' || event.type === 'updated') {
        if (tableProps.onChange) {
          tableProps.onChange({} as any, {}, {}, {} as any);
        }
      }
    },
  });

  // Handle cancel action
  const handleCancel = async (id: string) => {
    // TODO: Implement cancel API call
    console.log('Cancel backtest:', id);
  };

  return (
    <List>
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
              { label: 'Pending', value: 'JOB_STATUS_PENDING' },
              { label: 'Running', value: 'JOB_STATUS_RUNNING' },
              { label: 'Completed', value: 'JOB_STATUS_COMPLETED' },
              { label: 'Failed', value: 'JOB_STATUS_FAILED' },
              { label: 'Cancelled', value: 'JOB_STATUS_CANCELLED' },
            ]}
          />
        </Space>

        {/* Table */}
        <Table<BacktestJob>
          {...tableProps}
          rowKey="id"
          pagination={{
            ...tableProps.pagination,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} backtests`,
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
            dataIndex="strategy_id"
            title="Strategy"
            render={(value: string) => (
              <Text code copyable={{ text: value }}>
                {value.slice(0, 8)}
              </Text>
            )}
          />

          <Table.Column
            dataIndex="status"
            title="Status"
            render={(value: JobStatus) => (
              <Tag color={STATUS_COLORS[value]}>
                {STATUS_TEXT[value]}
              </Tag>
            )}
            filters={[
              { text: 'Pending', value: 'JOB_STATUS_PENDING' },
              { text: 'Running', value: 'JOB_STATUS_RUNNING' },
              { text: 'Completed', value: 'JOB_STATUS_COMPLETED' },
              { text: 'Failed', value: 'JOB_STATUS_FAILED' },
            ]}
          />

          <Table.Column
            dataIndex="priority"
            title="Priority"
            sorter
            width={100}
            render={(value: number) => (
              <Tag color={value > 5 ? 'red' : value > 3 ? 'orange' : 'default'}>
                {value}
              </Tag>
            )}
          />

          <Table.Column
            dataIndex="created_at"
            title="Created"
            sorter
            render={(value: string) => <DateField value={value} format="YYYY-MM-DD HH:mm:ss" />}
          />

          <Table.Column
            key="duration"
            title="Duration"
            render={(_, record: BacktestJob) => {
              const duration = calculateDuration(
                record.started_at,
                record.completed_at
              );
              return <Text>{duration}</Text>;
            }}
          />

          <Table.Column
            dataIndex="optimization_run_id"
            title="Optimization"
            render={(value?: string) =>
              value ? (
                <Text code copyable={{ text: value }}>
                  {value.slice(0, 8)}
                </Text>
              ) : (
                <Text type="secondary">-</Text>
              )
            }
          />

          <Table.Column
            title="Actions"
            fixed="right"
            width={150}
            render={(_, record: BacktestJob) => (
              <Space>
                <Button
                  type="link"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => show('backtests', record.id)}
                >
                  View
                </Button>
                {(record.status === 'JOB_STATUS_PENDING' ||
                  record.status === 'JOB_STATUS_RUNNING') && (
                  <Button
                    type="link"
                    danger
                    size="small"
                    icon={<StopOutlined />}
                    onClick={() => handleCancel(record.id)}
                  >
                    Cancel
                  </Button>
                )}
              </Space>
            )}
          />
        </Table>
      </Space>
    </List>
  );
};
