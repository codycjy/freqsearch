import { useCustom, useList } from '@refinedev/core';
import { Row, Col, Typography, Space } from 'antd';
import { QueueStats } from './QueueStats';
import { AgentStatus } from './AgentStatus';
import { OptimizationCard } from './OptimizationCard';
import { PerformanceChart } from './PerformanceChart';
import {
  QueueStats as QueueStatsType,
  OptimizationRun,
  Agent,
  PerformanceDataPoint,
} from '../../types/api';

const { Title } = Typography;

/**
 * Dashboard Page
 * Main admin dashboard displaying:
 * - Queue statistics (pending/running/completed/failed jobs)
 * - Active optimizations with progress
 * - Agent status panel
 * - Performance overview chart (last 24h)
 *
 * Uses Refine hooks for data fetching:
 * - useCustom for queue stats
 * - useList for optimizations and agents
 * - Real-time updates via liveProvider (when configured)
 */
export const DashboardPage = () => {
  // Fetch queue statistics
  const { data: queueStatsData, isLoading: queueStatsLoading } = useCustom<QueueStatsType>({
    url: '/backtests/queue/stats',
    method: 'get',
  });

  // Fetch active optimizations (running status)
  const { data: optimizationsData, isLoading: optimizationsLoading } = useList<OptimizationRun>({
    resource: 'optimizations',
    filters: [
      {
        field: 'status',
        operator: 'eq',
        value: 'running',
      },
    ],
    pagination: {
      pageSize: 10,
    },
    // Enable live updates
    liveMode: 'auto',
  });

  // Fetch agent status
  const { data: agentsData, isLoading: agentsLoading } = useCustom<Agent[]>({
    url: '/agents/status',
    method: 'get',
  });

  // Fetch performance data (last 24h)
  const { data: performanceData, isLoading: performanceLoading } = useCustom<PerformanceDataPoint[]>({
    url: '/optimizations/performance',
    method: 'get',
    config: {
      query: {
        period: '24h',
      },
    },
  });

  // Handle optimization control actions
  const handlePause = async (id: string) => {
    console.log('Pausing optimization:', id);
    // TODO: Implement with useUpdate hook
    // await update({
    //   resource: 'optimizations',
    //   id,
    //   values: { action: 'pause' },
    // });
  };

  const handleResume = async (id: string) => {
    console.log('Resuming optimization:', id);
    // TODO: Implement with useUpdate hook
  };

  const handleCancel = async (id: string) => {
    console.log('Canceling optimization:', id);
    // TODO: Implement with useUpdate hook or useDelete
  };

  const activeOptimizations = optimizationsData?.data || [];

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* Header */}
        <div>
          <Title level={2} style={{ margin: 0 }}>
            FreqSearch Admin Dashboard
          </Title>
          <p style={{ color: '#8c8c8c', marginTop: 4 }}>
            Real-time monitoring of backtest jobs, optimizations, and agent activity
          </p>
        </div>

        {/* Queue Statistics Cards */}
        <QueueStats stats={queueStatsData?.data} loading={queueStatsLoading} />

        {/* Main Content Grid */}
        <Row gutter={[16, 16]}>
          {/* Active Optimizations Column */}
          <Col xs={24} lg={16}>
            <div>
              <Title level={4} style={{ marginBottom: 16 }}>
                Active Optimizations
              </Title>
              {optimizationsLoading ? (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  {[1, 2].map((i) => (
                    <div
                      key={i}
                      style={{
                        height: 192,
                        backgroundColor: '#f5f5f5',
                        borderRadius: 4
                      }}
                    />
                  ))}
                </Space>
              ) : activeOptimizations.length > 0 ? (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  {activeOptimizations.map((optimization) => (
                    <OptimizationCard
                      key={optimization.id}
                      optimization={optimization}
                      onPause={handlePause}
                      onResume={handleResume}
                      onCancel={handleCancel}
                    />
                  ))}
                </Space>
              ) : (
                <div style={{
                  padding: 32,
                  textAlign: 'center',
                  backgroundColor: '#fafafa',
                  borderRadius: 8,
                  border: '2px dashed #e8e8e8',
                }}>
                  <svg
                    style={{
                      margin: '0 auto',
                      display: 'block',
                      width: 48,
                      height: 48,
                      color: '#bfbfbf',
                    }}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                    />
                  </svg>
                  <p style={{ marginTop: 8, color: '#595959' }}>No active optimizations</p>
                  <p style={{ fontSize: 14, color: '#8c8c8c' }}>
                    Start a new optimization to see progress here
                  </p>
                </div>
              )}
            </div>
          </Col>

          {/* Agent Status Column */}
          <Col xs={24} lg={8}>
            <AgentStatus agents={agentsData?.data} loading={agentsLoading} />
          </Col>
        </Row>

        {/* Performance Overview Chart */}
        <PerformanceChart data={performanceData?.data} loading={performanceLoading} />
      </Space>
    </div>
  );
};
