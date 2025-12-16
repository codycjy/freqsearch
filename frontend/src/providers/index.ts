/**
 * Providers barrel export
 */

// Data Provider
export { dataProvider, default } from './dataProvider';
export {
  getOptimizationWithIterations,
  getBacktestWithResult,
  getStrategyLineage,
  getQueueStats,
  controlOptimization,
} from "./dataProvider";

// Live Provider
export { createLiveProvider, liveProvider } from "./liveProvider";
export type {
  WebSocketEventType,
  WebSocketMessage,
  OptimizationIterationData,
  OptimizationCompletedData,
  OptimizationFailedData,
  BacktestSubmittedData,
  BacktestCompletedData,
  AgentStatusChangedData,
} from "./liveProvider";

// Hooks
export {
  useLiveUpdates,
  useOptimizationUpdates,
  useBacktestUpdates,
  useAgentUpdates,
} from "./useLiveUpdates";

// Types - re-export all types from types.ts
export type {
  PaginationResponse,
  JobStatus,
  ApprovalStatus,
  OptimizationStatus,
  OptimizationMode,
  OptimizationAction,
  StrategyTags,
  StrategyMetadata,
  Strategy,
  StrategyPerformanceMetrics,
  StrategyWithMetrics,
  CreateStrategyPayload,
  BacktestConfig,
  BacktestJob,
  PairResult,
  BacktestResult,
  BacktestResultSummary,
  CreateBacktestPayload,
  OptimizationCriteria,
  OptimizationConfig,
  OptimizationRun,
  OptimizationIteration,
  CreateOptimizationPayload,
  ControlOptimizationPayload,
  StrategyListResponse,
  BacktestListResponse,
  OptimizationListResponse,
  BacktestResultListResponse,
} from "./types";
