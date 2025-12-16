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
