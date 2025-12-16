import { Card, Title } from '@tremor/react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { PerformanceDataPoint } from '../../types/api';

interface PerformanceChartProps {
  data?: PerformanceDataPoint[];
  loading?: boolean;
}

/**
 * PerformanceChart Component
 * Line/Area chart showing Sharpe ratio trends over time for optimizations
 * Uses Recharts for detailed, interactive visualizations
 */
export const PerformanceChart: React.FC<PerformanceChartProps> = ({ data = [], loading }) => {
  // Transform data for Recharts format
  const chartData = data.map((point) => ({
    timestamp: new Date(point.timestamp).toLocaleTimeString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }),
    sharpe: point.sharpe_ratio,
    name: point.optimization_name,
  }));

  // Group data by optimization for multi-line support
  const optimizationIds = Array.from(new Set(data.map((d) => d.optimization_id)));

  // Generate colors for different optimizations
  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

  if (loading) {
    return (
      <Card>
        <Title>Performance Overview (Last 24h)</Title>
        <div style={{ height: 320, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: '100%', height: 256, backgroundColor: '#e8e8e8', borderRadius: 4 }} />
        </div>
      </Card>
    );
  }

  if (data.length === 0) {
    return (
      <Card>
        <Title>Performance Overview (Last 24h)</Title>
        <div style={{ height: 320, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ textAlign: 'center', color: '#8c8c8c' }}>
            <svg
              style={{
                margin: '0 auto',
                display: 'block',
                height: 48,
                width: 48,
                color: '#bfbfbf'
              }}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
            <p style={{ marginTop: 8 }}>No performance data available</p>
            <p style={{ fontSize: 14 }}>Start an optimization to see trends</p>
          </div>
        </div>
      </Card>
    );
  }

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          backgroundColor: 'white',
          padding: 12,
          border: '1px solid #e8e8e8',
          borderRadius: 4,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)'
        }}>
          <p style={{ fontSize: 14, fontWeight: 500, color: '#262626' }}>{payload[0].payload.timestamp}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} style={{ fontSize: 14, color: entry.color }}>
              {entry.name}: {entry.value.toFixed(3)}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <Card>
      <Title>Performance Overview (Last 24h)</Title>
      <div style={{ marginTop: 16, height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
          >
            <defs>
              {optimizationIds.map((id, index) => (
                <linearGradient key={id} id={`color${id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors[index % colors.length]} stopOpacity={0.8} />
                  <stop offset="95%" stopColor={colors[index % colors.length]} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="timestamp"
              stroke="#6b7280"
              style={{ fontSize: 12 }}
              tick={{ fill: '#6b7280' }}
            />
            <YAxis
              stroke="#6b7280"
              style={{ fontSize: 12 }}
              tick={{ fill: '#6b7280' }}
              label={{ value: 'Sharpe Ratio', angle: -90, position: 'insideLeft', style: { fill: '#6b7280' } }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area
              type="monotone"
              dataKey="sharpe"
              stroke={colors[0]}
              fillOpacity={1}
              fill={`url(#color${optimizationIds[0] || 'default'})`}
              name="Sharpe Ratio"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div style={{
        marginTop: 16,
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 16,
        textAlign: 'center',
        borderTop: '1px solid #f0f0f0',
        paddingTop: 16
      }}>
        <div>
          <p style={{ fontSize: 12, color: '#595959' }}>Avg Sharpe</p>
          <p style={{ fontSize: 18, fontWeight: 600, color: '#262626' }}>
            {(data.reduce((acc, curr) => acc + curr.sharpe_ratio, 0) / data.length).toFixed(2)}
          </p>
        </div>
        <div>
          <p style={{ fontSize: 12, color: '#595959' }}>Best Sharpe</p>
          <p style={{ fontSize: 18, fontWeight: 600, color: '#52c41a' }}>
            {Math.max(...data.map((d) => d.sharpe_ratio)).toFixed(2)}
          </p>
        </div>
        <div>
          <p style={{ fontSize: 12, color: '#595959' }}>Data Points</p>
          <p style={{ fontSize: 18, fontWeight: 600, color: '#262626' }}>{data.length}</p>
        </div>
      </div>
    </Card>
  );
};
