/**
 * Example: Real-time Optimization Monitor
 *
 * This component demonstrates how to use the live provider
 * to monitor optimization progress in real-time.
 */

import React, { useState, useEffect } from "react";
import { useOne } from "@refinedev/core";
import { Card, Progress, Statistic, Tag, Typography, Space, notification } from "antd";
import {
  RocketOutlined,
  TrophyOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from "@ant-design/icons";
import { useOptimizationUpdates } from "@providers";
import type { OptimizationRun } from "@providers";

const { Text } = Typography;

interface OptimizationMonitorProps {
  optimizationId: string;
}

/**
 * Real-time optimization monitor component
 */
export const OptimizationMonitor: React.FC<OptimizationMonitorProps> = ({
  optimizationId,
}) => {
  const [currentIteration, setCurrentIteration] = useState(0);
  const [bestSharpe, setBestSharpe] = useState<number | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  // Fetch optimization data
  const { data, isLoading, refetch } = useOne<OptimizationRun>({
    resource: "optimizations",
    id: optimizationId,
  });

  const optimization = data?.data;

  // Subscribe to real-time updates
  useOptimizationUpdates({
    ids: [optimizationId],
    enabled: true,
    onIterationStart: (eventData: any) => {
      setIsRunning(true);
      console.log("Iteration started:", eventData);
    },
    onIterationComplete: (eventData: any) => {
      const iteration = eventData.iteration as number;
      setCurrentIteration(iteration);
      console.log(`Iteration ${iteration} completed`);
    },
    onNewBest: (eventData: any) => {
      const sharpeRatio = eventData.sharpe_ratio as number;
      setBestSharpe(sharpeRatio);

      notification.success({
        message: "New Best Found!",
        description: `Sharpe Ratio: ${sharpeRatio.toFixed(4)}`,
        icon: <TrophyOutlined style={{ color: "#52c41a" }} />,
        duration: 3,
      });
    },
    onComplete: (eventData: any) => {
      setIsRunning(false);
      const totalIterations = eventData.total_iterations as number;

      notification.success({
        message: "Optimization Completed!",
        description: `Completed ${totalIterations} iterations`,
        icon: <CheckCircleOutlined style={{ color: "#52c41a" }} />,
        duration: 5,
      });

      // Refetch final data
      refetch();
    },
    onFailed: (eventData: any) => {
      setIsRunning(false);
      const error = eventData.error as string;

      notification.error({
        message: "Optimization Failed",
        description: error,
        icon: <CloseCircleOutlined style={{ color: "#ff4d4f" }} />,
        duration: 0, // Don't auto-close
      });
    },
  });

  // Initialize state from fetched data
  useEffect(() => {
    if (optimization) {
      setCurrentIteration(optimization.current_iteration);
      setBestSharpe(optimization.best_result?.sharpe_ratio ?? null);
      setIsRunning(optimization.status === "OPTIMIZATION_STATUS_RUNNING");
    }
  }, [optimization]);

  if (isLoading) {
    return <Card loading />;
  }

  if (!optimization) {
    return <Card>Optimization not found</Card>;
  }

  const progress = optimization.max_iterations > 0
    ? (currentIteration / optimization.max_iterations) * 100
    : 0;

  return (
    <Card
      title={
        <Space>
          <RocketOutlined />
          <span>Optimization Monitor</span>
          <Tag color={getStatusColor(optimization.status)}>
            {optimization.status.toUpperCase()}
          </Tag>
          {isRunning && (
            <Tag icon={<ThunderboltOutlined />} color="processing">
              LIVE
            </Tag>
          )}
        </Space>
      }
    >
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        {/* Progress */}
        <div>
          <Text strong>Progress</Text>
          <Progress
            percent={Math.round(progress)}
            status={getProgressStatus(optimization.status)}
            format={() => `${currentIteration} / ${optimization.max_iterations}`}
          />
        </div>

        {/* Statistics */}
        <Space size="large" wrap>
          <Statistic
            title="Current Iteration"
            value={currentIteration}
            suffix={`/ ${optimization.max_iterations}`}
          />
          <Statistic
            title="Best Sharpe Ratio"
            value={bestSharpe ?? "N/A"}
            precision={4}
            prefix={<TrophyOutlined />}
            valueStyle={{ color: bestSharpe && bestSharpe > 0 ? "#3f8600" : undefined }}
          />
          <Statistic
            title="Base Strategy ID"
            value={optimization.base_strategy_id.substring(0, 12) + '...'}
          />
        </Space>

        {/* Timestamps */}
        <Space direction="vertical" size="small">
          <Text type="secondary">
            Created: {new Date(optimization.created_at).toLocaleString()}
          </Text>
          <Text type="secondary">
            Updated: {new Date(optimization.updated_at).toLocaleString()}
          </Text>
          {optimization.completed_at && (
            <Text type="secondary">
              Completed: {new Date(optimization.completed_at).toLocaleString()}
            </Text>
          )}
          {!optimization.completed_at && isRunning && (
            <Text type="secondary">
              Last update: {new Date().toLocaleTimeString()}
            </Text>
          )}
        </Space>
      </Space>
    </Card>
  );
};

/**
 * Get status color for Tag
 */
function getStatusColor(status: string): string {
  switch (status) {
    case "pending":
      return "default";
    case "running":
      return "processing";
    case "completed":
      return "success";
    case "failed":
      return "error";
    default:
      return "default";
  }
}

/**
 * Get progress status for Progress bar
 */
function getProgressStatus(
  status: string
): "success" | "exception" | "active" | "normal" {
  switch (status) {
    case "running":
      return "active";
    case "completed":
      return "success";
    case "failed":
      return "exception";
    default:
      return "normal";
  }
}

export default OptimizationMonitor;
