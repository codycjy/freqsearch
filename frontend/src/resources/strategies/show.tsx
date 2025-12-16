import React from 'react';
import { Show } from '@refinedev/antd';
import { useShow, useCustom } from '@refinedev/core';
import {
  Typography,
  Card,
  Row,
  Col,
  Statistic,
  Tag,
  Space,
  Divider,
  Button,
  Table,
  Alert,
} from 'antd';
import {
  LineChartOutlined,
  ThunderboltOutlined,
  TrophyOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { StrategyWithMetrics } from '@providers/types';

const { Title, Text, Paragraph } = Typography;

/**
 * StrategyShow Component
 *
 * Displays detailed strategy information:
 * - Strategy metadata and code (with syntax highlighting)
 * - Performance metrics in cards
 * - Strategy lineage (parent/children relationships)
 * - Recent backtests for this strategy
 * - Action to run new backtest
 */
export const StrategyShow: React.FC = () => {
  const navigate = useNavigate();
  const { queryResult } = useShow<StrategyWithMetrics>();
  const { data, isLoading } = queryResult;

  const record = data?.data;
  const strategy = record?.strategy;
  const metrics = record?.best_result;

  // Fetch recent backtests for this strategy
  const { data: backtestsData } = useCustom({
    url: `backtests`,
    method: 'get',
    config: {
      query: {
        strategy_id: strategy?.id,
        limit: 5,
        sort: 'created_at',
        order: 'desc',
      },
    },
    queryOptions: {
      enabled: !!strategy?.id,
    },
  });

  const backtests = backtestsData?.data?.data || [];

  // Fetch parent strategy if exists
  const { data: parentData } = useCustom({
    url: `strategies/${strategy?.parent_id}`,
    method: 'get',
    queryOptions: {
      enabled: !!strategy?.parent_id,
    },
  });

  const parentStrategy = parentData?.data?.data?.strategy;

  // Fetch child strategies
  const { data: childrenData } = useCustom({
    url: `strategies`,
    method: 'get',
    config: {
      query: {
        parent_id: strategy?.id,
      },
    },
    queryOptions: {
      enabled: !!strategy?.id,
    },
  });

  const childStrategies = childrenData?.data?.data || [];

  const handleRunBacktest = () => {
    navigate(`/backtests/create?strategy_id=${strategy?.id}`);
  };

  return (
    <Show
      isLoading={isLoading}
      headerButtons={({ defaultButtons }) => (
        <>
          {defaultButtons}
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={handleRunBacktest}
          >
            Run Backtest
          </Button>
        </>
      )}
    >
      {/* Performance Metrics */}
      {metrics && (
        <Card style={{ marginBottom: 24 }}>
          <Title level={5}>Performance Metrics</Title>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} lg={4}>
              <Statistic
                title="Sharpe Ratio"
                value={metrics.sharpe_ratio}
                precision={2}
                valueStyle={{
                  color: metrics.sharpe_ratio > 0 ? '#3f8600' : '#cf1322',
                }}
                prefix={<LineChartOutlined />}
              />
            </Col>
            <Col xs={24} sm={12} lg={4}>
              <Statistic
                title="Profit %"
                value={metrics.profit_pct}
                precision={2}
                suffix="%"
                valueStyle={{
                  color: metrics.profit_pct > 0 ? '#3f8600' : '#cf1322',
                }}
                prefix={<TrophyOutlined />}
              />
            </Col>
            <Col xs={24} sm={12} lg={4}>
              <Statistic
                title="Win Rate"
                value={metrics.win_rate * 100}
                precision={1}
                suffix="%"
              />
            </Col>
            <Col xs={24} sm={12} lg={4}>
              <Statistic
                title="Total Trades"
                value={metrics.total_trades}
              />
            </Col>
            <Col xs={24} sm={12} lg={4}>
              <Statistic
                title="Max Drawdown"
                value={metrics.max_drawdown_pct}
                precision={2}
                suffix="%"
                valueStyle={{ color: '#cf1322' }}
                prefix={<WarningOutlined />}
              />
            </Col>
            <Col xs={24} sm={12} lg={4}>
              <Statistic
                title="Profit Factor"
                value={metrics.profit_factor}
                precision={2}
              />
            </Col>
          </Row>
        </Card>
      )}

      {/* Strategy Information */}
      <Card style={{ marginBottom: 24 }}>
        <Title level={5}>Strategy Information</Title>
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Text strong>Name: </Text>
            <Text>{strategy?.name}</Text>
          </Col>
          <Col span={24}>
            <Text strong>Description: </Text>
            <Paragraph>{strategy?.description || 'No description provided'}</Paragraph>
          </Col>
          <Col span={12}>
            <Text strong>Generation: </Text>
            <Tag color="blue">{strategy?.generation}</Tag>
          </Col>
          <Col span={12}>
            <Text strong>Backtests Run: </Text>
            <Tag color="green">{record?.backtest_count || 0}</Tag>
          </Col>
          <Col span={12}>
            <Text strong>Created: </Text>
            <Text type="secondary">
              {strategy?.created_at && new Date(strategy.created_at).toLocaleString()}
            </Text>
          </Col>
          <Col span={12}>
            <Text strong>Updated: </Text>
            <Text type="secondary">
              {strategy?.updated_at && new Date(strategy.updated_at).toLocaleString()}
            </Text>
          </Col>
        </Row>

        {strategy?.tags && (
          <>
            <Divider />
            <div>
              <Text strong>Tags: </Text>
              <Space wrap style={{ marginTop: 8 }}>
                {strategy.tags.strategy_type?.map((tag: string) => (
                  <Tag key={tag} color="blue">
                    {tag}
                  </Tag>
                ))}
                {strategy.tags.risk_level && (
                  <Tag color="orange">{strategy.tags.risk_level}</Tag>
                )}
                {strategy.tags.trading_style && (
                  <Tag color="purple">{strategy.tags.trading_style}</Tag>
                )}
                {strategy.tags.indicators?.map((tag: string) => (
                  <Tag key={tag} color="cyan">
                    {tag}
                  </Tag>
                ))}
                {strategy.tags.market_regime?.map((tag: string) => (
                  <Tag key={tag} color="geekblue">
                    {tag}
                  </Tag>
                ))}
              </Space>
            </div>
          </>
        )}
      </Card>

      {/* Strategy Lineage */}
      {(parentStrategy || childStrategies.length > 0) && (
        <Card style={{ marginBottom: 24 }}>
          <Title level={5}>Strategy Lineage</Title>

          {parentStrategy && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>Parent Strategy: </Text>
              <Button
                type="link"
                onClick={() => navigate(`/strategies/show/${strategy?.parent_id}`)}
              >
                {parentStrategy.name}
              </Button>
            </div>
          )}

          {childStrategies.length > 0 && (
            <div>
              <Text strong>Child Strategies ({childStrategies.length}): </Text>
              <Space wrap style={{ marginTop: 8 }}>
                {childStrategies.map((child: any) => (
                  <Button
                    key={child.strategy.id}
                    type="link"
                    onClick={() => navigate(`/strategies/show/${child.strategy.id}`)}
                  >
                    {child.strategy.name} (Gen {child.strategy.generation})
                  </Button>
                ))}
              </Space>
            </div>
          )}
        </Card>
      )}

      {/* Strategy Code */}
      <Card style={{ marginBottom: 24 }}>
        <Title level={5}>Strategy Code</Title>
        <Alert
          message="This is the FreqTrade strategy implementation code"
          type="info"
          style={{ marginBottom: 16 }}
        />
        <pre
          style={{
            background: '#f5f5f5',
            padding: 16,
            borderRadius: 4,
            overflow: 'auto',
            maxHeight: 500,
          }}
        >
          <code>{strategy?.code}</code>
        </pre>
      </Card>

      {/* Recent Backtests */}
      <Card>
        <Title level={5}>Recent Backtests</Title>
        {backtests.length === 0 ? (
          <Alert
            message="No backtests run yet"
            description="Click 'Run Backtest' to test this strategy"
            type="info"
          />
        ) : (
          <Table
            dataSource={backtests}
            rowKey="id"
            pagination={false}
            size="small"
          >
            <Table.Column
              title="Status"
              dataIndex="status"
              render={(status) => {
                const colors: Record<string, string> = {
                  JOB_STATUS_PENDING: 'default',
                  JOB_STATUS_RUNNING: 'processing',
                  JOB_STATUS_COMPLETED: 'success',
                  JOB_STATUS_FAILED: 'error',
                };
                return <Tag color={colors[status] || 'default'}>{status.replace('JOB_STATUS_', '')}</Tag>;
              }}
            />
            <Table.Column
              title="Created"
              dataIndex="created_at"
              render={(value) => new Date(value).toLocaleString()}
            />
            <Table.Column
              title="Actions"
              render={(_, record: any) => (
                <Button
                  type="link"
                  size="small"
                  onClick={() => navigate(`/backtests/show/${record.id}`)}
                >
                  View
                </Button>
              )}
            />
          </Table>
        )}
      </Card>
    </Show>
  );
};
