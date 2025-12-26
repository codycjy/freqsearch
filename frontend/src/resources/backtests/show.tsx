import React from 'react';
import { useShow, useNavigation } from '@refinedev/core';
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
  Table,
  Statistic,
  Button,
  Divider,
  Collapse,
} from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import type { BacktestJob, BacktestResult, JobStatus } from '@providers/types';
import { ProfitCurve } from '@components/charts/ProfitCurve';
import { DrawdownChart } from '@components/charts/DrawdownChart';

const { Text } = Typography;

/**
 * Status color mapping
 */
const STATUS_COLORS: Record<JobStatus, string> = {
  JOB_STATUS_UNSPECIFIED: 'default',
  JOB_STATUS_PENDING: 'blue',
  JOB_STATUS_RUNNING: 'orange',
  JOB_STATUS_COMPLETED: 'green',
  JOB_STATUS_FAILED: 'red',
  JOB_STATUS_CANCELLED: 'default',
};

const STATUS_TEXT: Record<JobStatus, string> = {
  JOB_STATUS_UNSPECIFIED: 'Unknown',
  JOB_STATUS_PENDING: 'Pending',
  JOB_STATUS_RUNNING: 'Running',
  JOB_STATUS_COMPLETED: 'Completed',
  JOB_STATUS_FAILED: 'Failed',
  JOB_STATUS_CANCELLED: 'Cancelled',
};

/**
 * Format percentage value
 */
const formatPercent = (value: number | undefined | null): string => {
  if (value === undefined || value === null) return 'N/A';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
};

/**
 * Format currency value
 */
const formatCurrency = (value: number | undefined | null): string => {
  if (value === undefined || value === null) return 'N/A';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value);
};

/**
 * Format duration in minutes to hours and minutes
 */
const formatDuration = (minutes: number | undefined | null): string => {
  if (minutes === undefined || minutes === null) return 'N/A';
  const hours = Math.floor(minutes / 60);
  const mins = Math.floor(minutes % 60);
  return `${hours}h ${mins}m`;
};

/**
 * Parse trades from JSON string
 */
const parseTrades = (tradesJson?: string): any[] => {
  if (!tradesJson) return [];
  try {
    return JSON.parse(tradesJson);
  } catch {
    return [];
  }
};

/**
 * BacktestShow Component
 *
 * Displays detailed backtest results including:
 * - Job information and status
 * - Performance metrics
 * - Profit and drawdown charts
 * - Trade list
 * - Configuration details
 */
// Extended type that includes result from the API response
interface BacktestJobWithResult extends BacktestJob {
  result?: BacktestResult;
}

export const BacktestShow: React.FC = () => {
  const { show: showResource } = useNavigation();
  const { queryResult } = useShow<BacktestJobWithResult>({
    liveMode: 'auto', // Enable real-time updates
  });

  const { data: jobData, isLoading } = queryResult;
  const job = jobData?.data;
  const result = job?.result;
  const trades = parseTrades(result?.trades_json);

  return (
    <Show isLoading={isLoading}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* Job Information */}
        <Card title="Backtest Job Information">
          <Descriptions column={2} bordered>
            <Descriptions.Item label="Job ID">
              <Text code copyable={{ text: job?.id }}>
                {job?.id}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color={STATUS_COLORS[job?.status || 'JOB_STATUS_UNSPECIFIED']}>
                {STATUS_TEXT[job?.status || 'JOB_STATUS_UNSPECIFIED']}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Strategy ID">
              <Space>
                <Text code copyable={{ text: job?.strategy_id }}>
                  {job?.strategy_id}
                </Text>
                <Button
                  type="link"
                  size="small"
                  icon={<LinkOutlined />}
                  onClick={() => showResource('strategies', job?.strategy_id || '')}
                >
                  View Strategy
                </Button>
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="Priority">
              <Tag color={job?.priority && job.priority > 5 ? 'red' : 'default'}>
                {job?.priority}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Created">
              <DateField value={job?.created_at} format="YYYY-MM-DD HH:mm:ss" />
            </Descriptions.Item>
            <Descriptions.Item label="Started">
              {job?.started_at ? (
                <DateField value={job.started_at} format="YYYY-MM-DD HH:mm:ss" />
              ) : (
                <Text type="secondary">Not started</Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Completed">
              {job?.completed_at ? (
                <DateField value={job.completed_at} format="YYYY-MM-DD HH:mm:ss" />
              ) : (
                <Text type="secondary">Not completed</Text>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Optimization Run">
              {job?.optimization_run_id ? (
                <Space>
                  <Text code copyable={{ text: job.optimization_run_id }}>
                    {job.optimization_run_id}
                  </Text>
                  <Button
                    type="link"
                    size="small"
                    icon={<LinkOutlined />}
                    onClick={() =>
                      showResource('optimizations', job.optimization_run_id || '')
                    }
                  >
                    View Run
                  </Button>
                </Space>
              ) : (
                <Text type="secondary">Manual run</Text>
              )}
            </Descriptions.Item>
          </Descriptions>

          {job?.error_message && (
            <Alert
              message="Error"
              description={job.error_message}
              type="error"
              showIcon
              style={{ marginTop: 16 }}
            />
          )}
        </Card>

        {/* Results - Only show if completed */}
        {job?.status === 'JOB_STATUS_COMPLETED' && result && (
          <>
            {/* Key Metrics */}
            <Card title="Performance Metrics">
              <Row gutter={[16, 16]}>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Statistic
                    title="Total Profit"
                    value={result.profit_pct}
                    precision={2}
                    valueStyle={{
                      color: result.profit_pct >= 0 ? '#3f8600' : '#cf1322',
                    }}
                    prefix={result.profit_pct >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                    suffix="%"
                  />
                  <Text type="secondary">{formatCurrency(result.profit_total)}</Text>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Statistic
                    title="Sharpe Ratio"
                    value={result.sharpe_ratio}
                    precision={2}
                    valueStyle={{
                      color: result.sharpe_ratio >= 1 ? '#3f8600' : '#cf1322',
                    }}
                  />
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Statistic
                    title="Sortino Ratio"
                    value={result.sortino_ratio}
                    precision={2}
                    valueStyle={{
                      color: result.sortino_ratio >= 1 ? '#3f8600' : '#cf1322',
                    }}
                  />
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Statistic
                    title="Calmar Ratio"
                    value={result.calmar_ratio}
                    precision={2}
                  />
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Statistic
                    title="Win Rate"
                    value={result.win_rate}
                    precision={2}
                    suffix="%"
                    valueStyle={{
                      color: result.win_rate >= 50 ? '#3f8600' : '#cf1322',
                    }}
                  />
                  <Text type="secondary">
                    {result.winning_trades}W / {result.losing_trades}L
                  </Text>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Statistic
                    title="Total Trades"
                    value={result.total_trades}
                  />
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Statistic
                    title="Max Drawdown"
                    value={result.max_drawdown_pct}
                    precision={2}
                    suffix="%"
                    valueStyle={{ color: '#cf1322' }}
                    prefix={<ArrowDownOutlined />}
                  />
                  <Text type="secondary">{formatCurrency(result.max_drawdown)}</Text>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Statistic
                    title="Profit Factor"
                    value={result.profit_factor}
                    precision={2}
                    valueStyle={{
                      color: result.profit_factor >= 1 ? '#3f8600' : '#cf1322',
                    }}
                  />
                </Col>
              </Row>

              <Divider />

              <Row gutter={[16, 16]}>
                <Col span={24} md={12}>
                  <Descriptions column={1} size="small">
                    <Descriptions.Item label="Avg Trade Duration">
                      {formatDuration(result.avg_trade_duration_minutes)}
                    </Descriptions.Item>
                    <Descriptions.Item label="Avg Profit/Trade">
                      {formatCurrency(result.avg_profit_per_trade)}
                    </Descriptions.Item>
                  </Descriptions>
                </Col>
                <Col span={24} md={12}>
                  <Descriptions column={1} size="small">
                    <Descriptions.Item label="Best Trade">
                      <Text style={{ color: '#3f8600' }}>
                        {formatPercent(result.best_trade_pct)}
                      </Text>
                    </Descriptions.Item>
                    <Descriptions.Item label="Worst Trade">
                      <Text style={{ color: '#cf1322' }}>
                        {formatPercent(result.worst_trade_pct)}
                      </Text>
                    </Descriptions.Item>
                  </Descriptions>
                </Col>
              </Row>
            </Card>

            {/* Charts */}
            <Row gutter={[16, 16]}>
              <Col span={24} lg={12}>
                <Card title="Profit Curve" bordered={false}>
                  <ProfitCurve trades={trades} />
                </Card>
              </Col>
              <Col span={24} lg={12}>
                <Card title="Drawdown" bordered={false}>
                  <DrawdownChart trades={trades} />
                </Card>
              </Col>
            </Row>

            {/* Pair Results */}
            {result.pair_results && result.pair_results.length > 0 && (
              <Card title="Results by Trading Pair">
                <Table
                  dataSource={result.pair_results}
                  rowKey="pair"
                  pagination={false}
                  size="small"
                >
                  <Table.Column dataIndex="pair" title="Pair" />
                  <Table.Column
                    dataIndex="trades"
                    title="Trades"
                    align="center"
                  />
                  <Table.Column
                    dataIndex="profit_pct"
                    title="Profit %"
                    align="right"
                    render={(value: number) => (
                      <Text style={{ color: value >= 0 ? '#3f8600' : '#cf1322' }}>
                        {formatPercent(value)}
                      </Text>
                    )}
                    sorter={(a, b) => a.profit_pct - b.profit_pct}
                  />
                  <Table.Column
                    dataIndex="win_rate"
                    title="Win Rate"
                    align="right"
                    render={(value: number) => value != null ? `${value.toFixed(2)}%` : 'N/A'}
                    sorter={(a, b) => (a.win_rate ?? 0) - (b.win_rate ?? 0)}
                  />
                  <Table.Column
                    dataIndex="avg_duration_minutes"
                    title="Avg Duration"
                    align="right"
                    render={(value: number) => formatDuration(value)}
                  />
                </Table>
              </Card>
            )}

            {/* Trade List */}
            {trades.length > 0 && (
              <Card title={`Trades (${trades.length})`}>
                <Table
                  dataSource={trades}
                  rowKey={(record, index) => `${record.pair}-${index}`}
                  pagination={{
                    pageSize: 20,
                    showSizeChanger: true,
                    pageSizeOptions: ['10', '20', '50', '100'],
                    showTotal: (total) => `Total ${total} trades`,
                  }}
                  size="small"
                  scroll={{ x: 1200 }}
                >
                  <Table.Column
                    dataIndex="pair"
                    title="Pair"
                    width={120}
                    fixed="left"
                  />
                  <Table.Column
                    dataIndex="open_date"
                    title="Open Date"
                    width={180}
                    render={(value: string) => (
                      <DateField value={value} format="YYYY-MM-DD HH:mm" />
                    )}
                  />
                  <Table.Column
                    dataIndex="close_date"
                    title="Close Date"
                    width={180}
                    render={(value: string) => (
                      <DateField value={value} format="YYYY-MM-DD HH:mm" />
                    )}
                  />
                  <Table.Column
                    dataIndex="profit_pct"
                    title="Profit %"
                    align="right"
                    width={100}
                    render={(value: number) => (
                      <Text style={{ color: value >= 0 ? '#3f8600' : '#cf1322' }}>
                        {formatPercent(value)}
                      </Text>
                    )}
                    sorter={(a, b) => a.profit_pct - b.profit_pct}
                  />
                  <Table.Column
                    dataIndex="profit_abs"
                    title="Profit"
                    align="right"
                    width={120}
                    render={(value: number) => formatCurrency(value)}
                  />
                  <Table.Column
                    dataIndex="trade_duration"
                    title="Duration"
                    align="right"
                    width={120}
                  />
                  <Table.Column
                    dataIndex="buy_reason"
                    title="Entry"
                    width={150}
                    ellipsis
                  />
                  <Table.Column
                    dataIndex="sell_reason"
                    title="Exit"
                    width={150}
                    ellipsis
                  />
                </Table>
              </Card>
            )}
          </>
        )}

        {/* Backtest Configuration */}
        {job?.config && (
          <Card title="Configuration">
            <Descriptions column={2} bordered>
              <Descriptions.Item label="Exchange">
                {job.config.exchange}
              </Descriptions.Item>
              <Descriptions.Item label="Timeframe">
                {job.config.timeframe}
              </Descriptions.Item>
              <Descriptions.Item label="Pairs" span={2}>
                <Space wrap>
                  {job.config.pairs.map((pair) => (
                    <Tag key={pair}>{pair}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="Time Range Start">
                <DateField value={job.config.timerange_start} format="YYYY-MM-DD" />
              </Descriptions.Item>
              <Descriptions.Item label="Time Range End">
                <DateField value={job.config.timerange_end} format="YYYY-MM-DD" />
              </Descriptions.Item>
              <Descriptions.Item label="Starting Balance">
                {formatCurrency(job.config.dry_run_wallet)}
              </Descriptions.Item>
              <Descriptions.Item label="Max Open Trades">
                {job.config.max_open_trades}
              </Descriptions.Item>
              <Descriptions.Item label="Stake Amount">
                {job.config.stake_amount}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        )}

        {/* Error Information - Show for failed backtests */}
        {job?.status === 'JOB_STATUS_FAILED' && (
          <Card title="Error Details" style={{ marginTop: 16 }}>
            {job?.error_message && (
              <Alert
                type="error"
                message="Backtest Failed"
                description={job.error_message}
                showIcon
                style={{ marginBottom: 16 }}
              />
            )}
            {!job?.error_message && !result?.raw_log && (
              <Alert
                type="error"
                message="Backtest Failed"
                description="The backtest job failed but no error details are available. This might indicate a system-level issue or timeout."
                showIcon
                style={{ marginBottom: 16 }}
              />
            )}
            {result?.raw_log && (
              <Collapse>
                <Collapse.Panel header="Raw Execution Log" key="log">
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, maxHeight: 400, overflow: 'auto' }}>
                    {result.raw_log}
                  </pre>
                </Collapse.Panel>
              </Collapse>
            )}
          </Card>
        )}
      </Space>
    </Show>
  );
};
