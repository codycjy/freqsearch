// Package events provides RabbitMQ event publishing for FreqSearch.
package events

import (
	"time"

	"github.com/google/uuid"

	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// Routing keys for events.
const (
	// Task lifecycle events
	RoutingKeyTaskCreated   = "task.created"
	RoutingKeyTaskRunning   = "task.running"
	RoutingKeyTaskCompleted = "task.completed"
	RoutingKeyTaskFailed    = "task.failed"
	RoutingKeyTaskCancelled = "task.cancelled"
	RoutingKeyOptIteration  = "optimization.iteration"

	// Strategy lifecycle events (for Python Agents)
	RoutingKeyStrategyDiscovered     = "strategy.discovered"
	RoutingKeyStrategyNeedsProcessing = "strategy.needs_processing"
	RoutingKeyStrategyReadyForBacktest = "strategy.ready_for_backtest"
	RoutingKeyStrategyApproved       = "strategy.approved"
	RoutingKeyStrategyEvolve         = "strategy.evolve"
	RoutingKeyStrategyArchived       = "strategy.archived"

	// Backtest events (bridging Go backend and Python agents)
	RoutingKeyBacktestCompleted = "backtest.completed"
	RoutingKeyBacktestFailed    = "backtest.failed"
)

// Event types.
const (
	// Task events
	EventTypeTaskCreated   = "task.created"
	EventTypeTaskRunning   = "task.running"
	EventTypeTaskCompleted = "task.completed"
	EventTypeTaskFailed    = "task.failed"
	EventTypeTaskCancelled = "task.cancelled"
	EventTypeOptIteration  = "optimization.iteration"

	// Strategy events
	EventTypeStrategyDiscovered       = "strategy.discovered"
	EventTypeStrategyNeedsProcessing  = "strategy.needs_processing"
	EventTypeStrategyReadyForBacktest = "strategy.ready_for_backtest"
	EventTypeStrategyApproved         = "strategy.approved"
	EventTypeStrategyEvolve           = "strategy.evolve"
	EventTypeStrategyArchived         = "strategy.archived"

	// Backtest bridge events
	EventTypeBacktestCompleted = "backtest.completed"
	EventTypeBacktestFailed    = "backtest.failed"
)

// BaseEvent contains common fields for all events.
type BaseEvent struct {
	EventID   string    `json:"event_id"`
	EventType string    `json:"event_type"`
	Timestamp time.Time `json:"timestamp"`
	Source    string    `json:"source,omitempty"`
}

// NewBaseEvent creates a new BaseEvent with auto-generated event_id.
func NewBaseEvent(eventType string) BaseEvent {
	return BaseEvent{
		EventID:   uuid.New().String(),
		EventType: eventType,
		Timestamp: time.Now(),
		Source:    "go-backend",
	}
}

// TaskCreatedEvent is published when a backtest job is created.
type TaskCreatedEvent struct {
	BaseEvent
	JobID      uuid.UUID `json:"job_id"`
	StrategyID uuid.UUID `json:"strategy_id"`
	Priority   int       `json:"priority"`
}

// NewTaskCreatedEvent creates a new TaskCreatedEvent.
func NewTaskCreatedEvent(job *domain.BacktestJob) *TaskCreatedEvent {
	return &TaskCreatedEvent{
		BaseEvent:  NewBaseEvent(EventTypeTaskCreated),
		JobID:      job.ID,
		StrategyID: job.StrategyID,
		Priority:   job.Priority,
	}
}

// TaskRunningEvent is published when a backtest job starts running.
type TaskRunningEvent struct {
	BaseEvent
	JobID       uuid.UUID `json:"job_id"`
	StrategyID  uuid.UUID `json:"strategy_id"`
	ContainerID string    `json:"container_id,omitempty"`
}

// NewTaskRunningEvent creates a new TaskRunningEvent.
func NewTaskRunningEvent(job *domain.BacktestJob) *TaskRunningEvent {
	containerID := ""
	if job.ContainerID != nil {
		containerID = *job.ContainerID
	}
	return &TaskRunningEvent{
		BaseEvent:   NewBaseEvent(EventTypeTaskRunning),
		JobID:       job.ID,
		StrategyID:  job.StrategyID,
		ContainerID: containerID,
	}
}

// TaskCompletedEvent is published when a backtest job completes successfully.
type TaskCompletedEvent struct {
	BaseEvent
	JobID       uuid.UUID `json:"job_id"`
	StrategyID  uuid.UUID `json:"strategy_id"`
	ResultID    uuid.UUID `json:"result_id"`
	DurationMs  int64     `json:"duration_ms"`
	SharpeRatio *float64  `json:"sharpe_ratio,omitempty"`
	ProfitPct   float64   `json:"profit_pct"`
	TotalTrades int       `json:"total_trades"`
}

// NewTaskCompletedEvent creates a new TaskCompletedEvent.
func NewTaskCompletedEvent(job *domain.BacktestJob, result *domain.BacktestResult) *TaskCompletedEvent {
	var durationMs int64
	if job.StartedAt != nil && job.CompletedAt != nil {
		durationMs = job.CompletedAt.Sub(*job.StartedAt).Milliseconds()
	} else if job.StartedAt != nil {
		durationMs = time.Since(*job.StartedAt).Milliseconds()
	}

	return &TaskCompletedEvent{
		BaseEvent:   NewBaseEvent(EventTypeTaskCompleted),
		JobID:       job.ID,
		StrategyID:  job.StrategyID,
		ResultID:    result.ID,
		DurationMs:  durationMs,
		SharpeRatio: result.SharpeRatio,
		ProfitPct:   result.ProfitPct,
		TotalTrades: result.TotalTrades,
	}
}

// TaskFailedEvent is published when a backtest job fails.
type TaskFailedEvent struct {
	BaseEvent
	JobID        uuid.UUID `json:"job_id"`
	StrategyID   uuid.UUID `json:"strategy_id"`
	ErrorMessage string    `json:"error_message"`
	RetryCount   int       `json:"retry_count"`
}

// NewTaskFailedEvent creates a new TaskFailedEvent.
func NewTaskFailedEvent(job *domain.BacktestJob, errMsg string) *TaskFailedEvent {
	return &TaskFailedEvent{
		BaseEvent:    NewBaseEvent(EventTypeTaskFailed),
		JobID:        job.ID,
		StrategyID:   job.StrategyID,
		ErrorMessage: errMsg,
		RetryCount:   job.RetryCount,
	}
}

// TaskCancelledEvent is published when a backtest job is cancelled.
type TaskCancelledEvent struct {
	BaseEvent
	JobID      uuid.UUID `json:"job_id"`
	StrategyID uuid.UUID `json:"strategy_id"`
}

// NewTaskCancelledEvent creates a new TaskCancelledEvent.
func NewTaskCancelledEvent(job *domain.BacktestJob) *TaskCancelledEvent {
	return &TaskCancelledEvent{
		BaseEvent:  NewBaseEvent(EventTypeTaskCancelled),
		JobID:      job.ID,
		StrategyID: job.StrategyID,
	}
}

// OptimizationIterationEvent is published when an optimization iteration completes.
type OptimizationIterationEvent struct {
	BaseEvent
	RunID           uuid.UUID `json:"run_id"`
	IterationNumber int       `json:"iteration_number"`
	StrategyID      uuid.UUID `json:"strategy_id"`
	ResultID        uuid.UUID `json:"result_id,omitempty"`
	SharpeRatio     *float64  `json:"sharpe_ratio,omitempty"`
	ProfitPct       float64   `json:"profit_pct"`
	IsBest          bool      `json:"is_best"`
}

// NewOptimizationIterationEvent creates a new OptimizationIterationEvent.
func NewOptimizationIterationEvent(
	iteration *domain.OptimizationIteration,
	result *domain.BacktestResult,
	isBest bool,
) *OptimizationIterationEvent {
	event := &OptimizationIterationEvent{
		BaseEvent:       NewBaseEvent(EventTypeOptIteration),
		RunID:           iteration.OptimizationRunID,
		IterationNumber: iteration.IterationNumber,
		StrategyID:      iteration.StrategyID,
		IsBest:          isBest,
	}

	if result != nil {
		event.ResultID = result.ID
		event.SharpeRatio = result.SharpeRatio
		event.ProfitPct = result.ProfitPct
	}

	return event
}

// =============================================================================
// Strategy Lifecycle Events (for Python Agents integration)
// =============================================================================

// StrategyDiscoveredEvent is published when Scout Agent finds a new strategy.
type StrategyDiscoveredEvent struct {
	BaseEvent
	Name               string   `json:"name"`
	SourceType         string   `json:"source_type"` // "stratninja", "github", etc.
	SourceURL          string   `json:"source_url"`
	Code               string   `json:"code"`
	CodeHash           string   `json:"code_hash"`
	DetectedIndicators []string `json:"detected_indicators,omitempty"`
	Timeframe          string   `json:"timeframe,omitempty"`
	Stoploss           *float64 `json:"stoploss,omitempty"`
	IsValid            bool     `json:"is_valid"`
	ValidationErrors   []string `json:"validation_errors,omitempty"`
}

// StrategyNeedsProcessingEvent is published when a discovered strategy needs
// to be processed by Engineer Agent.
type StrategyNeedsProcessingEvent struct {
	BaseEvent
	StrategyID uuid.UUID `json:"strategy_id"`
	Name       string    `json:"name"`
	Code       string    `json:"code"`
	SourceType string    `json:"source_type"`
}

// StrategyReadyForBacktestEvent is published when Engineer Agent completes processing
// and the strategy is ready for backtesting.
type StrategyReadyForBacktestEvent struct {
	BaseEvent
	StrategyID     uuid.UUID              `json:"strategy_id"`
	Name           string                 `json:"name"`
	Code           string                 `json:"code"`
	CodeHash       string                 `json:"code_hash"`
	Description    string                 `json:"description,omitempty"`
	Tags           *domain.StrategyTags   `json:"tags,omitempty"`
	HyperoptConfig map[string]interface{} `json:"hyperopt_config,omitempty"`
	ParentID       *uuid.UUID             `json:"parent_id,omitempty"`
	Generation     int                    `json:"generation"`
}

// BacktestCompletedBridgeEvent bridges task completion to Python Agents.
// This is separate from TaskCompletedEvent to allow different routing.
type BacktestCompletedBridgeEvent struct {
	BaseEvent
	JobID           uuid.UUID `json:"job_id"`
	StrategyID      uuid.UUID `json:"strategy_id"`
	StrategyName    string    `json:"strategy_name"`
	Success         bool      `json:"success"`
	ErrorMessage    string    `json:"error_message,omitempty"`
	TotalTrades     *int      `json:"total_trades,omitempty"`
	ProfitPct       *float64  `json:"profit_pct,omitempty"`
	WinRate         *float64  `json:"win_rate,omitempty"`
	MaxDrawdownPct  *float64  `json:"max_drawdown_pct,omitempty"`
	SharpeRatio     *float64  `json:"sharpe_ratio,omitempty"`
	ResultID        *uuid.UUID `json:"result_id,omitempty"`
}

// NewBacktestCompletedBridgeEvent creates a BacktestCompletedBridgeEvent from job and result.
func NewBacktestCompletedBridgeEvent(
	job *domain.BacktestJob,
	strategy *domain.Strategy,
	result *domain.BacktestResult,
) *BacktestCompletedBridgeEvent {
	event := &BacktestCompletedBridgeEvent{
		BaseEvent:  NewBaseEvent(EventTypeBacktestCompleted),
		JobID:      job.ID,
		StrategyID: job.StrategyID,
		Success:    job.Status == domain.JobStatusCompleted,
	}

	if strategy != nil {
		event.StrategyName = strategy.Name
	}

	if job.ErrorMessage != nil {
		event.ErrorMessage = *job.ErrorMessage
	}

	if result != nil {
		event.ResultID = &result.ID
		event.TotalTrades = &result.TotalTrades
		event.ProfitPct = &result.ProfitPct
		event.WinRate = &result.WinRate
		event.MaxDrawdownPct = &result.MaxDrawdownPct
		event.SharpeRatio = result.SharpeRatio
	}

	return event
}

// StrategyEvolveEvent is published when Analyst Agent decides a strategy needs modification.
type StrategyEvolveEvent struct {
	BaseEvent
	StrategyID            uuid.UUID          `json:"strategy_id"`
	StrategyName          string             `json:"strategy_name"`
	CurrentCode           string             `json:"current_code"`
	DiagnosisJobID        uuid.UUID          `json:"diagnosis_job_id"`
	SuggestionType        string             `json:"suggestion_type"`
	SuggestionDescription string             `json:"suggestion_description"`
	TargetMetrics         []string           `json:"target_metrics,omitempty"`
	PreviousMetrics       map[string]float64 `json:"previous_metrics,omitempty"`
}

// StrategyApprovedEvent is published when Analyst Agent approves a strategy for live trading.
type StrategyApprovedEvent struct {
	BaseEvent
	StrategyID          uuid.UUID `json:"strategy_id"`
	StrategyName        string    `json:"strategy_name"`
	ProfitPct           float64   `json:"profit_pct"`
	WinRate             float64   `json:"win_rate"`
	MaxDrawdownPct      float64   `json:"max_drawdown_pct"`
	SharpeRatio         *float64  `json:"sharpe_ratio,omitempty"`
	EnhancedDescription string    `json:"enhanced_description,omitempty"`
	MarketRegime        []string  `json:"market_regime,omitempty"`
	Confidence          float64   `json:"confidence"`
	ApprovedForPairs    []string  `json:"approved_for_pairs,omitempty"`
	ApprovedTimeframe   string    `json:"approved_timeframe,omitempty"`
}

// StrategyArchivedEvent is published when a strategy is discarded.
type StrategyArchivedEvent struct {
	BaseEvent
	StrategyID   uuid.UUID          `json:"strategy_id"`
	StrategyName string             `json:"strategy_name"`
	Reason       string             `json:"reason"`
	FinalMetrics map[string]float64 `json:"final_metrics,omitempty"`
}
