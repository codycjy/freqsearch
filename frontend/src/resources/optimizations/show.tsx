import { useShow, useNavigation } from '@refinedev/core';
import { Show, DateField } from '@refinedev/antd';
import {
  Typography,
  Card,
  Row,
  Col,
  Descriptions,
  Tag,
  Progress,
  Statistic,
  Table,
  Button,
  Spin,
} from 'antd';
import {
  RocketOutlined,
  TrophyOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import type { OptimizationRun, OptimizationIteration, OptimizationStatus } from '@providers/types';
import { OptimizationControlPanel } from './control';
import { MetricsComparison } from '@components/charts/MetricsComparison';

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

export const OptimizationShow = () => {
  const { queryResult } = useShow<OptimizationRun>({
    liveMode: 'auto',
  });
  const { data, isLoading } = queryResult;
  const record = data?.data;
  const { show } = useNavigation();

  // Use iterations from the record (populated by dataProvider)
  const iterations = record?.iterations || [];
  const iterationsLoading = queryResult.isLoading;

  if (isLoading || !record) {
    return (
      <Show>
        <Spin size="large" />
      </Show>
    );
  }

  const progress = (record.current_iteration / record.max_iterations) * 100;

  const iterationColumns = [
    {
      title: 'Iteration',
      dataIndex: 'iteration_number',
      key: 'iteration_number',
      sorter: (a: OptimizationIteration, b: OptimizationIteration) =>
        a.iteration_number - b.iteration_number,
    },
    {
      title: 'Strategy ID',
      dataIndex: 'strategy_id',
      key: 'strategy_id',
      render: (strategyId: string) => (
        <Button
          type="link"
          size="small"
          icon={<LinkOutlined />}
          onClick={() => show('strategies', strategyId)}
        >
          {strategyId.substring(0, 12)}...
        </Button>
      ),
    },
    {
      title: 'Sharpe Ratio',
      key: 'sharpe_ratio',
      render: (_: any, record: OptimizationIteration) => (
        <Text strong style={{ color: record.is_best ? '#52c41a' : undefined }}>
          {record.result?.sharpe_ratio?.toFixed(3) || 'N/A'}
        </Text>
      ),
      sorter: (a: OptimizationIteration, b: OptimizationIteration) =>
        (a.result?.sharpe_ratio || 0) - (b.result?.sharpe_ratio || 0),
    },
    {
      title: 'Profit %',
      key: 'profit_pct',
      render: (_: any, record: OptimizationIteration) => (
        <Text>{record.result?.profit_pct?.toFixed(2) || 'N/A'}%</Text>
      ),
      sorter: (a: OptimizationIteration, b: OptimizationIteration) =>
        (a.result?.profit_pct || 0) - (b.result?.profit_pct || 0),
    },
    {
      title: 'Drawdown %',
      key: 'drawdown_pct',
      render: (_: any, record: OptimizationIteration) => (
        <Text type="danger">{record.result?.max_drawdown_pct?.toFixed(2) || 'N/A'}%</Text>
      ),
    },
    {
      title: 'Trades',
      key: 'trades',
      render: (_: any, record: OptimizationIteration) => record.result?.total_trades || 0,
    },
    {
      title: 'Status',
      key: 'is_best',
      render: (_: any, record: OptimizationIteration) =>
        record.is_best ? <Tag color="gold">Best</Tag> : null,
      filters: [
        { text: 'Best Only', value: true },
        { text: 'All', value: false },
      ],
      onFilter: (value: any, record: OptimizationIteration) =>
        value === true ? (record.is_best === true) : true,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
  ];

  return (
    <Show
      isLoading={isLoading}
      headerButtons={({ defaultButtons }) => (
        <>
          {defaultButtons}
          {(record.status === 'OPTIMIZATION_STATUS_RUNNING' ||
            record.status === 'OPTIMIZATION_STATUS_PAUSED') && (
            <OptimizationControlPanel
              optimizationId={record.id}
              currentStatus={record.status}
              showLabels
            />
          )}
        </>
      )}
    >
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card>
            <Descriptions column={2} bordered>
              <Descriptions.Item label="Name">
                <Text strong>{record.name}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Status">
                <Tag color={statusColors[record.status]}>{statusLabels[record.status]}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Base Strategy">
                <Button
                  type="link"
                  size="small"
                  icon={<LinkOutlined />}
                  onClick={() => show('strategies', record.base_strategy_id)}
                >
                  {record.base_strategy_id}
                </Button>
              </Descriptions.Item>
              <Descriptions.Item label="Optimization Mode">
                <Tag color="blue">
                  {record.config.mode.replace('OPTIMIZATION_MODE_', '').replace(/_/g, ' ')}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Created At">
                <DateField value={record.created_at} format="YYYY-MM-DD HH:mm:ss" />
              </Descriptions.Item>
              <Descriptions.Item label="Updated At">
                <DateField value={record.updated_at} format="YYYY-MM-DD HH:mm:ss" />
              </Descriptions.Item>
              {record.completed_at && (
                <Descriptions.Item label="Completed At">
                  <DateField value={record.completed_at} format="YYYY-MM-DD HH:mm:ss" />
                </Descriptions.Item>
              )}
              {record.termination_reason && (
                <Descriptions.Item label="Termination Reason" span={2}>
                  <Text>{record.termination_reason}</Text>
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card>
            <Statistic
              title="Progress"
              value={record.current_iteration}
              suffix={`/ ${record.max_iterations}`}
              prefix={<RocketOutlined />}
            />
            <Progress
              percent={Math.round(progress)}
              status={
                record.status === 'OPTIMIZATION_STATUS_RUNNING'
                  ? 'active'
                  : record.status === 'OPTIMIZATION_STATUS_COMPLETED'
                  ? 'success'
                  : record.status === 'OPTIMIZATION_STATUS_FAILED'
                  ? 'exception'
                  : 'normal'
              }
              style={{ marginTop: 16 }}
            />
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card>
            <Statistic
              title="Best Sharpe Ratio"
              value={record.best_result?.sharpe_ratio || 0}
              precision={3}
              prefix={<TrophyOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
            {record.best_strategy_id && (
              <Button
                type="link"
                size="small"
                icon={<LinkOutlined />}
                onClick={() => show('strategies', record.best_strategy_id!)}
                style={{ marginTop: 16 }}
              >
                View Best Strategy
              </Button>
            )}
          </Card>
        </Col>

        {record.best_result && (
          <Col span={24}>
            <Card title="Best Result Metrics">
              <Row gutter={16}>
                <Col xs={12} sm={8} md={6}>
                  <Statistic
                    title="Profit %"
                    value={record.best_result.profit_pct}
                    precision={2}
                    suffix="%"
                  />
                </Col>
                <Col xs={12} sm={8} md={6}>
                  <Statistic
                    title="Max Drawdown %"
                    value={record.best_result.max_drawdown_pct}
                    precision={2}
                    suffix="%"
                    valueStyle={{ color: '#cf1322' }}
                  />
                </Col>
                <Col xs={12} sm={8} md={6}>
                  <Statistic
                    title="Total Trades"
                    value={record.best_result.total_trades}
                  />
                </Col>
                <Col xs={12} sm={8} md={6}>
                  <Statistic
                    title="Win Rate"
                    value={record.best_result.win_rate}
                    precision={1}
                    suffix="%"
                  />
                </Col>
              </Row>
            </Card>
          </Col>
        )}

        {iterations.length > 0 && (
          <>
            <Col span={24}>
              <MetricsComparison iterations={iterations} />
            </Col>

            <Col span={24}>
              <Card title="Iteration History" loading={iterationsLoading}>
                <Table
                  dataSource={iterations}
                  columns={iterationColumns}
                  rowKey="iteration_number"
                  pagination={{ pageSize: 10, showSizeChanger: true }}
                  rowClassName={(record) => (record.is_best ? 'best-iteration' : '')}
                />
              </Card>
            </Col>
          </>
        )}

        <Col span={24}>
          <Card title="Configuration">
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="Exchange">
                {record.config.backtest_config.exchange}
              </Descriptions.Item>
              <Descriptions.Item label="Trading Pairs">
                {record.config.backtest_config.pairs.join(', ')}
              </Descriptions.Item>
              <Descriptions.Item label="Timeframe">
                {record.config.backtest_config.timeframe}
              </Descriptions.Item>
              <Descriptions.Item label="Time Range">
                {record.config.backtest_config.timerange_start} to{' '}
                {record.config.backtest_config.timerange_end}
              </Descriptions.Item>
              <Descriptions.Item label="Criteria">
                Min Sharpe: {record.config.criteria.min_sharpe} | Min Profit:{' '}
                {record.config.criteria.min_profit_pct}% | Max Drawdown:{' '}
                {record.config.criteria.max_drawdown_pct}% | Min Trades:{' '}
                {record.config.criteria.min_trades}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>

      <style>{`
        .best-iteration {
          background-color: #fffbe6;
        }
        .best-iteration:hover {
          background-color: #fff7cc !important;
        }
      `}</style>
    </Show>
  );
};
