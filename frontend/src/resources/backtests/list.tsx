import React from 'react';
import { useNavigation, useDelete, useCustom, useCreate } from '@refinedev/core';
import { List, useTable as useAntdTable, DateField } from '@refinedev/antd';
import { Table, Space, Tag, Button, Select, Typography, Card, Statistic, Row, Col, Tooltip } from 'antd';
import { EyeOutlined, StopOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons';
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
interface QueueStats {
  pending_jobs: number;
  running_jobs: number;
  completed_today: number;
  failed_today: number;
  max_concurrent: number;
}

export const BacktestList: React.FC = () => {
  const { show } = useNavigation();
  const { mutate: cancelBacktest } = useDelete();
  const { mutate: createBacktest } = useCreate();

  // Fetch queue stats
  const { data: queueStats, isLoading: queueLoading, refetch: refetchQueue } = useCustom<QueueStats>({
    url: '/backtests/queue/stats',
    method: 'get',
    queryOptions: {
      refetchInterval: 5000, // Refresh every 5 seconds
    },
  });

  const { tableProps, setFilters, tableQuery } = useAntdTable<BacktestJob>({
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
    try {
      cancelBacktest({
        resource: 'backtests',
        id: id,
        successNotification: {
          message: 'Backtest cancelled successfully',
          type: 'success',
        },
        errorNotification: {
          message: 'Failed to cancel backtest',
          type: 'error',
        },
      });
    } catch (error) {
      console.error('Cancel error:', error);
    }
  };

  // Handle retry action - resubmit failed backtest with same config
  const handleRetry = async (record: BacktestJob) => {
    createBacktest({
      resource: 'backtests',
      values: {
        strategy_id: record.strategy_id,
        config: record.config,
        priority: record.priority,
      },
      successNotification: {
        message: 'Backtest resubmitted successfully',
        type: 'success',
      },
      errorNotification: {
        message: 'Failed to retry backtest',
        type: 'error',
      },
    }, {
      onSuccess: () => {
        tableQuery.refetch();
        refetchQueue();
      },
    });
  };

  const stats = queueStats?.data;

  return (
    <List>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {/* Queue Stats Bar */}
        <Card size="small" loading={queueLoading}>
          <Row gutter={16}>
            <Col span={4}>
              <Statistic
                title="Pending"
                value={stats?.pending_jobs ?? 0}
                valueStyle={{ color: '#1890ff' }}
                prefix={<SyncOutlined spin={!!stats?.running_jobs} />}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="Running"
                value={stats?.running_jobs ?? 0}
                suffix={`/ ${stats?.max_concurrent ?? 8}`}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="Completed Today"
                value={stats?.completed_today ?? 0}
                valueStyle={{ color: '#52c41a' }}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="Failed Today"
                value={stats?.failed_today ?? 0}
                valueStyle={{ color: stats?.failed_today ? '#ff4d4f' : undefined }}
              />
            </Col>
            <Col span={8} style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
              <Button icon={<ReloadOutlined />} onClick={() => { tableQuery.refetch(); refetchQueue(); }}>
                Refresh
              </Button>
            </Col>
          </Row>
        </Card>

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
            width={180}
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
                {record.status === 'JOB_STATUS_FAILED' && (
                  <Tooltip title="Retry with same config">
                    <Button
                      type="link"
                      size="small"
                      icon={<ReloadOutlined />}
                      onClick={() => handleRetry(record)}
                    >
                      Retry
                    </Button>
                  </Tooltip>
                )}
              </Space>
            )}
          />
        </Table>
      </Space>
    </List>
  );
};
