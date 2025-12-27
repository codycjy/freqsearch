import { useForm, useSelect } from '@refinedev/antd';
import { Create } from '@refinedev/antd';
import { Form, Input, InputNumber, Select, Card, Row, Col, DatePicker } from 'antd';
import type { CreateOptimizationPayload, Strategy } from '@providers/types';
import dayjs from 'dayjs';
import type { Dayjs } from 'dayjs';

const { RangePicker } = DatePicker;

const rangePresets: {
  label: string;
  value: [Dayjs, Dayjs];
}[] = [
  { label: 'Last 7 Days', value: [dayjs().subtract(7, 'day'), dayjs()] },
  { label: 'Last 30 Days', value: [dayjs().subtract(30, 'day'), dayjs()] },
  { label: 'Last 90 Days', value: [dayjs().subtract(90, 'day'), dayjs()] },
  { label: 'Last 365 Days', value: [dayjs().subtract(365, 'day'), dayjs()] },
];

const optimizationModes: Array<{ label: string; value: string }> = [
  { label: 'Maximize Sharpe Ratio', value: 'maximize_sharpe' },
  { label: 'Maximize Profit', value: 'maximize_profit' },
  { label: 'Minimize Drawdown', value: 'minimize_drawdown' },
  { label: 'Balanced', value: 'balanced' },
];

export const OptimizationCreate = () => {
  const { formProps, saveButtonProps, onFinish } = useForm<CreateOptimizationPayload>({
    redirect: 'show',
  });

  const { selectProps: strategySelectProps } = useSelect<Strategy>({
    resource: 'strategies',
    optionLabel: 'name',
    optionValue: 'id',
  });

  const handleFinish = (values: any) => {
    // Transform timerange array to timerange_start and timerange_end
    const timerange = values.config?.backtest_config?.timerange;
    if (timerange && Array.isArray(timerange)) {
      const transformedValues = {
        ...values,
        config: {
          ...values.config,
          backtest_config: {
            ...values.config.backtest_config,
            timerange_start: timerange[0],
            timerange_end: timerange[1],
          },
        },
      };
      // Remove the temporary timerange field
      delete transformedValues.config.backtest_config.timerange;
      onFinish(transformedValues);
    } else {
      onFinish(values);
    }
  };

  return (
    <Create saveButtonProps={saveButtonProps}>
      <Form
        {...formProps}
        layout="vertical"
        onFinish={handleFinish}
        initialValues={{
          config: {
            max_iterations: 50,
            mode: 'maximize_sharpe',
            backtest_config: {
              exchange: 'okx',
              timeframe: '1h',
              dry_run_wallet: 1000,
              max_open_trades: 3,
              stake_amount: 'unlimited',
            },
            criteria: {
              min_sharpe: 0.5,
              min_profit_pct: 5.0,
              max_drawdown_pct: 20.0,
              min_trades: 10,
              min_win_rate: 40.0,
            },
          },
        }}
      >
        <Card title="Basic Information" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="Name"
                name="name"
                rules={[{ required: true, message: 'Please enter optimization name' }]}
              >
                <Input placeholder="My Optimization Run" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="Base Strategy"
                name="base_strategy_id"
                rules={[{ required: true, message: 'Please select a base strategy' }]}
              >
                <Select
                  {...strategySelectProps}
                  placeholder="Select a strategy"
                  showSearch
                  filterOption={(input, option) => {
                    const label = option?.label;
                    if (typeof label === 'string') {
                      return label.toLowerCase().includes(input.toLowerCase());
                    }
                    return false;
                  }}
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="Max Iterations"
                name={['config', 'max_iterations']}
                rules={[{ required: true, message: 'Please enter max iterations' }]}
              >
                <InputNumber min={1} max={1000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="Optimization Mode"
                name={['config', 'mode']}
                rules={[{ required: true, message: 'Please select optimization mode' }]}
              >
                <Select options={optimizationModes} />
              </Form.Item>
            </Col>
          </Row>
        </Card>

        <Card title="Backtest Configuration" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                label="Exchange"
                name={['config', 'backtest_config', 'exchange']}
                rules={[{ required: true }]}
              >
                <Select>
                  <Select.Option value="binance">Binance</Select.Option>
                  <Select.Option value="bybit">Bybit</Select.Option>
                  <Select.Option value="okx">OKX</Select.Option>
                  <Select.Option value="coinbasepro">Coinbase Pro</Select.Option>
                  <Select.Option value="kraken">Kraken</Select.Option>
                  <Select.Option value="bitfinex">Bitfinex</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="Timeframe"
                name={['config', 'backtest_config', 'timeframe']}
                rules={[{ required: true }]}
              >
                <Select>
                  <Select.Option value="1m">1 Minute</Select.Option>
                  <Select.Option value="5m">5 Minutes</Select.Option>
                  <Select.Option value="15m">15 Minutes</Select.Option>
                  <Select.Option value="1h">1 Hour</Select.Option>
                  <Select.Option value="4h">4 Hours</Select.Option>
                  <Select.Option value="1d">1 Day</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="Max Open Trades"
                name={['config', 'backtest_config', 'max_open_trades']}
                rules={[{ required: true }]}
              >
                <InputNumber min={1} max={10} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="Trading Pairs"
                name={['config', 'backtest_config', 'pairs']}
                rules={[{ required: true, message: 'Please enter at least one trading pair' }]}
              >
                <Select
                  mode="tags"
                  placeholder="e.g., BTC/USDT, ETH/USDT"
                  tokenSeparators={[',']}
                >
                  <Select.Option value="BTC/USDT">BTC/USDT</Select.Option>
                  <Select.Option value="ETH/USDT">ETH/USDT</Select.Option>
                  <Select.Option value="BNB/USDT">BNB/USDT</Select.Option>
                  <Select.Option value="SOL/USDT">SOL/USDT</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="Dry Run Wallet (USDT)"
                name={['config', 'backtest_config', 'dry_run_wallet']}
                rules={[{ required: true }]}
              >
                <InputNumber min={100} max={1000000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={24}>
              <Form.Item
                label="Time Range"
                name={['config', 'backtest_config', 'timerange']}
                rules={[{ required: true, message: 'Please select time range' }]}
                getValueProps={(value) => ({
                  value: value ? [dayjs(value[0]), dayjs(value[1])] : undefined,
                })}
                getValueFromEvent={(dates: [Dayjs, Dayjs] | null) => {
                  if (!dates) return undefined;
                  return [dates[0].format('YYYY-MM-DD'), dates[1].format('YYYY-MM-DD')];
                }}
              >
                <RangePicker
                  presets={rangePresets}
                  style={{ width: '100%' }}
                  format="YYYY-MM-DD"
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="Stake Amount"
            name={['config', 'backtest_config', 'stake_amount']}
            rules={[{ required: true }]}
          >
            <Input placeholder="unlimited or specific amount in USDT" />
          </Form.Item>
        </Card>

        <Card title="Optimization Criteria" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="Minimum Sharpe Ratio"
                name={['config', 'criteria', 'min_sharpe']}
                rules={[{ required: true }]}
              >
                <InputNumber
                  min={0}
                  max={10}
                  step={0.1}
                  style={{ width: '100%' }}
                  placeholder="0.5"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="Minimum Profit %"
                name={['config', 'criteria', 'min_profit_pct']}
                rules={[{ required: true }]}
              >
                <InputNumber
                  min={0}
                  max={1000}
                  step={1}
                  style={{ width: '100%' }}
                  placeholder="5.0"
                />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="Maximum Drawdown %"
                name={['config', 'criteria', 'max_drawdown_pct']}
                rules={[{ required: true }]}
              >
                <InputNumber
                  min={0}
                  max={100}
                  step={1}
                  style={{ width: '100%' }}
                  placeholder="20.0"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="Minimum Trades"
                name={['config', 'criteria', 'min_trades']}
                rules={[{ required: true }]}
              >
                <InputNumber min={1} max={10000} step={1} style={{ width: '100%' }} placeholder="10" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="Minimum Win Rate %"
            name={['config', 'criteria', 'min_win_rate']}
            rules={[{ required: true }]}
          >
            <InputNumber
              min={0}
              max={100}
              step={1}
              style={{ width: '50%' }}
              placeholder="40.0"
            />
          </Form.Item>
        </Card>
      </Form>
    </Create>
  );
};
