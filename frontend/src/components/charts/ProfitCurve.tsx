import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Empty, Typography } from 'antd';
import dayjs from 'dayjs';

const { Text } = Typography;

interface Trade {
  open_date: string;
  close_date: string;
  profit_abs: number;
  profit_pct: number;
  pair?: string;
}

interface ProfitCurveProps {
  trades: Trade[];
  height?: number;
  initialBalance?: number;
}

interface ChartDataPoint {
  timestamp: string;
  balance: number;
  profit: number;
  profitPct: number;
  date: Date;
}

/**
 * ProfitCurve Component
 *
 * Displays a cumulative profit curve chart showing:
 * - Account balance over time
 * - Cumulative profit
 * - Break-even line
 *
 * Usage:
 * ```tsx
 * <ProfitCurve trades={backtestTrades} initialBalance={10000} />
 * ```
 */
export const ProfitCurve: React.FC<ProfitCurveProps> = ({
  trades,
  height = 300,
  initialBalance = 10000,
}) => {
  const chartData = useMemo<ChartDataPoint[]>(() => {
    if (!trades || trades.length === 0) {
      return [];
    }

    // Sort trades by close date
    const sortedTrades = [...trades].sort(
      (a, b) => new Date(a.close_date).getTime() - new Date(b.close_date).getTime()
    );

    let cumulativeProfit = 0;
    const data: ChartDataPoint[] = [];

    // Add starting point
    const firstTrade = sortedTrades[0];
    data.push({
      timestamp: dayjs(firstTrade.open_date).format('MMM DD HH:mm'),
      balance: initialBalance,
      profit: 0,
      profitPct: 0,
      date: new Date(firstTrade.open_date),
    });

    // Process each trade
    sortedTrades.forEach((trade) => {
      cumulativeProfit += trade.profit_abs;
      const balance = initialBalance + cumulativeProfit;
      const profitPct = (cumulativeProfit / initialBalance) * 100;

      data.push({
        timestamp: dayjs(trade.close_date).format('MMM DD HH:mm'),
        balance: Number(balance.toFixed(2)),
        profit: Number(cumulativeProfit.toFixed(2)),
        profitPct: Number(profitPct.toFixed(2)),
        date: new Date(trade.close_date),
      });
    });

    return data;
  }, [trades, initialBalance]);

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload as ChartDataPoint;
      return (
        <div
          style={{
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            border: '1px solid #ccc',
            padding: '10px',
            borderRadius: '4px',
          }}
        >
          <Text strong>{data.timestamp}</Text>
          <br />
          <Text>Balance: ${data.balance.toLocaleString()}</Text>
          <br />
          <Text style={{ color: data.profit >= 0 ? '#3f8600' : '#cf1322' }}>
            Profit: ${data.profit.toLocaleString()} ({data.profitPct >= 0 ? '+' : ''}
            {data.profitPct.toFixed(2)}%)
          </Text>
        </div>
      );
    }
    return null;
  };

  // Format Y-axis values as currency
  const formatCurrency = (value: number) => {
    return `$${(value / 1000).toFixed(0)}k`;
  };

  if (!trades || trades.length === 0) {
    return (
      <Empty
        description="No trade data available"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        style={{ padding: '40px 0' }}
      />
    );
  }

  const finalBalance = chartData[chartData.length - 1]?.balance || initialBalance;
  const profitColor = finalBalance >= initialBalance ? '#3f8600' : '#cf1322';

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart
        data={chartData}
        margin={{
          top: 5,
          right: 30,
          left: 20,
          bottom: 5,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="timestamp"
          stroke="#8c8c8c"
          tick={{ fontSize: 12 }}
          angle={-45}
          textAnchor="end"
          height={80}
        />
        <YAxis
          stroke="#8c8c8c"
          tick={{ fontSize: 12 }}
          tickFormatter={formatCurrency}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ paddingTop: '10px' }}
          iconType="line"
        />

        {/* Break-even line */}
        <ReferenceLine
          y={initialBalance}
          stroke="#8c8c8c"
          strokeDasharray="5 5"
          label={{
            value: 'Break-even',
            position: 'right',
            fill: '#8c8c8c',
            fontSize: 12,
          }}
        />

        {/* Main profit curve */}
        <Line
          type="monotone"
          dataKey="balance"
          stroke={profitColor}
          strokeWidth={2}
          dot={false}
          name="Account Balance"
          animationDuration={800}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};
