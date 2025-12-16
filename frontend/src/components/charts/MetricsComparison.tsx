import React from 'react';
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
import { Card } from 'antd';
import type { OptimizationIteration } from '@providers/types';

interface MetricsComparisonProps {
  iterations: OptimizationIteration[];
  title?: string;
  height?: number;
}

export const MetricsComparison: React.FC<MetricsComparisonProps> = ({
  iterations,
  title = 'Optimization Progress',
  height = 400,
}) => {
  const chartData = iterations
    .sort((a, b) => a.iteration_number - b.iteration_number)
    .map((iteration) => ({
      iteration: iteration.iteration_number,
      sharpe: iteration.result?.sharpe_ratio || 0,
      profit: iteration.result?.profit_pct || 0,
      drawdown: iteration.result?.max_drawdown_pct ? Math.abs(iteration.result.max_drawdown_pct) : 0,
      isBest: iteration.is_best,
    }));

  const bestSharpe = Math.max(...chartData.map((d) => d.sharpe));

  return (
    <Card title={title}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="iteration"
            label={{ value: 'Iteration', position: 'insideBottom', offset: -5 }}
          />
          <YAxis yAxisId="left" label={{ value: 'Sharpe Ratio', angle: -90, position: 'insideLeft' }} />
          <YAxis
            yAxisId="right"
            orientation="right"
            label={{ value: 'Profit %', angle: 90, position: 'insideRight' }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload || !payload.length) return null;
              const data = payload[0].payload;
              return (
                <div
                  style={{
                    backgroundColor: 'white',
                    padding: '10px',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                  }}
                >
                  <p style={{ margin: 0, fontWeight: 'bold' }}>Iteration {data.iteration}</p>
                  <p style={{ margin: '5px 0 0 0', color: '#8884d8' }}>
                    Sharpe: {data.sharpe.toFixed(3)}
                  </p>
                  <p style={{ margin: '5px 0 0 0', color: '#82ca9d' }}>
                    Profit: {data.profit.toFixed(2)}%
                  </p>
                  <p style={{ margin: '5px 0 0 0', color: '#ffc658' }}>
                    Drawdown: {data.drawdown.toFixed(2)}%
                  </p>
                  {data.isBest && (
                    <p style={{ margin: '5px 0 0 0', color: '#ff4d4f', fontWeight: 'bold' }}>
                      ⭐ Best Result
                    </p>
                  )}
                </div>
              );
            }}
          />
          <Legend />
          <ReferenceLine yAxisId="left" y={bestSharpe} stroke="red" strokeDasharray="3 3" />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="sharpe"
            stroke="#8884d8"
            strokeWidth={2}
            dot={(props) => {
              const { cx, cy, payload } = props;
              if (payload.isBest) {
                return (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={6}
                    fill="#ff4d4f"
                    stroke="#fff"
                    strokeWidth={2}
                  />
                );
              }
              return <circle cx={cx} cy={cy} r={3} fill="#8884d8" />;
            }}
            name="Sharpe Ratio"
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="profit"
            stroke="#82ca9d"
            strokeWidth={2}
            dot={{ r: 3 }}
            name="Profit %"
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="drawdown"
            stroke="#ffc658"
            strokeWidth={1}
            strokeDasharray="5 5"
            dot={{ r: 2 }}
            name="Drawdown %"
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
};
