package domain

import (
	"time"

	"github.com/google/uuid"
)

// OptimizationRun represents an AI-driven strategy optimization session.
type OptimizationRun struct {
	ID             uuid.UUID          `json:"id"`
	Name           string             `json:"name"`
	BaseStrategyID uuid.UUID          `json:"base_strategy_id"`
	Config         OptimizationConfig `json:"config"`
	Mode           OptimizationMode   `json:"mode"`
	Criteria       OptimizationCriteria `json:"criteria"`

	Status           OptimizationStatus `json:"status"`
	CurrentIteration int                `json:"current_iteration"`
	MaxIterations    int                `json:"max_iterations"`

	BestStrategyID    *uuid.UUID `json:"best_strategy_id,omitempty"`
	BestResultID      *uuid.UUID `json:"best_result_id,omitempty"`
	TerminationReason string     `json:"termination_reason,omitempty"`

	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`
}

// NewOptimizationRun creates a new OptimizationRun with generated UUID.
func NewOptimizationRun(name string, baseStrategyID uuid.UUID, config OptimizationConfig) *OptimizationRun {
	now := time.Now()
	return &OptimizationRun{
		ID:               uuid.New(),
		Name:             name,
		BaseStrategyID:   baseStrategyID,
		Config:           config,
		Mode:             config.Mode,
		Criteria:         config.Criteria,
		Status:           OptimizationStatusPending,
		CurrentIteration: 0,
		MaxIterations:    config.MaxIterations,
		CreatedAt:        now,
		UpdatedAt:        now,
	}
}

// Duration returns the duration of the optimization run.
func (r *OptimizationRun) Duration() time.Duration {
	end := time.Now()
	if r.CompletedAt != nil {
		end = *r.CompletedAt
	}
	return end.Sub(r.CreatedAt)
}

// IsComplete returns true if the optimization run is in a terminal state.
func (r *OptimizationRun) IsComplete() bool {
	return r.Status.IsTerminal()
}

// OptimizationConfig represents the configuration for an optimization run.
type OptimizationConfig struct {
	BacktestConfig BacktestConfig       `json:"backtest_config"`
	MaxIterations  int                  `json:"max_iterations"`
	Criteria       OptimizationCriteria `json:"criteria"`
	Mode           OptimizationMode     `json:"mode"`
}

// OptimizationCriteria represents the success criteria for optimization.
type OptimizationCriteria struct {
	MinSharpe      float64 `json:"min_sharpe"`
	MinProfitPct   float64 `json:"min_profit_pct"`
	MaxDrawdownPct float64 `json:"max_drawdown_pct"`
	MinTrades      int     `json:"min_trades"`
	MinWinRate     float64 `json:"min_win_rate"`
}

// IsMet checks if the given metrics meet the optimization criteria.
func (c *OptimizationCriteria) IsMet(metrics *BacktestResult) bool {
	if metrics == nil {
		return false
	}

	// Check sharpe ratio if specified and available
	if c.MinSharpe > 0 {
		if metrics.SharpeRatio == nil || *metrics.SharpeRatio < c.MinSharpe {
			return false
		}
	}

	// Check profit
	if c.MinProfitPct > 0 && metrics.ProfitPct < c.MinProfitPct {
		return false
	}

	// Check drawdown
	if c.MaxDrawdownPct > 0 && metrics.MaxDrawdownPct > c.MaxDrawdownPct {
		return false
	}

	// Check trades
	if c.MinTrades > 0 && metrics.TotalTrades < c.MinTrades {
		return false
	}

	// Check win rate
	if c.MinWinRate > 0 && metrics.WinRate < c.MinWinRate {
		return false
	}

	return true
}

// OptimizationIteration represents a single iteration in an optimization run.
type OptimizationIteration struct {
	ID                uuid.UUID      `json:"id"`
	OptimizationRunID uuid.UUID      `json:"optimization_run_id"`
	IterationNumber   int            `json:"iteration_number"`
	StrategyID        uuid.UUID      `json:"strategy_id"`
	BacktestJobID     uuid.UUID      `json:"backtest_job_id"`
	ResultID          *uuid.UUID     `json:"result_id,omitempty"`
	EngineerChanges   string         `json:"engineer_changes,omitempty"`
	AnalystFeedback   string         `json:"analyst_feedback,omitempty"`
	Approval          ApprovalStatus `json:"approval"`
	CreatedAt         time.Time      `json:"created_at"`
}

// NewOptimizationIteration creates a new OptimizationIteration.
func NewOptimizationIteration(
	runID uuid.UUID,
	iterationNumber int,
	strategyID uuid.UUID,
	jobID uuid.UUID,
) *OptimizationIteration {
	return &OptimizationIteration{
		ID:                uuid.New(),
		OptimizationRunID: runID,
		IterationNumber:   iterationNumber,
		StrategyID:        strategyID,
		BacktestJobID:     jobID,
		Approval:          ApprovalStatusPending,
		CreatedAt:         time.Now(),
	}
}

// OptimizationListQuery represents query parameters for listing optimization runs.
type OptimizationListQuery struct {
	Status    *OptimizationStatus `json:"status,omitempty"`
	TimeRange *TimeRange          `json:"time_range,omitempty"`
	OrderBy   string              `json:"order_by,omitempty"`
	Ascending bool                `json:"ascending,omitempty"`
	Page      int                 `json:"page"`
	PageSize  int                 `json:"page_size"`
}

// SetDefaults sets default values for the query.
func (q *OptimizationListQuery) SetDefaults() {
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
func (q *OptimizationListQuery) Offset() int {
	return (q.Page - 1) * q.PageSize
}

// Pagination represents pagination parameters.
type Pagination struct {
	Page     int `json:"page"`
	PageSize int `json:"page_size"`
}

// Offset returns the offset for pagination.
func (p *Pagination) Offset() int {
	return (p.Page - 1) * p.PageSize
}

// PaginationResponse represents pagination metadata in responses.
type PaginationResponse struct {
	TotalCount int `json:"total_count"`
	Page       int `json:"page"`
	PageSize   int `json:"page_size"`
	TotalPages int `json:"total_pages"`
}

// NewPaginationResponse creates a new PaginationResponse.
func NewPaginationResponse(totalCount, page, pageSize int) PaginationResponse {
	totalPages := (totalCount + pageSize - 1) / pageSize
	if totalPages < 1 {
		totalPages = 1
	}
	return PaginationResponse{
		TotalCount: totalCount,
		Page:       page,
		PageSize:   pageSize,
		TotalPages: totalPages,
	}
}
