import React, { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
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

interface DrawdownChartProps {
  trades: Trade[];
  height?: number;
  initialBalance?: number;
}

interface ChartDataPoint {
  timestamp: string;
  drawdown: number;
  drawdownPct: number;
  balance: number;
  peak: number;
  date: Date;
}

/**
 * DrawdownChart Component
 *
 * Displays a drawdown chart showing:
 * - Drawdown percentage over time
 * - Maximum drawdown point
 * - Peak balance points
 *
 * Drawdown is calculated as the percentage decline from the peak balance.
 *
 * Usage:
 * ```tsx
 * <DrawdownChart trades={backtestTrades} initialBalance={10000} />
 * ```
 */
export const DrawdownChart: React.FC<DrawdownChartProps> = ({
  trades,
  height = 300,
  initialBalance = 10000,
}) => {
  const { chartData, maxDrawdown } = useMemo(() => {
    if (!trades || trades.length === 0) {
      return { chartData: [], maxDrawdown: 0 };
    }

    // Sort trades by close date
    const sortedTrades = [...trades].sort(
      (a, b) => new Date(a.close_date).getTime() - new Date(b.close_date).getTime()
    );

    let cumulativeProfit = 0;
    let peakBalance = initialBalance;
    let maxDrawdownValue = 0;
    const data: ChartDataPoint[] = [];

    // Add starting point
    const firstTrade = sortedTrades[0];
    data.push({
      timestamp: dayjs(firstTrade.open_date).format('MMM DD HH:mm'),
      drawdown: 0,
      drawdownPct: 0,
      balance: initialBalance,
      peak: initialBalance,
      date: new Date(firstTrade.open_date),
    });

    // Process each trade
    sortedTrades.forEach((trade) => {
      cumulativeProfit += trade.profit_abs;
      const balance = initialBalance + cumulativeProfit;

      // Update peak if current balance is higher
      if (balance > peakBalance) {
        peakBalance = balance;
      }

      // Calculate drawdown from peak
      const drawdown = peakBalance - balance;
      const drawdownPct = peakBalance > 0 ? (drawdown / peakBalance) * 100 : 0;

      // Track maximum drawdown
      if (drawdownPct > maxDrawdownValue) {
        maxDrawdownValue = drawdownPct;
      }

      data.push({
        timestamp: dayjs(trade.close_date).format('MMM DD HH:mm'),
        drawdown: Number(drawdown.toFixed(2)),
        drawdownPct: Number(drawdownPct.toFixed(2)),
        balance: Number(balance.toFixed(2)),
        peak: Number(peakBalance.toFixed(2)),
        date: new Date(trade.close_date),
      });
    });

    return {
      chartData: data,
      maxDrawdown: maxDrawdownValue,
    };
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
          <Text>Peak: ${data.peak.toLocaleString()}</Text>
          <br />
          <Text style={{ color: '#cf1322' }}>
            Drawdown: ${data.drawdown.toLocaleString()} (-{data.drawdownPct.toFixed(2)}%)
          </Text>
        </div>
      );
    }
    return null;
  };

  // Format Y-axis values as percentage
  const formatPercent = (value: number) => {
    return `-${value.toFixed(0)}%`;
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

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart
        data={chartData}
        margin={{
          top: 5,
          right: 30,
          left: 20,
          bottom: 5,
        }}
      >
        <defs>
          <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#cf1322" stopOpacity={0.8} />
            <stop offset="95%" stopColor="#cf1322" stopOpacity={0.1} />
          </linearGradient>
        </defs>
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
          tickFormatter={formatPercent}
          reversed
          domain={[0, 'dataMax']}
        />
        <Tooltip content={<CustomTooltip />} />

        {/* Zero line */}
        <ReferenceLine
          y={0}
          stroke="#8c8c8c"
          strokeDasharray="5 5"
          label={{
            value: 'No Drawdown',
            position: 'right',
            fill: '#8c8c8c',
            fontSize: 12,
          }}
        />

        {/* Max drawdown line */}
        {maxDrawdown > 0 && (
          <ReferenceLine
            y={maxDrawdown}
            stroke="#cf1322"
            strokeDasharray="3 3"
            label={{
              value: `Max: -${maxDrawdown.toFixed(2)}%`,
              position: 'right',
              fill: '#cf1322',
              fontSize: 12,
            }}
          />
        )}

        {/* Drawdown area */}
        <Area
          type="monotone"
          dataKey="drawdownPct"
          stroke="#cf1322"
          strokeWidth={2}
          fill="url(#drawdownGradient)"
          name="Drawdown %"
          animationDuration={800}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};
