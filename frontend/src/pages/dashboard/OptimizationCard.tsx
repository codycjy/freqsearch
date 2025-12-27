import { Card, Title, Text, ProgressBar, Flex, Badge, Metric } from '@tremor/react';
import { Button, Space, Tooltip } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { OptimizationRun } from '../../types/api';

interface OptimizationCardProps {
  optimization: OptimizationRun;
  onPause?: (id: string) => void;
  onResume?: (id: string) => void;
  onCancel?: (id: string) => void;
  loading?: boolean;
}

/**
 * OptimizationCard Component
 * Displays individual optimization run with:
 * - Name and status
 * - Progress bar (current iteration / max iterations)
 * - Best Sharpe ratio achieved
 * - Quick action buttons (pause/resume/cancel)
 */
export const OptimizationCard: React.FC<OptimizationCardProps> = ({
  optimization,
  onPause,
  onResume,
  onCancel,
  loading = false,
}) => {
  const progress = (optimization.current_iteration / optimization.max_iterations) * 100;

  const getStatusColor = (status: OptimizationRun['status']): 'emerald' | 'yellow' | 'blue' | 'red' => {
    switch (status) {
      case 'running':
        return 'emerald';
      case 'paused':
        return 'yellow';
      case 'completed':
        return 'blue';
      case 'failed':
        return 'red';
      default:
        return 'blue';
    }
  };

  const formatSharpeRatio = (ratio: number | undefined | null): string => {
    if (ratio == null) return 'N/A';
    return ratio.toFixed(2);
  };

  const handlePause = () => {
    if (onPause) onPause(optimization.id);
  };

  const handleResume = () => {
    if (onResume) onResume(optimization.id);
  };

  const handleCancel = () => {
    if (onCancel) onCancel(optimization.id);
  };

  return (
    <Card>
      <Flex alignItems="start" style={{ marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Title style={{ fontSize: 16, marginBottom: 0 }}>{optimization.name}</Title>
            <Badge color={getStatusColor(optimization.status)} size="xs">
              {optimization.status}
            </Badge>
          </div>
          <Text style={{ fontSize: 12, color: '#8c8c8c' }}>ID: {optimization.id}</Text>
        </div>

        <Space size="small">
          {optimization.status === 'running' && (
            <Tooltip title="Pause">
              <Button
                type="text"
                icon={<PauseCircleOutlined />}
                onClick={handlePause}
                loading={loading}
                size="small"
              />
            </Tooltip>
          )}
          {optimization.status === 'paused' && (
            <Tooltip title="Resume">
              <Button
                type="text"
                icon={<PlayCircleOutlined />}
                onClick={handleResume}
                loading={loading}
                size="small"
              />
            </Tooltip>
          )}
          {(optimization.status === 'running' || optimization.status === 'paused') && (
            <Tooltip title="Cancel">
              <Button
                type="text"
                danger
                icon={<CloseCircleOutlined />}
                onClick={handleCancel}
                loading={loading}
                size="small"
              />
            </Tooltip>
          )}
        </Space>
      </Flex>

      <div>
        <div style={{ marginBottom: 12 }}>
          <Flex justifyContent="between" style={{ marginBottom: 4 }}>
            <Text>Iteration: {optimization.current_iteration}/{optimization.max_iterations}</Text>
            <Text style={{ color: '#8c8c8c' }}>{Math.round(progress)}%</Text>
          </Flex>
          <ProgressBar value={progress} color={getStatusColor(optimization.status)} />
        </div>

        <Flex alignItems="center" style={{ backgroundColor: '#fafafa', borderRadius: 4, padding: 12, marginTop: 12 }}>
          <div style={{ flex: 1 }}>
            <Text style={{ fontSize: 12, color: '#595959', marginBottom: 4 }}>Best Sharpe Ratio</Text>
            <Metric style={{ fontSize: 24 }}>
              {formatSharpeRatio(optimization.best_sharpe_ratio)}
            </Metric>
          </div>
          {optimization.best_strategy_id && (
            <Tooltip title={`Strategy ID: ${optimization.best_strategy_id}`}>
              <Badge color="blue" size="sm">
                Best
              </Badge>
            </Tooltip>
          )}
        </Flex>

        {optimization.updated_at && (
          <Text style={{ fontSize: 12, color: '#8c8c8c', display: 'block', marginTop: 12 }}>
            Last updated: {new Date(optimization.updated_at).toLocaleString()}
          </Text>
        )}
      </div>
    </Card>
  );
};
