import React, { useState, useEffect } from 'react';
import { useCreate, useNavigation, useList } from '@refinedev/core';
import { useSearchParams } from 'react-router-dom';
import { Create } from '@refinedev/antd';
import {
  Form,
  Input,
  Select,
  DatePicker,
  InputNumber,
  Card,
  Space,
  Alert,
  Typography,
  Row,
  Col,
} from 'antd';
import {
  InfoCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { CreateBacktestPayload, BacktestConfig, StrategyWithMetrics } from '@providers/types';
import dayjs, { Dayjs } from 'dayjs';

const { Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;

/**
 * Common trading pairs for quick selection
 */
const COMMON_PAIRS = [
  'BTC/USDT',
  'ETH/USDT',
  'BNB/USDT',
  'SOL/USDT',
  'ADA/USDT',
  'XRP/USDT',
  'DOGE/USDT',
  'DOT/USDT',
  'MATIC/USDT',
  'AVAX/USDT',
];

/**
 * Common timeframes
 */
const TIMEFRAMES = [
  { label: '1 minute', value: '1m' },
  { label: '5 minutes', value: '5m' },
  { label: '15 minutes', value: '15m' },
  { label: '30 minutes', value: '30m' },
  { label: '1 hour', value: '1h' },
  { label: '4 hours', value: '4h' },
  { label: '1 day', value: '1d' },
  { label: '1 week', value: '1w' },
];

/**
 * Common exchanges
 */
const EXCHANGES = [
  { label: 'Binance', value: 'binance' },
  { label: 'Coinbase Pro', value: 'coinbasepro' },
  { label: 'Kraken', value: 'kraken' },
  { label: 'Bitfinex', value: 'bitfinex' },
  { label: 'FTX', value: 'ftx' },
];

/**
 * Priority levels
 */
const PRIORITIES = [
  { label: 'Low (1)', value: 1, color: 'default' },
  { label: 'Normal (3)', value: 3, color: 'blue' },
  { label: 'High (5)', value: 5, color: 'orange' },
  { label: 'Critical (10)', value: 10, color: 'red' },
];

/**
 * Calculate estimated runtime based on configuration
 */
const estimateRuntime = (
  pairs: string[],
  timeframe: string,
  dateRange: [Dayjs, Dayjs] | null
): string => {
  if (!pairs.length || !timeframe || !dateRange) {
    return 'Select configuration to estimate';
  }

  // Simple estimation logic (this would be more sophisticated in production)
  const days = dateRange[1].diff(dateRange[0], 'days');
  const pairCount = pairs.length;

  let multiplier = 1;
  switch (timeframe) {
    case '1m':
      multiplier = 3;
      break;
    case '5m':
      multiplier = 2;
      break;
    case '15m':
    case '30m':
      multiplier = 1.5;
      break;
    case '1h':
      multiplier = 1;
      break;
    case '4h':
      multiplier = 0.5;
      break;
    default:
      multiplier = 0.3;
  }

  const estimatedMinutes = Math.ceil((days * pairCount * multiplier) / 10);

  if (estimatedMinutes < 60) {
    return `~${estimatedMinutes} minutes`;
  } else {
    const hours = Math.floor(estimatedMinutes / 60);
    const mins = estimatedMinutes % 60;
    return `~${hours}h ${mins}m`;
  }
};

/**
 * BacktestCreate Component
 *
 * Form to submit a new backtest job with:
 * - Strategy selection
 * - Trading configuration (exchange, pairs, timeframe, date range)
 * - Advanced options (priority, wallet size, max trades)
 * - Runtime estimation
 */
export const BacktestCreate: React.FC = () => {
  const [form] = Form.useForm();
  const { mutate, isLoading } = useCreate<CreateBacktestPayload>();
  const { push } = useNavigation();
  const [searchParams] = useSearchParams();

  const [selectedPairs, setSelectedPairs] = useState<string[]>([]);
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('');
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);

  // Get strategy_id from URL params (when coming from strategy page)
  const strategyIdFromUrl = searchParams.get('strategy_id');

  // Fetch available strategies
  const { data: strategiesData, isLoading: strategiesLoading } = useList<StrategyWithMetrics>({
    resource: 'strategies',
    pagination: {
      pageSize: 100,
    },
  });

  const strategies = strategiesData?.data || [];

  // Set strategy_id from URL params when available
  useEffect(() => {
    if (strategyIdFromUrl) {
      form.setFieldsValue({ strategy_id: strategyIdFromUrl });
    }
  }, [strategyIdFromUrl, form]);

  const handleSubmit = (values: any) => {
    const config: BacktestConfig = {
      exchange: values.exchange,
      pairs: values.pairs,
      timeframe: values.timeframe,
      timerange_start: values.date_range[0].format('YYYY-MM-DD'),
      timerange_end: values.date_range[1].format('YYYY-MM-DD'),
      dry_run_wallet: values.dry_run_wallet || 10000,
      max_open_trades: values.max_open_trades || 3,
      stake_amount: values.stake_amount || 'unlimited',
    };

    const payload: CreateBacktestPayload = {
      strategy_id: values.strategy_id,
      config,
      priority: values.priority || 3,
    };

    mutate(
      {
        resource: 'backtests',
        values: payload,
      },
      {
        onSuccess: (data: any) => {
          const jobId = data?.data?.id || data?.id;
          if (jobId) {
            push(`/backtests/show/${jobId}`);
          }
        },
      }
    );
  };

  return (
    <Create
      isLoading={isLoading}
      saveButtonProps={{
        loading: isLoading,
        onClick: () => form.submit(),
      }}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          exchange: 'binance',
          timeframe: '1h',
          priority: 3,
          dry_run_wallet: 10000,
          max_open_trades: 3,
          stake_amount: 'unlimited',
        }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* Info Alert */}
          <Alert
            message="Submit New Backtest"
            description="Configure and submit a new backtest job. The job will be queued and executed by the backtest engine."
            type="info"
            showIcon
            icon={<InfoCircleOutlined />}
          />

          {/* Strategy Selection */}
          <Card title="Strategy" size="small">
            <Form.Item
              name="strategy_id"
              label="Select Strategy"
              rules={[{ required: true, message: 'Please select a strategy' }]}
              extra="Choose the trading strategy to backtest"
            >
              <Select
                placeholder="Select a strategy"
                loading={strategiesLoading}
                showSearch
                filterOption={(input, option) =>
                  (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                }
                options={strategies.map((item) => ({
                  label: `${item.strategy.name} (${item.strategy.id.slice(0, 8)})`,
                  value: item.strategy.id,
                }))}
              />
            </Form.Item>
          </Card>

          {/* Backtest Configuration */}
          <Card title="Configuration" size="small">
            <Row gutter={16}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="exchange"
                  label="Exchange"
                  rules={[{ required: true, message: 'Please select an exchange' }]}
                >
                  <Select
                    placeholder="Select exchange"
                    options={EXCHANGES}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  name="timeframe"
                  label="Timeframe"
                  rules={[{ required: true, message: 'Please select a timeframe' }]}
                >
                  <Select
                    placeholder="Select timeframe"
                    options={TIMEFRAMES}
                    onChange={setSelectedTimeframe}
                  />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item
              name="pairs"
              label="Trading Pairs"
              rules={[
                { required: true, message: 'Please select at least one pair' },
                {
                  validator: (_, value) => {
                    if (value && value.length > 10) {
                      return Promise.reject('Maximum 10 pairs allowed');
                    }
                    return Promise.resolve();
                  },
                },
              ]}
              extra="Select up to 10 trading pairs"
            >
              <Select
                mode="multiple"
                placeholder="Select trading pairs"
                onChange={setSelectedPairs}
                options={COMMON_PAIRS.map((pair) => ({
                  label: pair,
                  value: pair,
                }))}
              />
            </Form.Item>

            <Form.Item
              name="date_range"
              label="Date Range"
              rules={[{ required: true, message: 'Please select a date range' }]}
              extra="Historical data range for backtesting"
            >
              <RangePicker
                style={{ width: '100%' }}
                format="YYYY-MM-DD"
                disabledDate={(current) => current && current > dayjs().endOf('day')}
                onChange={(dates) => setDateRange(dates as [Dayjs, Dayjs])}
                presets={[
                  { label: 'Last 7 days', value: [dayjs().subtract(7, 'days'), dayjs()] },
                  { label: 'Last 30 days', value: [dayjs().subtract(30, 'days'), dayjs()] },
                  { label: 'Last 3 months', value: [dayjs().subtract(3, 'months'), dayjs()] },
                  { label: 'Last 6 months', value: [dayjs().subtract(6, 'months'), dayjs()] },
                  { label: 'Last year', value: [dayjs().subtract(1, 'year'), dayjs()] },
                ]}
              />
            </Form.Item>
          </Card>

          {/* Advanced Options */}
          <Card title="Advanced Options" size="small">
            <Row gutter={16}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="dry_run_wallet"
                  label="Starting Balance (USD)"
                  rules={[
                    { required: true },
                    { type: 'number', min: 100, message: 'Minimum $100' },
                  ]}
                  extra="Initial wallet balance for simulation"
                >
                  <InputNumber
                    style={{ width: '100%' }}
                    formatter={(value) => `$ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={(value) => value!.replace(/\$\s?|(,*)/g, '') as any}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  name="max_open_trades"
                  label="Max Open Trades"
                  rules={[
                    { required: true },
                    { type: 'number', min: 1, max: 20 },
                  ]}
                  extra="Maximum number of concurrent positions"
                >
                  <InputNumber
                    style={{ width: '100%' }}
                    min={1}
                    max={20}
                  />
                </Form.Item>
              </Col>
            </Row>

            <Row gutter={16}>
              <Col xs={24} md={12}>
                <Form.Item
                  name="stake_amount"
                  label="Stake Amount"
                  extra="Amount to invest per trade (or 'unlimited' for full balance)"
                >
                  <Input placeholder="e.g., 100 or unlimited" />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item
                  name="priority"
                  label="Priority"
                  extra="Higher priority jobs execute first"
                >
                  <Select options={PRIORITIES} />
                </Form.Item>
              </Col>
            </Row>
          </Card>

          {/* Estimated Runtime */}
          <Card size="small">
            <Space>
              <ThunderboltOutlined style={{ fontSize: 20, color: '#1890ff' }} />
              <div>
                <Text strong>Estimated Runtime: </Text>
                <Text type="secondary">
                  {estimateRuntime(selectedPairs, selectedTimeframe, dateRange)}
                </Text>
              </div>
            </Space>
            <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
              Actual runtime may vary based on system load and data availability.
            </Paragraph>
          </Card>
        </Space>
      </Form>
    </Create>
  );
};
