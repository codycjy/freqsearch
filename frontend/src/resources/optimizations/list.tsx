import { useNavigation } from '@refinedev/core';
import { List, useTable, FilterDropdown, ShowButton } from '@refinedev/antd';
import { Table, Tag, Progress, Typography, Select, Space } from 'antd';
import type { OptimizationRun, OptimizationStatus } from '@providers/types';
import { OptimizationControlPanel } from './control';
import { useState } from 'react';

const { Text } = Typography;

const statusColors: Record<OptimizationStatus, string> = {
  OPTIMIZATION_STATUS_UNSPECIFIED: 'default',
  OPTIMIZATION_STATUS_PENDING: 'blue',
  OPTIMIZATION_STATUS_RUNNING: 'green',
  OPTIMIZATION_STATUS_PAUSED: 'orange',
  OPTIMIZATION_STATUS_COMPLETED: 'cyan',
  OPTIMIZATION_STATUS_FAILED: 'red',
  OPTIMIZATION_STATUS_CANCELLED: 'gray',
};

const statusLabels: Record<OptimizationStatus, string> = {
  OPTIMIZATION_STATUS_UNSPECIFIED: 'Unknown',
  OPTIMIZATION_STATUS_PENDING: 'Pending',
  OPTIMIZATION_STATUS_RUNNING: 'Running',
  OPTIMIZATION_STATUS_PAUSED: 'Paused',
  OPTIMIZATION_STATUS_COMPLETED: 'Completed',
  OPTIMIZATION_STATUS_FAILED: 'Failed',
  OPTIMIZATION_STATUS_CANCELLED: 'Cancelled',
};

export const OptimizationList = () => {
  useNavigation();
  const [, setControllingId] = useState<string | null>(null);

  const { tableProps } = useTable<OptimizationRun>({
    resource: 'optimizations',
    pagination: {
      pageSize: 20,
    },
    liveMode: 'auto',
  });

  const handleControlSuccess = () => {
    setControllingId(null);
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: OptimizationRun) => (
        <div>
          <Text strong>{name}</Text>
          <br />
          <Text type="secondary" style={{ fontSize: '12px' }}>
            ID: {record.id.substring(0, 8)}...
          </Text>
        </div>
      ),
    },
    {
      title: 'Base Strategy',
      dataIndex: 'base_strategy_id',
      key: 'base_strategy_id',
      render: (strategyId: string) => (
        <Text code style={{ fontSize: '12px' }}>
          {strategyId.substring(0, 12)}...
        </Text>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: OptimizationStatus) => (
        <Tag color={statusColors[status] || 'default'}>
          {statusLabels[status] || status}
        </Tag>
      ),
      filterDropdown: (props: any) => (
        <FilterDropdown {...props}>
          <Select
            style={{ width: 200 }}
            mode="multiple"
            placeholder="Select status"
            options={Object.entries(statusLabels).map(([value, label]) => ({
              label,
              value,
            }))}
          />
        </FilterDropdown>
      ),
    },
    {
      title: 'Progress',
      key: 'progress',
      render: (_: any, record: OptimizationRun) => {
        const percent = (record.current_iteration / record.max_iterations) * 100;
        return (
          <div>
            <Progress
              percent={Math.round(percent)}
              size="small"
              status={
                record.status === 'OPTIMIZATION_STATUS_RUNNING'
                  ? 'active'
                  : record.status === 'OPTIMIZATION_STATUS_COMPLETED'
                  ? 'success'
                  : record.status === 'OPTIMIZATION_STATUS_FAILED'
                  ? 'exception'
                  : 'normal'
              }
            />
            <Text type="secondary" style={{ fontSize: '12px' }}>
              {record.current_iteration} / {record.max_iterations} iterations
            </Text>
          </div>
        );
      },
    },
    {
      title: 'Best Sharpe',
      dataIndex: ['best_result', 'sharpe_ratio'],
      key: 'best_sharpe',
      render: (sharpe?: number) => (
        <Text strong style={{ color: sharpe && sharpe > 0 ? '#52c41a' : undefined }}>
          {sharpe !== undefined && sharpe !== null ? sharpe.toFixed(3) : 'N/A'}
        </Text>
      ),
      sorter: true,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
      sorter: true,
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: OptimizationRun) => (
        <Space size="small">
          <ShowButton hideText size="small" recordItemId={record.id} />
          {(record.status === 'OPTIMIZATION_STATUS_RUNNING' ||
            record.status === 'OPTIMIZATION_STATUS_PAUSED') && (
            <OptimizationControlPanel
              optimizationId={record.id}
              currentStatus={record.status}
              size="small"
              onSuccess={handleControlSuccess}
            />
          )}
        </Space>
      ),
    },
  ];

  return (
    <List>
      <Table
        {...tableProps}
        columns={columns}
        rowKey="id"
        pagination={{
          ...tableProps.pagination,
          showSizeChanger: true,
          showTotal: (total) => `Total ${total} optimization runs`,
        }}
      />
    </List>
  );
};
