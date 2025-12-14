// Package repository provides data access layer implementations.
package repository

import (
	"context"
	"time"

	"github.com/google/uuid"

	"github.com/saltfish/freqsearch/go-backend/internal/db"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// StrategyRepository defines the interface for strategy data access.
type StrategyRepository interface {
	// Create creates a new strategy.
	Create(ctx context.Context, strategy *domain.Strategy) error

	// GetByID retrieves a strategy by ID.
	GetByID(ctx context.Context, id uuid.UUID) (*domain.Strategy, error)

	// GetByCodeHash retrieves a strategy by its code hash.
	GetByCodeHash(ctx context.Context, hash string) (*domain.Strategy, error)

	// Update updates an existing strategy.
	Update(ctx context.Context, strategy *domain.Strategy) error

	// Delete deletes a strategy by ID.
	Delete(ctx context.Context, id uuid.UUID) error

	// Search searches for strategies with filters and pagination.
	Search(ctx context.Context, query domain.StrategySearchQuery) ([]domain.StrategyWithMetrics, int, error)

	// GetLineage retrieves the strategy lineage tree.
	GetLineage(ctx context.Context, strategyID uuid.UUID, depth int) (*domain.StrategyLineageNode, error)

	// GetDescendants retrieves all descendants of a strategy.
	GetDescendants(ctx context.Context, strategyID uuid.UUID) ([]*domain.Strategy, error)

	// GetAncestors retrieves all ancestors of a strategy.
	GetAncestors(ctx context.Context, strategyID uuid.UUID) ([]*domain.Strategy, error)
}

// BacktestJobRepository defines the interface for backtest job data access.
type BacktestJobRepository interface {
	// Create creates a new backtest job.
	Create(ctx context.Context, job *domain.BacktestJob) error

	// CreateBatch creates multiple backtest jobs in a single transaction.
	CreateBatch(ctx context.Context, jobs []*domain.BacktestJob) error

	// GetByID retrieves a job by ID.
	GetByID(ctx context.Context, id uuid.UUID) (*domain.BacktestJob, error)

	// Update updates an existing job.
	Update(ctx context.Context, job *domain.BacktestJob) error

	// GetPendingJobs retrieves pending jobs for processing.
	// Uses FOR UPDATE SKIP LOCKED for concurrent-safe dequeuing.
	GetPendingJobs(ctx context.Context, limit int) ([]*domain.BacktestJob, error)

	// UpdateStatus updates the job status with optional container ID and error message.
	UpdateStatus(ctx context.Context, id uuid.UUID, status domain.JobStatus, containerID, errMsg *string) error

	// MarkRunning marks a job as running with the container ID.
	MarkRunning(ctx context.Context, id uuid.UUID, containerID string) error

	// MarkCompleted marks a job as completed.
	MarkCompleted(ctx context.Context, id uuid.UUID) error

	// MarkFailed marks a job as failed with an error message.
	MarkFailed(ctx context.Context, id uuid.UUID, errMsg string) error

	// Cancel cancels a pending or running job.
	Cancel(ctx context.Context, id uuid.UUID) error

	// GetRunningJobs retrieves all currently running jobs.
	GetRunningJobs(ctx context.Context) ([]*domain.BacktestJob, error)

	// GetTimedOutJobs retrieves jobs that have exceeded the timeout.
	GetTimedOutJobs(ctx context.Context, timeout time.Duration) ([]*domain.BacktestJob, error)

	// GetByOptimizationRunID retrieves jobs for an optimization run.
	GetByOptimizationRunID(ctx context.Context, runID uuid.UUID) ([]*domain.BacktestJob, error)

	// GetQueueStats retrieves queue statistics.
	GetQueueStats(ctx context.Context) (*domain.QueueStats, error)

	// IncrementRetryCount increments the retry count for a job.
	IncrementRetryCount(ctx context.Context, id uuid.UUID) error
}

// BacktestResultRepository defines the interface for backtest result data access.
type BacktestResultRepository interface {
	// Create creates a new backtest result.
	Create(ctx context.Context, result *domain.BacktestResult) error

	// GetByID retrieves a result by ID.
	GetByID(ctx context.Context, id uuid.UUID) (*domain.BacktestResult, error)

	// GetByJobID retrieves a result by job ID.
	GetByJobID(ctx context.Context, jobID uuid.UUID) (*domain.BacktestResult, error)

	// GetByStrategyID retrieves all results for a strategy.
	GetByStrategyID(ctx context.Context, strategyID uuid.UUID) ([]*domain.BacktestResult, error)

	// Query queries results with filters and pagination.
	Query(ctx context.Context, query domain.BacktestResultQuery) ([]*domain.BacktestResult, int, error)

	// GetBestByStrategyID retrieves the best result for a strategy based on sharpe ratio.
	GetBestByStrategyID(ctx context.Context, strategyID uuid.UUID) (*domain.BacktestResult, error)
}

// OptimizationRepository defines the interface for optimization run data access.
type OptimizationRepository interface {
	// Create creates a new optimization run.
	Create(ctx context.Context, run *domain.OptimizationRun) error

	// GetByID retrieves an optimization run by ID.
	GetByID(ctx context.Context, id uuid.UUID) (*domain.OptimizationRun, error)

	// Update updates an existing optimization run.
	Update(ctx context.Context, run *domain.OptimizationRun) error

	// List lists optimization runs with filters and pagination.
	List(ctx context.Context, query domain.OptimizationListQuery) ([]*domain.OptimizationRun, int, error)

	// UpdateStatus updates the status of an optimization run.
	UpdateStatus(ctx context.Context, id uuid.UUID, status domain.OptimizationStatus) error

	// SetBestResult sets the best strategy and result for an optimization run.
	SetBestResult(ctx context.Context, id uuid.UUID, strategyID, resultID uuid.UUID) error

	// Complete marks an optimization run as completed with a termination reason.
	Complete(ctx context.Context, id uuid.UUID, reason string, bestStrategyID, bestResultID *uuid.UUID) error

	// Fail marks an optimization run as failed with a reason.
	Fail(ctx context.Context, id uuid.UUID, reason string) error

	// IncrementIteration increments the current iteration counter.
	IncrementIteration(ctx context.Context, id uuid.UUID) error

	// AddIteration adds a new iteration record.
	AddIteration(ctx context.Context, iteration *domain.OptimizationIteration) error

	// GetIterations retrieves all iterations for an optimization run.
	GetIterations(ctx context.Context, runID uuid.UUID) ([]*domain.OptimizationIteration, error)

	// UpdateIterationResult updates the result ID for an iteration.
	UpdateIterationResult(ctx context.Context, iterID, resultID uuid.UUID) error

	// UpdateIterationFeedback updates the engineer and analyst feedback for an iteration.
	UpdateIterationFeedback(ctx context.Context, iterID uuid.UUID, engineerChanges, analystFeedback string, approval domain.ApprovalStatus) error
}

// Repositories aggregates all repository interfaces.
type Repositories struct {
	Strategy     StrategyRepository
	BacktestJob  BacktestJobRepository
	Result       BacktestResultRepository
	Optimization OptimizationRepository
}

// NewRepositories creates a new Repositories instance with all PostgreSQL implementations.
func NewRepositories(pool *db.Pool) *Repositories {
	return &Repositories{
		Strategy:     NewStrategyRepository(pool),
		BacktestJob:  NewBacktestJobRepository(pool),
		Result:       NewBacktestResultRepository(pool),
		Optimization: NewOptimizationRepository(pool),
	}
}
