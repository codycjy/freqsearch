/**
 * FreqSearch API Type Definitions
 *
 * These types correspond to the REST API responses and requests.
 * Based on the proto definitions in proto/freqsearch/v1/
 */

// ============================================================================
// Common Types
// ============================================================================

export interface PaginationResponse {
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export type JobStatus =
  | "JOB_STATUS_UNSPECIFIED"
  | "JOB_STATUS_PENDING"
  | "JOB_STATUS_RUNNING"
  | "JOB_STATUS_COMPLETED"
  | "JOB_STATUS_FAILED"
  | "JOB_STATUS_CANCELLED";

export type ApprovalStatus =
  | "APPROVAL_STATUS_UNSPECIFIED"
  | "APPROVAL_STATUS_PENDING"
  | "APPROVAL_STATUS_APPROVED"
  | "APPROVAL_STATUS_REJECTED"
  | "APPROVAL_STATUS_NEEDS_ITERATION";

export type OptimizationStatus =
  | "OPTIMIZATION_STATUS_UNSPECIFIED"
  | "OPTIMIZATION_STATUS_PENDING"
  | "OPTIMIZATION_STATUS_RUNNING"
  | "OPTIMIZATION_STATUS_PAUSED"
  | "OPTIMIZATION_STATUS_COMPLETED"
  | "OPTIMIZATION_STATUS_FAILED"
  | "OPTIMIZATION_STATUS_CANCELLED";

export type OptimizationMode =
  | "OPTIMIZATION_MODE_UNSPECIFIED"
  | "OPTIMIZATION_MODE_MAXIMIZE_SHARPE"
  | "OPTIMIZATION_MODE_MAXIMIZE_PROFIT"
  | "OPTIMIZATION_MODE_MINIMIZE_DRAWDOWN"
  | "OPTIMIZATION_MODE_BALANCED";

export type OptimizationAction =
  | "OPTIMIZATION_ACTION_UNSPECIFIED"
  | "OPTIMIZATION_ACTION_PAUSE"
  | "OPTIMIZATION_ACTION_RESUME"
  | "OPTIMIZATION_ACTION_CANCEL";

// ============================================================================
// Strategy Types
// ============================================================================

export interface StrategyTags {
  strategy_type: string[];
  risk_level: string;
  trading_style: string;
  indicators: string[];
  market_regime: string[];
}

export interface StrategyMetadata {
  timeframe: string;
  indicators: string[];
  stoploss: number;
  trailing_stop: boolean;
  trailing_stop_positive: number;
  trailing_stop_positive_offset: number;
  minimal_roi: Record<string, number>;
  startup_candle_count: number;
}

export interface Strategy {
  id: string;
  name: string;
  code: string;
  code_hash: string;
  parent_id?: string;
  generation: number;
  description: string;
  metadata: StrategyMetadata;
  tags: StrategyTags;
  created_at: string;
  updated_at: string;
}

export interface StrategyPerformanceMetrics {
  sharpe_ratio: number;
  sortino_ratio: number;
  profit_pct: number;
  max_drawdown_pct: number;
  total_trades: number;
  win_rate: number;
  profit_factor: number;
}

export interface StrategyWithMetrics {
  strategy: Strategy;
  best_result?: StrategyPerformanceMetrics;
  backtest_count: number;
}

export interface CreateStrategyPayload {
  name: string;
  code: string;
  parent_id?: string;
  description: string;
  tags?: StrategyTags;
}

// ============================================================================
// Backtest Types
// ============================================================================

export interface BacktestConfig {
  exchange: string;
  pairs: string[];
  timeframe: string;
  timerange_start: string;
  timerange_end: string;
  dry_run_wallet: number;
  max_open_trades: number;
  stake_amount: string;
}

export interface BacktestJob {
  id: string;
  strategy_id: string;
  optimization_run_id?: string;
  config: BacktestConfig;
  status: JobStatus;
  container_id?: string;
  error_message?: string;
  priority: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface PairResult {
  pair: string;
  trades: number;
  profit_pct: number;
  win_rate: number;
  avg_duration_minutes: number;
}

export interface BacktestResult {
  id: string;
  job_id: string;
  strategy_id: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  profit_total: number;
  profit_pct: number;
  profit_factor: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  avg_trade_duration_minutes: number;
  avg_profit_per_trade: number;
  best_trade_pct: number;
  worst_trade_pct: number;
  pair_results: PairResult[];
  raw_log: string;
  trades_json?: string;
  created_at: string;
}

export interface BacktestResultSummary {
  id: string;
  job_id: string;
  strategy_id: string;
  strategy_name: string;
  profit_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  total_trades: number;
  win_rate: number;
  created_at: string;
}

export interface CreateBacktestPayload {
  strategy_id: string;
  config: BacktestConfig;
  optimization_run_id?: string;
  priority?: number;
}

// ============================================================================
// Optimization Types
// ============================================================================

export interface OptimizationCriteria {
  min_sharpe: number;
  min_profit_pct: number;
  max_drawdown_pct: number;
  min_trades: number;
  min_win_rate: number;
}

export interface OptimizationConfig {
  backtest_config: BacktestConfig;
  max_iterations: number;
  criteria: OptimizationCriteria;
  mode: OptimizationMode;
}

export interface OptimizationRun {
  id: string;
  name: string;
  base_strategy_id: string;
  config: OptimizationConfig;
  status: OptimizationStatus;
  current_iteration: number;
  max_iterations: number;
  best_strategy_id?: string;
  best_result?: BacktestResult;
  termination_reason: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  iterations?: OptimizationIteration[];
}

export interface OptimizationIteration {
  iteration_number: number;
  strategy_id: string;
  backtest_job_id: string;
  result?: BacktestResult;
  engineer_changes: string;
  analyst_feedback: string;
  approval: ApprovalStatus;
  timestamp: string;
  is_best?: boolean;
}

export interface CreateOptimizationPayload {
  name: string;
  base_strategy_id: string;
  config: OptimizationConfig;
}

export interface ControlOptimizationPayload {
  action: OptimizationAction;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface StrategyListResponse {
  strategies: StrategyWithMetrics[];
  pagination: PaginationResponse;
}

export interface BacktestListResponse {
  backtests: BacktestJob[];
  pagination: PaginationResponse;
}

export interface OptimizationListResponse {
  runs: OptimizationRun[];
  pagination: PaginationResponse;
}

export interface BacktestResultListResponse {
  results: BacktestResultSummary[];
  pagination: PaginationResponse;
}

// ============================================================================
// Scout Types
// ============================================================================

export type ScoutSource = "stratninja" | "github" | "freqai_gym";

export interface ScoutSchedule {
  id: string;
  name: string;
  cron_expression: string;
  source: ScoutSource;
  max_strategies: number;
  enabled: boolean;
  last_run_at?: string;
  next_run_at?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateScoutSchedulePayload {
  name: string;
  cron_expression: string;
  source: ScoutSource;
  max_strategies?: number;
  enabled?: boolean;
}

export interface UpdateScoutSchedulePayload {
  name?: string;
  cron_expression?: string;
  source?: ScoutSource;
  max_strategies?: number;
  enabled?: boolean;
}

export interface ScoutScheduleListResponse {
  schedules: ScoutSchedule[];
  pagination: PaginationResponse;
}
