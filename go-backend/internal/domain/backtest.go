package domain

import (
	"time"

	"github.com/google/uuid"
)

// BacktestJob represents a backtest execution task.
type BacktestJob struct {
	ID                uuid.UUID      `json:"id"`
	StrategyID        uuid.UUID      `json:"strategy_id"`
	OptimizationRunID *uuid.UUID     `json:"optimization_run_id,omitempty"`
	Config            BacktestConfig `json:"config"`
	Priority          int            `json:"priority"`
	Status            JobStatus      `json:"status"`
	ContainerID       *string        `json:"container_id,omitempty"`
	ErrorMessage      *string        `json:"error_message,omitempty"`
	RetryCount        int            `json:"retry_count"`
	CreatedAt         time.Time      `json:"created_at"`
	StartedAt         *time.Time     `json:"started_at,omitempty"`
	CompletedAt       *time.Time     `json:"completed_at,omitempty"`
}

// NewBacktestJob creates a new BacktestJob with generated UUID.
func NewBacktestJob(strategyID uuid.UUID, config BacktestConfig, priority int, optRunID *uuid.UUID) *BacktestJob {
	return &BacktestJob{
		ID:                uuid.New(),
		StrategyID:        strategyID,
		OptimizationRunID: optRunID,
		Config:            config,
		Priority:          priority,
		Status:            JobStatusPending,
		RetryCount:        0,
		CreatedAt:         time.Now(),
	}
}

// Duration returns the duration of the job execution.
func (j *BacktestJob) Duration() time.Duration {
	if j.StartedAt == nil {
		return 0
	}
	end := time.Now()
	if j.CompletedAt != nil {
		end = *j.CompletedAt
	}
	return end.Sub(*j.StartedAt)
}

// BacktestConfig represents the configuration for a backtest run.
type BacktestConfig struct {
	Exchange          string                 `json:"exchange"`
	Pairs             []string               `json:"pairs"`
	Timeframe         string                 `json:"timeframe"`
	TimerangeStart    string                 `json:"timerange_start"`
	TimerangeEnd      string                 `json:"timerange_end"`
	DryRunWallet      float64                `json:"dry_run_wallet"`
	MaxOpenTrades     int                    `json:"max_open_trades"`
	StakeAmount       string                 `json:"stake_amount"`
	HyperoptOverrides map[string]interface{} `json:"hyperopt_overrides,omitempty"`
}

// Timerange returns the formatted timerange string for Freqtrade.
func (c *BacktestConfig) Timerange() string {
	return c.TimerangeStart + "-" + c.TimerangeEnd
}

// BacktestResult represents the result of a completed backtest.
type BacktestResult struct {
	ID         uuid.UUID `json:"id"`
	JobID      uuid.UUID `json:"job_id"`
	StrategyID uuid.UUID `json:"strategy_id"`

	// Trade statistics
	TotalTrades   int     `json:"total_trades"`
	WinningTrades int     `json:"winning_trades"`
	LosingTrades  int     `json:"losing_trades"`
	WinRate       float64 `json:"win_rate"`

	// Profit metrics
	ProfitTotal  float64  `json:"profit_total"`
	ProfitPct    float64  `json:"profit_pct"`
	ProfitFactor *float64 `json:"profit_factor,omitempty"`

	// Risk metrics
	MaxDrawdown    float64  `json:"max_drawdown"`
	MaxDrawdownPct float64  `json:"max_drawdown_pct"`
	SharpeRatio    *float64 `json:"sharpe_ratio,omitempty"`
	SortinoRatio   *float64 `json:"sortino_ratio,omitempty"`
	CalmarRatio    *float64 `json:"calmar_ratio,omitempty"`

	// Trade duration metrics
	AvgTradeDurationMinutes *float64 `json:"avg_trade_duration_minutes,omitempty"`
	AvgProfitPerTrade       *float64 `json:"avg_profit_per_trade,omitempty"`
	BestTradePct            *float64 `json:"best_trade_pct,omitempty"`
	WorstTradePct           *float64 `json:"worst_trade_pct,omitempty"`

	// Detailed data
	PairResults []PairResult `json:"pair_results,omitempty"`
	RawLog      []byte       `json:"-"` // gzip compressed, not serialized to JSON

	CreatedAt time.Time `json:"created_at"`
}

// NewBacktestResult creates a new BacktestResult with generated UUID.
func NewBacktestResult(jobID, strategyID uuid.UUID) *BacktestResult {
	return &BacktestResult{
		ID:          uuid.New(),
		JobID:       jobID,
		StrategyID:  strategyID,
		PairResults: make([]PairResult, 0),
		CreatedAt:   time.Now(),
	}
}

// PairResult represents the backtest result for a single trading pair.
type PairResult struct {
	Pair               string  `json:"pair"`
	Trades             int     `json:"trades"`
	ProfitPct          float64 `json:"profit_pct"`
	WinRate            float64 `json:"win_rate"`
	AvgDurationMinutes float64 `json:"avg_duration_minutes"`
}

// BacktestResultQuery represents query parameters for backtest results.
type BacktestResultQuery struct {
	StrategyID        *uuid.UUID `json:"strategy_id,omitempty"`
	OptimizationRunID *uuid.UUID `json:"optimization_run_id,omitempty"`
	MinSharpe         *float64   `json:"min_sharpe,omitempty"`
	MinProfitPct      *float64   `json:"min_profit_pct,omitempty"`
	MaxDrawdownPct    *float64   `json:"max_drawdown_pct,omitempty"`
	MinTrades         *int       `json:"min_trades,omitempty"`
	TimeRange         *TimeRange `json:"time_range,omitempty"`
	OrderBy           string     `json:"order_by,omitempty"` // "sharpe", "profit", "created_at"
	Ascending         bool       `json:"ascending,omitempty"`
	Page              int        `json:"page"`
	PageSize          int        `json:"page_size"`
}

// SetDefaults sets default values for the query.
func (q *BacktestResultQuery) SetDefaults() {
	if q.OrderBy == "" {
		q.OrderBy = "created_at"
	}
	if q.Page <= 0 {
		q.Page = 1
	}
	if q.PageSize <= 0 {
		q.PageSize = 20
	}
	if q.PageSize > 100 {
		q.PageSize = 100
	}
}

// Offset returns the offset for pagination.
func (q *BacktestResultQuery) Offset() int {
	return (q.Page - 1) * q.PageSize
}

// TimeRange represents a time range for queries.
type TimeRange struct {
	Start time.Time `json:"start"`
	End   time.Time `json:"end"`
}

// QueueStats represents statistics about the backtest job queue.
type QueueStats struct {
	PendingJobs    int   `json:"pending_jobs"`
	RunningJobs    int   `json:"running_jobs"`
	CompletedToday int   `json:"completed_today"`
	FailedToday    int   `json:"failed_today"`
	AvgWaitTimeMs  int64 `json:"avg_wait_time_ms"`
	AvgRunTimeMs   int64 `json:"avg_run_time_ms"`
}
