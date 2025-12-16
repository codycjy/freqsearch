import { useForm, useSelect } from '@refinedev/antd';
import { Create } from '@refinedev/antd';
import { Form, Input, InputNumber, Select, Card, Row, Col } from 'antd';
import type { CreateOptimizationPayload, OptimizationMode, Strategy } from '@providers/types';

const optimizationModes: Array<{ label: string; value: OptimizationMode }> = [
  { label: 'Maximize Sharpe Ratio', value: 'OPTIMIZATION_MODE_MAXIMIZE_SHARPE' },
  { label: 'Maximize Profit', value: 'OPTIMIZATION_MODE_MAXIMIZE_PROFIT' },
  { label: 'Minimize Drawdown', value: 'OPTIMIZATION_MODE_MINIMIZE_DRAWDOWN' },
  { label: 'Balanced', value: 'OPTIMIZATION_MODE_BALANCED' },
];

export const OptimizationCreate = () => {
  const { formProps, saveButtonProps } = useForm<CreateOptimizationPayload>({
    redirect: 'show',
  });

  const { selectProps: strategySelectProps } = useSelect<Strategy>({
    resource: 'strategies',
    optionLabel: 'name',
    optionValue: 'id',
  });

  return (
    <Create saveButtonProps={saveButtonProps}>
      <Form
        {...formProps}
        layout="vertical"
        initialValues={{
          config: {
            max_iterations: 50,
            mode: 'OPTIMIZATION_MODE_MAXIMIZE_SHARPE',
            backtest_config: {
              exchange: 'binance',
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
                  <Select.Option value="kraken">Kraken</Select.Option>
                  <Select.Option value="coinbase">Coinbase</Select.Option>
                  <Select.Option value="bybit">Bybit</Select.Option>
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
            <Col span={12}>
              <Form.Item
                label="Start Date"
                name={['config', 'backtest_config', 'timerange_start']}
                rules={[{ required: true }]}
              >
                <Input type="date" style={{ width: '100%' }} placeholder="YYYY-MM-DD" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="End Date"
                name={['config', 'backtest_config', 'timerange_end']}
                rules={[{ required: true }]}
              >
                <Input type="date" style={{ width: '100%' }} placeholder="YYYY-MM-DD" />
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
