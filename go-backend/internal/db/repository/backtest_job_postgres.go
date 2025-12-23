package repository

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/saltfish/freqsearch/go-backend/internal/db"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// backtestJobRepo implements BacktestJobRepository using PostgreSQL.
type backtestJobRepo struct {
	pool *db.Pool
}

// NewBacktestJobRepository creates a new PostgreSQL backtest job repository.
func NewBacktestJobRepository(pool *db.Pool) BacktestJobRepository {
	return &backtestJobRepo{pool: pool}
}

// Create creates a new backtest job.
func (r *backtestJobRepo) Create(ctx context.Context, job *domain.BacktestJob) error {
	configJSON, err := json.Marshal(job.Config)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	query := `
		INSERT INTO backtest_jobs (
			id, strategy_id, optimization_run_id, config, priority, status,
			container_id, error_message, retry_count, created_at, started_at, completed_at
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
		)
	`

	_, err = r.pool.Exec(ctx, query,
		job.ID,
		job.StrategyID,
		job.OptimizationRunID,
		configJSON,
		job.Priority,
		job.Status.String(),
		job.ContainerID,
		job.ErrorMessage,
		job.RetryCount,
		job.CreatedAt,
		job.StartedAt,
		job.CompletedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to create backtest job: %w", err)
	}

	return nil
}

// CreateBatch creates multiple backtest jobs in a single transaction.
func (r *backtestJobRepo) CreateBatch(ctx context.Context, jobs []*domain.BacktestJob) error {
	if len(jobs) == 0 {
		return nil
	}

	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback(ctx)

	query := `
		INSERT INTO backtest_jobs (
			id, strategy_id, optimization_run_id, config, priority, status,
			container_id, error_message, retry_count, created_at, started_at, completed_at
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
		)
	`

	for _, job := range jobs {
		configJSON, err := json.Marshal(job.Config)
		if err != nil {
			return fmt.Errorf("failed to marshal config for job %s: %w", job.ID, err)
		}

		_, err = tx.Exec(ctx, query,
			job.ID,
			job.StrategyID,
			job.OptimizationRunID,
			configJSON,
			job.Priority,
			job.Status.String(),
			job.ContainerID,
			job.ErrorMessage,
			job.RetryCount,
			job.CreatedAt,
			job.StartedAt,
			job.CompletedAt,
		)
		if err != nil {
			return fmt.Errorf("failed to create backtest job %s: %w", job.ID, err)
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

// GetByID retrieves a job by ID.
func (r *backtestJobRepo) GetByID(ctx context.Context, id uuid.UUID) (*domain.BacktestJob, error) {
	query := `
		SELECT
			id, strategy_id, optimization_run_id, config, priority, status,
			container_id, error_message, retry_count, created_at, started_at, completed_at
		FROM backtest_jobs
		WHERE id = $1
	`

	job := &domain.BacktestJob{}
	var configJSON []byte
	var statusStr string

	err := r.pool.QueryRow(ctx, query, id).Scan(
		&job.ID,
		&job.StrategyID,
		&job.OptimizationRunID,
		&configJSON,
		&job.Priority,
		&statusStr,
		&job.ContainerID,
		&job.ErrorMessage,
		&job.RetryCount,
		&job.CreatedAt,
		&job.StartedAt,
		&job.CompletedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domain.NewNotFoundError("backtest_job", id.String())
		}
		return nil, fmt.Errorf("failed to get backtest job: %w", err)
	}

	if err := json.Unmarshal(configJSON, &job.Config); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	job.Status = domain.JobStatusFromString(statusStr)
	return job, nil
}

// Update updates an existing job.
func (r *backtestJobRepo) Update(ctx context.Context, job *domain.BacktestJob) error {
	configJSON, err := json.Marshal(job.Config)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	query := `
		UPDATE backtest_jobs SET
			strategy_id = $2,
			optimization_run_id = $3,
			config = $4,
			priority = $5,
			status = $6,
			container_id = $7,
			error_message = $8,
			retry_count = $9,
			started_at = $10,
			completed_at = $11
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query,
		job.ID,
		job.StrategyID,
		job.OptimizationRunID,
		configJSON,
		job.Priority,
		job.Status.String(),
		job.ContainerID,
		job.ErrorMessage,
		job.RetryCount,
		job.StartedAt,
		job.CompletedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to update backtest job: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("backtest_job", job.ID.String())
	}

	return nil
}

// GetPendingJobs retrieves pending jobs for processing.
// Uses FOR UPDATE SKIP LOCKED for concurrent-safe dequeuing.
func (r *backtestJobRepo) GetPendingJobs(ctx context.Context, limit int) ([]*domain.BacktestJob, error) {
	query := `
		SELECT
			id, strategy_id, optimization_run_id, config, priority, status,
			container_id, error_message, retry_count, created_at, started_at, completed_at
		FROM backtest_jobs
		WHERE status = 'pending'
		ORDER BY priority DESC, created_at ASC
		LIMIT $1
		FOR UPDATE SKIP LOCKED
	`

	rows, err := r.pool.Query(ctx, query, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query pending jobs: %w", err)
	}
	defer rows.Close()

	return r.scanJobs(rows)
}

// UpdateStatus updates the job status with optional container ID and error message.
func (r *backtestJobRepo) UpdateStatus(
	ctx context.Context,
	id uuid.UUID,
	status domain.JobStatus,
	containerID, errMsg *string,
) error {
	query := `
		UPDATE backtest_jobs SET
			status = $2,
			container_id = COALESCE($3, container_id),
			error_message = COALESCE($4, error_message),
			started_at = CASE WHEN $2 = 'running' AND started_at IS NULL THEN NOW() ELSE started_at END,
			completed_at = CASE WHEN $2 IN ('completed', 'failed', 'cancelled') THEN NOW() ELSE completed_at END
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query, id, status.String(), containerID, errMsg)
	if err != nil {
		return fmt.Errorf("failed to update job status: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("backtest_job", id.String())
	}

	return nil
}

// MarkRunning marks a job as running with the container ID.
func (r *backtestJobRepo) MarkRunning(ctx context.Context, id uuid.UUID, containerID string) error {
	query := `
		UPDATE backtest_jobs SET
			status = 'running',
			container_id = $2,
			started_at = NOW()
		WHERE id = $1 AND status = 'pending'
	`

	result, err := r.pool.Exec(ctx, query, id, containerID)
	if err != nil {
		return fmt.Errorf("failed to mark job running: %w", err)
	}

	if result.RowsAffected() == 0 {
		// Check if job exists
		var exists bool
		err := r.pool.QueryRow(ctx, "SELECT EXISTS(SELECT 1 FROM backtest_jobs WHERE id = $1)", id).Scan(&exists)
		if err != nil {
			return fmt.Errorf("failed to check job existence: %w", err)
		}
		if !exists {
			return domain.NewNotFoundError("backtest_job", id.String())
		}
		return domain.ErrJobAlreadyRunning
	}

	return nil
}

// MarkCompleted marks a job as completed.
func (r *backtestJobRepo) MarkCompleted(ctx context.Context, id uuid.UUID) error {
	query := `
		UPDATE backtest_jobs SET
			status = 'completed',
			completed_at = NOW()
		WHERE id = $1 AND status = 'running'
	`

	result, err := r.pool.Exec(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to mark job completed: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("backtest_job", id.String())
	}

	return nil
}

// MarkFailed marks a job as failed with an error message.
func (r *backtestJobRepo) MarkFailed(ctx context.Context, id uuid.UUID, errMsg string) error {
	query := `
		UPDATE backtest_jobs SET
			status = 'failed',
			error_message = $2,
			completed_at = NOW()
		WHERE id = $1 AND status IN ('pending', 'running')
	`

	result, err := r.pool.Exec(ctx, query, id, errMsg)
	if err != nil {
		return fmt.Errorf("failed to mark job failed: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("backtest_job", id.String())
	}

	return nil
}

// Cancel cancels a pending or running job.
func (r *backtestJobRepo) Cancel(ctx context.Context, id uuid.UUID) error {
	query := `
		UPDATE backtest_jobs SET
			status = 'cancelled',
			completed_at = NOW()
		WHERE id = $1 AND status IN ('pending', 'running')
	`

	result, err := r.pool.Exec(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to cancel job: %w", err)
	}

	if result.RowsAffected() == 0 {
		// Check if job exists and its status
		var status string
		err := r.pool.QueryRow(ctx, "SELECT status FROM backtest_jobs WHERE id = $1", id).Scan(&status)
		if err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return domain.NewNotFoundError("backtest_job", id.String())
			}
			return fmt.Errorf("failed to check job status: %w", err)
		}
		return domain.ErrJobNotCancellable
	}

	return nil
}

// GetRunningJobs retrieves all currently running jobs.
func (r *backtestJobRepo) GetRunningJobs(ctx context.Context) ([]*domain.BacktestJob, error) {
	query := `
		SELECT
			id, strategy_id, optimization_run_id, config, priority, status,
			container_id, error_message, retry_count, created_at, started_at, completed_at
		FROM backtest_jobs
		WHERE status = 'running'
		ORDER BY started_at ASC
	`

	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query running jobs: %w", err)
	}
	defer rows.Close()

	return r.scanJobs(rows)
}

// GetTimedOutJobs retrieves jobs that have exceeded the timeout.
func (r *backtestJobRepo) GetTimedOutJobs(ctx context.Context, timeout time.Duration) ([]*domain.BacktestJob, error) {
	query := `
		SELECT
			id, strategy_id, optimization_run_id, config, priority, status,
			container_id, error_message, retry_count, created_at, started_at, completed_at
		FROM backtest_jobs
		WHERE status = 'running'
			AND started_at < NOW() - $1::interval
		ORDER BY started_at ASC
	`

	rows, err := r.pool.Query(ctx, query, timeout.String())
	if err != nil {
		return nil, fmt.Errorf("failed to query timed out jobs: %w", err)
	}
	defer rows.Close()

	return r.scanJobs(rows)
}

// GetByOptimizationRunID retrieves jobs for an optimization run.
func (r *backtestJobRepo) GetByOptimizationRunID(ctx context.Context, runID uuid.UUID) ([]*domain.BacktestJob, error) {
	query := `
		SELECT
			id, strategy_id, optimization_run_id, config, priority, status,
			container_id, error_message, retry_count, created_at, started_at, completed_at
		FROM backtest_jobs
		WHERE optimization_run_id = $1
		ORDER BY created_at ASC
	`

	rows, err := r.pool.Query(ctx, query, runID)
	if err != nil {
		return nil, fmt.Errorf("failed to query jobs by optimization run: %w", err)
	}
	defer rows.Close()

	return r.scanJobs(rows)
}

// Query queries backtest jobs with filters and pagination.
func (r *backtestJobRepo) Query(ctx context.Context, query *domain.BacktestJobQuery) ([]*domain.BacktestJob, *domain.PaginationResponse, error) {
	query.SetDefaults()

	// Build WHERE clause
	whereClause := ""
	args := []interface{}{}
	argCount := 0

	if query.StrategyID != nil {
		argCount++
		whereClause = fmt.Sprintf("WHERE strategy_id = $%d", argCount)
		args = append(args, *query.StrategyID)
	}

	if query.OptimizationRunID != nil {
		argCount++
		if whereClause == "" {
			whereClause = fmt.Sprintf("WHERE optimization_run_id = $%d", argCount)
		} else {
			whereClause += fmt.Sprintf(" AND optimization_run_id = $%d", argCount)
		}
		args = append(args, *query.OptimizationRunID)
	}

	if query.Status != nil {
		argCount++
		if whereClause == "" {
			whereClause = fmt.Sprintf("WHERE status = $%d", argCount)
		} else {
			whereClause += fmt.Sprintf(" AND status = $%d", argCount)
		}
		args = append(args, query.Status.String())
	}

	// Get total count
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM backtest_jobs %s", whereClause)
	var totalCount int
	if err := r.pool.QueryRow(ctx, countQuery, args...).Scan(&totalCount); err != nil {
		return nil, nil, fmt.Errorf("failed to count jobs: %w", err)
	}

	// Build ORDER BY clause
	orderDirection := "DESC"
	if query.Ascending {
		orderDirection = "ASC"
	}

	orderColumn := "created_at"
	switch query.OrderBy {
	case "priority":
		orderColumn = "priority"
	case "started_at":
		orderColumn = "started_at"
	case "created_at":
		orderColumn = "created_at"
	}

	orderClause := fmt.Sprintf("ORDER BY %s %s", orderColumn, orderDirection)

	// Add pagination
	argCount++
	limitArg := argCount
	argCount++
	offsetArg := argCount
	args = append(args, query.PageSize, query.Offset())

	// Build and execute main query
	selectQuery := fmt.Sprintf(`
		SELECT
			id, strategy_id, optimization_run_id, config, priority, status,
			container_id, error_message, retry_count, created_at, started_at, completed_at
		FROM backtest_jobs
		%s
		%s
		LIMIT $%d OFFSET $%d
	`, whereClause, orderClause, limitArg, offsetArg)

	rows, err := r.pool.Query(ctx, selectQuery, args...)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to query jobs: %w", err)
	}
	defer rows.Close()

	jobs, err := r.scanJobs(rows)
	if err != nil {
		return nil, nil, err
	}

	pagination := domain.NewPaginationResponse(totalCount, query.Page, query.PageSize)
	return jobs, &pagination, nil
}

// GetQueueStats retrieves queue statistics.
func (r *backtestJobRepo) GetQueueStats(ctx context.Context) (*domain.QueueStats, error) {
	query := `
		WITH today_jobs AS (
			SELECT status, started_at, completed_at, created_at
			FROM backtest_jobs
			WHERE created_at >= CURRENT_DATE
		),
		wait_times AS (
			SELECT EXTRACT(EPOCH FROM (started_at - created_at)) * 1000 AS wait_ms
			FROM backtest_jobs
			WHERE started_at IS NOT NULL
				AND created_at >= CURRENT_DATE - INTERVAL '7 days'
		),
		run_times AS (
			SELECT EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000 AS run_ms
			FROM backtest_jobs
			WHERE completed_at IS NOT NULL
				AND started_at IS NOT NULL
				AND created_at >= CURRENT_DATE - INTERVAL '7 days'
		)
		SELECT
			(SELECT COUNT(*) FROM backtest_jobs WHERE status = 'pending') AS pending_jobs,
			(SELECT COUNT(*) FROM backtest_jobs WHERE status = 'running') AS running_jobs,
			(SELECT COUNT(*) FROM today_jobs WHERE status = 'completed') AS completed_today,
			(SELECT COUNT(*) FROM today_jobs WHERE status = 'failed') AS failed_today,
			COALESCE((SELECT AVG(wait_ms)::bigint FROM wait_times), 0) AS avg_wait_time_ms,
			COALESCE((SELECT AVG(run_ms)::bigint FROM run_times), 0) AS avg_run_time_ms
	`

	stats := &domain.QueueStats{}
	err := r.pool.QueryRow(ctx, query).Scan(
		&stats.PendingJobs,
		&stats.RunningJobs,
		&stats.CompletedToday,
		&stats.FailedToday,
		&stats.AvgWaitTimeMs,
		&stats.AvgRunTimeMs,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get queue stats: %w", err)
	}

	return stats, nil
}

// IncrementRetryCount increments the retry count for a job.
func (r *backtestJobRepo) IncrementRetryCount(ctx context.Context, id uuid.UUID) error {
	query := `
		UPDATE backtest_jobs SET
			retry_count = retry_count + 1
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to increment retry count: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("backtest_job", id.String())
	}

	return nil
}

// scanJobs scans rows into a slice of BacktestJob.
func (r *backtestJobRepo) scanJobs(rows pgx.Rows) ([]*domain.BacktestJob, error) {
	var jobs []*domain.BacktestJob

	for rows.Next() {
		job := &domain.BacktestJob{}
		var configJSON []byte
		var statusStr string

		err := rows.Scan(
			&job.ID,
			&job.StrategyID,
			&job.OptimizationRunID,
			&configJSON,
			&job.Priority,
			&statusStr,
			&job.ContainerID,
			&job.ErrorMessage,
			&job.RetryCount,
			&job.CreatedAt,
			&job.StartedAt,
			&job.CompletedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan job row: %w", err)
		}

		if err := json.Unmarshal(configJSON, &job.Config); err != nil {
			return nil, fmt.Errorf("failed to unmarshal config: %w", err)
		}

		job.Status = domain.JobStatusFromString(statusStr)
		jobs = append(jobs, job)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating job rows: %w", err)
	}

	return jobs, nil
}
