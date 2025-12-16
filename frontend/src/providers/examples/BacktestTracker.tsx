/**
 * Example: Real-time Backtest Tracker
 *
 * This component demonstrates how to track backtest submission
 * and completion with real-time updates.
 */

import React, { useState, useEffect } from "react";
import { useList } from "@refinedev/core";
import { Table, Card, Tag, Space, Badge, Statistic, Row, Col, notification } from "antd";
import {
  ClockCircleOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { useBacktestUpdates } from "@providers";
import type { BacktestJob } from "@providers";
import type { ColumnsType } from "antd/es/table";

/**
 * Real-time backtest tracker component
 */
export const BacktestTracker: React.FC = () => {
  const [recentBacktests, setRecentBacktests] = useState<BacktestJob[]>([]);

  // Fetch backtest list
  const { data, isLoading, refetch } = useList<BacktestJob>({
    resource: "backtests",
    pagination: { current: 1, pageSize: 20 },
    sorters: [{ field: "created_at", order: "desc" }],
  });

  // Subscribe to real-time backtest updates
  useBacktestUpdates({
    enabled: true,
    onSubmitted: (eventData: any) => {
      const strategy = eventData.strategy as string;

      notification.info({
        message: "Backtest Submitted",
        description: `${strategy} backtest queued`,
        icon: <ClockCircleOutlined style={{ color: "#1890ff" }} />,
        duration: 3,
      });

      // Refetch list to show new backtest
      refetch();
    },
    onComplete: (eventData: any) => {
      const backtestId = eventData.backtest_id as string;
      const sharpeRatio = eventData.sharpe_ratio as number;

      notification.success({
        message: "Backtest Completed",
        description: `Sharpe Ratio: ${sharpeRatio.toFixed(4)}`,
        icon: <CheckCircleOutlined style={{ color: "#52c41a" }} />,
        duration: 5,
      });

      // Add to recent backtests
      setRecentBacktests((prev) => {
        const existing = prev.find((bt) => bt.id === backtestId);
        if (!existing && data?.data) {
          const backtest = data.data.find((bt) => bt.id === backtestId);
          if (backtest) {
            return [backtest, ...prev].slice(0, 5);
          }
        }
        return prev;
      });

      // Refetch to update table
      refetch();
    },
  });

  // Initialize recent backtests from data
  useEffect(() => {
    if (data?.data && recentBacktests.length === 0) {
      const completed = data.data
        .filter((bt) => bt.status === "JOB_STATUS_COMPLETED")
        .slice(0, 5);
      setRecentBacktests(completed);
    }
  }, [data]);

  const columns: ColumnsType<BacktestJob> = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 120,
      render: (id: string) => (
        <code style={{ fontSize: "0.85em" }}>{id.slice(0, 8)}...</code>
      ),
    },
    {
      title: "Strategy",
      dataIndex: "strategy",
      key: "strategy",
      width: 200,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (status: string) => {
        const { color, icon } = getStatusDisplay(status);
        return <Tag icon={icon} color={color}>{status.toUpperCase()}</Tag>;
      },
    },
    {
      title: "Sharpe Ratio",
      dataIndex: "sharpe_ratio",
      key: "sharpe_ratio",
      width: 120,
      render: (sharpe: number | null) => (
        sharpe !== null ? (
          <span style={{ color: sharpe > 0 ? "#3f8600" : "#cf1322" }}>
            {sharpe.toFixed(4)}
          </span>
        ) : (
          <span style={{ color: "#bfbfbf" }}>-</span>
        )
      ),
    },
    {
      title: "Total Return",
      dataIndex: "total_return",
      key: "total_return",
      width: 120,
      render: (totalReturn: number | null) => (
        totalReturn !== null ? (
          <span style={{ color: totalReturn > 0 ? "#3f8600" : "#cf1322" }}>
            {(totalReturn * 100).toFixed(2)}%
          </span>
        ) : (
          <span style={{ color: "#bfbfbf" }}>-</span>
        )
      ),
    },
    {
      title: "Max Drawdown",
      dataIndex: "max_drawdown",
      key: "max_drawdown",
      width: 120,
      render: (drawdown: number | null) => (
        drawdown !== null ? (
          <span style={{ color: "#cf1322" }}>
            {(drawdown * 100).toFixed(2)}%
          </span>
        ) : (
          <span style={{ color: "#bfbfbf" }}>-</span>
        )
      ),
    },
    {
      title: "Trades",
      dataIndex: "trades_count",
      key: "trades_count",
      width: 100,
      render: (count: number | null) => count ?? "-",
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (date: string) => new Date(date).toLocaleString(),
    },
  ];

  const runningCount = data?.data.filter((bt) => bt.status === "JOB_STATUS_RUNNING").length ?? 0;
  const pendingCount = data?.data.filter((bt) => bt.status === "JOB_STATUS_PENDING").length ?? 0;
  const completedCount = data?.data.filter((bt) => bt.status === "JOB_STATUS_COMPLETED").length ?? 0;

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {/* Summary Statistics */}
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Running"
              value={runningCount}
              prefix={<SyncOutlined spin />}
              valueStyle={{ color: "#1890ff" }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Pending"
              value={pendingCount}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: "#faad14" }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Completed"
              value={completedCount}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Recent Best"
              value={getBestRecentSharpe(recentBacktests)}
              precision={4}
              prefix={<TrophyOutlined />}
              valueStyle={{ color: "#3f8600" }}
            />
          </Card>
        </Col>
      </Row>

      {/* Live Updates Badge */}
      <Card size="small">
        <Space>
          <Badge status="processing" />
          <span>Live updates active - new backtests will appear automatically</span>
        </Space>
      </Card>

      {/* Backtest Table */}
      <Card title="Backtests">
        <Table<BacktestJob>
          columns={columns}
          dataSource={data?.data}
          loading={isLoading}
          rowKey="id"
          pagination={{
            total: data?.total,
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} backtests`,
          }}
          scroll={{ x: 1200 }}
        />
      </Card>
    </Space>
  );
};

/**
 * Get status display properties
 */
function getStatusDisplay(status: string): {
  color: string;
  icon: React.ReactNode;
} {
  switch (status) {
    case "pending":
      return {
        color: "default",
        icon: <ClockCircleOutlined />,
      };
    case "running":
      return {
        color: "processing",
        icon: <SyncOutlined spin />,
      };
    case "completed":
      return {
        color: "success",
        icon: <CheckCircleOutlined />,
      };
    case "failed":
      return {
        color: "error",
        icon: <CheckCircleOutlined />,
      };
    default:
      return {
        color: "default",
        icon: null,
      };
  }
}

/**
 * Get best Sharpe ratio from recent backtests
 */
function getBestRecentSharpe(_backtests: BacktestJob[]): number {
  // Note: BacktestJob doesn't include results directly, would need to fetch separately
  // This is a placeholder implementation
  return 0;
}

export default BacktestTracker;
