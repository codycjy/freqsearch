import React from 'react';
import { useShow, useNavigation, useCustomMutation, useInvalidate } from '@refinedev/core';
import { Show, DateField } from '@refinedev/antd';
import {
  Card,
  Row,
  Col,
  Descriptions,
  Tag,
  Typography,
  Space,
  Alert,
  Statistic,
  Button,
  Progress,
  message,
} from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  StopOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import type { ScoutRun, ScoutRunStatus } from '@/types/api';

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
  if (!start) return 'Not started';

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
 * Calculate percentage for progress bars
 */
const calculatePercentage = (value: number, total: number): number => {
  if (total === 0) return 0;
  return Math.round((value / total) * 100);
};

/**
 * ScoutShow Component
 *
 * Displays detailed information about a Scout agent run including:
 * - Basic information (ID, status, trigger type, source, etc.)
 * - Metrics with statistics and progress bars
 * - Error information (if failed)
 * - Cancel action for pending/running runs
 *
 * Features:
 * - Real-time updates via live mode
 * - Visual metrics with Ant Design Statistic and Progress components
 * - Conditional rendering based on status
 * - Cancel functionality for active runs
 */
export const ScoutShow: React.FC = () => {
  const { list } = useNavigation();
  const invalidate = useInvalidate();

  const { queryResult } = useShow<ScoutRun>({
    liveMode: 'auto', // Enable real-time updates
  });

  const { data, isLoading } = queryResult;
  const run = data?.data;

  // Cancel mutation
  const { mutate: cancelRun, isLoading: isCancelling } = useCustomMutation();

  /**
   * Handle cancel action
   */
  const handleCancel = async () => {
    if (!run?.id) return;

    cancelRun(
      {
        url: `/agents/scout/runs/${run.id}`,
        method: 'delete',
        values: {},
      },
      {
        onSuccess: () => {
          message.success('Scout run cancelled successfully');
          invalidate({
            resource: 'scout-runs',
            invalidates: ['detail', 'list'],
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
    <Show
      isLoading={isLoading}
      headerButtons={({ defaultButtons }) => (
        <>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => list('scout-runs')}
          >
            Back to List
          </Button>
          {run && (run.status === 'pending' || run.status === 'running') && (
            <Button
              danger
              icon={<StopOutlined />}
              onClick={handleCancel}
              loading={isCancelling}
            >
              Cancel Run
            </Button>
          )}
          {defaultButtons}
        </>
      )}
    >
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* Basic Information */}
        <Card title="Scout Run Information">
          <Descriptions column={2} bordered>
            <Descriptions.Item label="Run ID">
              <Text code copyable={{ text: run?.id }}>
                {run?.id}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color={STATUS_COLORS[run?.status || 'pending']}>
                {STATUS_TEXT[run?.status || 'pending']}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Trigger Type">
              <Tag
                color={
                  run?.trigger_type === 'manual'
                    ? 'blue'
                    : run?.trigger_type === 'scheduled'
                    ? 'green'
                    : 'orange'
                }
              >
                {run?.trigger_type
                  ? run.trigger_type.charAt(0).toUpperCase() + run.trigger_type.slice(1)
                  : 'Unknown'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Triggered By">
              {run?.triggered_by ? (
                <Text>{run.triggered_by}</Text>
              ) : (
                <Text type="secondary">System</Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Source">
              <Text strong>{run?.source}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="Max Strategies">
              <Text>{run?.max_strategies}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="Created At">
              <DateField value={run?.created_at} format="YYYY-MM-DD HH:mm:ss" />
            </Descriptions.Item>
            <Descriptions.Item label="Started At">
              {run?.started_at ? (
                <DateField value={run.started_at} format="YYYY-MM-DD HH:mm:ss" />
              ) : (
                <Text type="secondary">Not started</Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Completed At">
              {run?.completed_at ? (
                <DateField value={run.completed_at} format="YYYY-MM-DD HH:mm:ss" />
              ) : (
                <Text type="secondary">Not completed</Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Duration">
              <Text>
                {calculateDuration(run?.started_at, run?.completed_at)}
              </Text>
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* Error Message - Only show if failed */}
        {run?.status === 'failed' && run?.error_message && (
          <Alert
            message="Error Details"
            description={run.error_message}
            type="error"
            showIcon
            icon={<CloseCircleOutlined />}
          />
        )}

        {/* Metrics */}
        {run?.metrics && (
          <Card title="Metrics">
            <Row gutter={[16, 16]}>
              <Col xs={24} sm={12} md={8}>
                <Statistic
                  title="Total Fetched"
                  value={run.metrics.total_fetched}
                  prefix={<CheckCircleOutlined />}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Col>
              <Col xs={24} sm={12} md={8}>
                <Statistic
                  title="Validated"
                  value={run.metrics.validated}
                  prefix={<CheckCircleOutlined />}
                  valueStyle={{ color: '#52c41a' }}
                />
                <Progress
                  percent={calculatePercentage(
                    run.metrics.validated,
                    run.metrics.total_fetched
                  )}
                  status="success"
                  size="small"
                />
              </Col>
              <Col xs={24} sm={12} md={8}>
                <Statistic
                  title="Validation Failed"
                  value={run.metrics.validation_failed}
                  prefix={<CloseCircleOutlined />}
                  valueStyle={{ color: '#ff4d4f' }}
                />
                <Progress
                  percent={calculatePercentage(
                    run.metrics.validation_failed,
                    run.metrics.total_fetched
                  )}
                  status="exception"
                  size="small"
                />
              </Col>
              <Col xs={24} sm={12} md={8}>
                <Statistic
                  title="Duplicates Removed"
                  value={run.metrics.duplicates_removed}
                  valueStyle={{ color: '#faad14' }}
                />
                <Progress
                  percent={calculatePercentage(
                    run.metrics.duplicates_removed,
                    run.metrics.total_fetched
                  )}
                  status="normal"
                  size="small"
                />
              </Col>
              <Col xs={24} sm={12} md={8}>
                <Statistic
                  title="Submitted"
                  value={run.metrics.submitted}
                  prefix={<CheckCircleOutlined />}
                  valueStyle={{ color: '#52c41a' }}
                />
                <Progress
                  percent={calculatePercentage(
                    run.metrics.submitted,
                    run.metrics.validated
                  )}
                  status="success"
                  size="small"
                />
              </Col>
            </Row>

            {/* Summary Stats */}
            <Card
              type="inner"
              title="Summary"
              style={{ marginTop: 24 }}
              size="small"
            >
              <Row gutter={[16, 16]}>
                <Col span={12}>
                  <Statistic
                    title="Success Rate"
                    value={calculatePercentage(
                      run.metrics.validated,
                      run.metrics.total_fetched
                    )}
                    suffix="%"
                    valueStyle={{
                      color:
                        calculatePercentage(
                          run.metrics.validated,
                          run.metrics.total_fetched
                        ) >= 50
                          ? '#52c41a'
                          : '#ff4d4f',
                    }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="Submission Rate"
                    value={calculatePercentage(
                      run.metrics.submitted,
                      run.metrics.validated
                    )}
                    suffix="%"
                    valueStyle={{
                      color:
                        calculatePercentage(
                          run.metrics.submitted,
                          run.metrics.validated
                        ) >= 50
                          ? '#52c41a'
                          : '#ff4d4f',
                    }}
                  />
                </Col>
              </Row>
            </Card>
          </Card>
        )}

        {/* No Metrics Available */}
        {!run?.metrics && run?.status !== 'pending' && (
          <Alert
            message="No metrics available yet"
            description="Metrics will be displayed once the Scout run starts processing strategies."
            type="info"
            showIcon
          />
        )}
      </Space>
    </Show>
  );
};
