// API data types for FreqSearch

export interface QueueStats {
  pending: number;
  running: number;
  completed: number;
  failed: number;
}

export interface OptimizationRun {
  id: string;
  name: string;
  status: 'running' | 'paused' | 'completed' | 'failed';
  current_iteration: number;
  max_iterations: number;
  best_sharpe_ratio: number;
  best_strategy_id?: string;
  created_at: string;
  updated_at: string;
}

export type AgentType = 'orchestrator' | 'engineer' | 'analyst' | 'scout';

export type AgentStatus = 'active' | 'idle' | 'offline';

export interface Agent {
  type: AgentType;
  status: AgentStatus;
  last_seen?: string;
  current_task?: string;
}

export interface PerformanceDataPoint {
  timestamp: string;
  sharpe_ratio: number;
  optimization_id: string;
  optimization_name: string;
}

export interface BacktestJob {
  id: string;
  strategy_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  optimization_run_id?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  results?: {
    sharpe_ratio?: number;
    total_profit?: number;
    max_drawdown?: number;
  };
}

// Scout related types
export type ScoutRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type ScoutTriggerType = 'manual' | 'scheduled' | 'event';

export interface ScoutMetrics {
  total_fetched: number;
  validated: number;
  validation_failed: number;
  duplicates_removed: number;
  submitted: number;
}

export interface ScoutRun {
  id: string;
  trigger_type: ScoutTriggerType;
  triggered_by?: string;
  source: string;
  max_strategies: number;
  status: ScoutRunStatus;
  error_message?: string;
  metrics?: ScoutMetrics;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface ScoutSchedule {
  id: string;
  name: string;
  cron_expression: string;
  source: string;
  max_strategies: number;
  enabled: boolean;
  last_run_id?: string;
  last_run_at?: string;
  next_run_at?: string;
  created_at: string;
  updated_at: string;
}

export interface TriggerScoutPayload {
  source: string;
  max_strategies?: number;
  trigger_type?: ScoutTriggerType;
  triggered_by?: string;
}

export interface CreateScoutSchedulePayload {
  name: string;
  cron_expression: string;
  source: string;
  max_strategies?: number;
  enabled?: boolean;
}

export interface UpdateScoutSchedulePayload {
  name?: string;
  cron_expression?: string;
  source?: string;
  max_strategies?: number;
  enabled?: boolean;
}
