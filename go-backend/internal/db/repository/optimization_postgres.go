package repository

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/saltfish/freqsearch/go-backend/internal/db"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// optimizationRepo implements OptimizationRepository using PostgreSQL.
type optimizationRepo struct {
	pool *db.Pool
}

// NewOptimizationRepository creates a new PostgreSQL optimization repository.
func NewOptimizationRepository(pool *db.Pool) OptimizationRepository {
	return &optimizationRepo{pool: pool}
}

// Create creates a new optimization run.
func (r *optimizationRepo) Create(ctx context.Context, run *domain.OptimizationRun) error {
	configJSON, err := json.Marshal(run.Config)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	query := `
		INSERT INTO optimization_runs (
			id, name, base_strategy_id, config, mode,
			criteria_min_sharpe, criteria_min_profit_pct, criteria_max_drawdown_pct,
			criteria_min_trades, criteria_min_win_rate,
			status, current_iteration, max_iterations,
			best_strategy_id, best_result_id, termination_reason,
			created_at, updated_at, completed_at
		) VALUES (
			$1, $2, $3, $4, $5,
			$6, $7, $8, $9, $10,
			$11, $12, $13,
			$14, $15, $16,
			$17, $18, $19
		)
	`

	_, err = r.pool.Exec(ctx, query,
		run.ID,
		run.Name,
		run.BaseStrategyID,
		configJSON,
		run.Mode.String(),
		nullIfZeroFloat(run.Criteria.MinSharpe),
		nullIfZeroFloat(run.Criteria.MinProfitPct),
		nullIfZeroFloat(run.Criteria.MaxDrawdownPct),
		nullIfZeroInt(run.Criteria.MinTrades),
		nullIfZeroFloat(run.Criteria.MinWinRate),
		run.Status.String(),
		run.CurrentIteration,
		run.MaxIterations,
		run.BestStrategyID,
		run.BestResultID,
		nullIfEmptyString(run.TerminationReason),
		run.CreatedAt,
		run.UpdatedAt,
		run.CompletedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to create optimization run: %w", err)
	}

	return nil
}

// GetByID retrieves an optimization run by ID.
func (r *optimizationRepo) GetByID(ctx context.Context, id uuid.UUID) (*domain.OptimizationRun, error) {
	query := `
		SELECT
			id, name, base_strategy_id, config, mode,
			criteria_min_sharpe, criteria_min_profit_pct, criteria_max_drawdown_pct,
			criteria_min_trades, criteria_min_win_rate,
			status, current_iteration, max_iterations,
			best_strategy_id, best_result_id, termination_reason,
			created_at, updated_at, completed_at
		FROM optimization_runs
		WHERE id = $1
	`

	return r.scanRun(r.pool.QueryRow(ctx, query, id))
}

// Update updates an existing optimization run.
func (r *optimizationRepo) Update(ctx context.Context, run *domain.OptimizationRun) error {
	configJSON, err := json.Marshal(run.Config)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	query := `
		UPDATE optimization_runs SET
			name = $2,
			base_strategy_id = $3,
			config = $4,
			mode = $5,
			criteria_min_sharpe = $6,
			criteria_min_profit_pct = $7,
			criteria_max_drawdown_pct = $8,
			criteria_min_trades = $9,
			criteria_min_win_rate = $10,
			status = $11,
			current_iteration = $12,
			max_iterations = $13,
			best_strategy_id = $14,
			best_result_id = $15,
			termination_reason = $16,
			completed_at = $17
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query,
		run.ID,
		run.Name,
		run.BaseStrategyID,
		configJSON,
		run.Mode.String(),
		nullIfZeroFloat(run.Criteria.MinSharpe),
		nullIfZeroFloat(run.Criteria.MinProfitPct),
		nullIfZeroFloat(run.Criteria.MaxDrawdownPct),
		nullIfZeroInt(run.Criteria.MinTrades),
		nullIfZeroFloat(run.Criteria.MinWinRate),
		run.Status.String(),
		run.CurrentIteration,
		run.MaxIterations,
		run.BestStrategyID,
		run.BestResultID,
		nullIfEmptyString(run.TerminationReason),
		run.CompletedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to update optimization run: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("optimization_run", run.ID.String())
	}

	return nil
}

// List lists optimization runs with filters and pagination.
func (r *optimizationRepo) List(
	ctx context.Context,
	query domain.OptimizationListQuery,
) ([]*domain.OptimizationRun, int, error) {
	query.SetDefaults()

	var conditions []string
	var args []interface{}
	argNum := 1

	if query.Status != nil {
		conditions = append(conditions, fmt.Sprintf("status = $%d", argNum))
		args = append(args, query.Status.String())
		argNum++
	}

	if query.TimeRange != nil {
		conditions = append(conditions, fmt.Sprintf("created_at >= $%d", argNum))
		args = append(args, query.TimeRange.Start)
		argNum++
		conditions = append(conditions, fmt.Sprintf("created_at <= $%d", argNum))
		args = append(args, query.TimeRange.End)
		argNum++
	}

	whereClause := ""
	if len(conditions) > 0 {
		whereClause = "WHERE " + strings.Join(conditions, " AND ")
	}

	// Validate and sanitize order column
	orderColumn := "created_at"
	switch query.OrderBy {
	case "name":
		orderColumn = "name"
	case "status":
		orderColumn = "status"
	case "current_iteration":
		orderColumn = "current_iteration"
	case "created_at", "":
		orderColumn = "created_at"
	case "updated_at":
		orderColumn = "updated_at"
	}

	orderDir := "DESC"
	if query.Ascending {
		orderDir = "ASC"
	}

	// Count total
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM optimization_runs %s", whereClause)
	var totalCount int
	err := r.pool.QueryRow(ctx, countQuery, args...).Scan(&totalCount)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to count optimization runs: %w", err)
	}

	// Query runs
	selectQuery := fmt.Sprintf(`
		SELECT
			id, name, base_strategy_id, config, mode,
			criteria_min_sharpe, criteria_min_profit_pct, criteria_max_drawdown_pct,
			criteria_min_trades, criteria_min_win_rate,
			status, current_iteration, max_iterations,
			best_strategy_id, best_result_id, termination_reason,
			created_at, updated_at, completed_at
		FROM optimization_runs
		%s
		ORDER BY %s %s
		LIMIT $%d OFFSET $%d
	`, whereClause, orderColumn, orderDir, argNum, argNum+1)

	args = append(args, query.PageSize, query.Offset())

	rows, err := r.pool.Query(ctx, selectQuery, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to query optimization runs: %w", err)
	}
	defer rows.Close()

	runs, err := r.scanRuns(rows)
	if err != nil {
		return nil, 0, err
	}

	return runs, totalCount, nil
}

// UpdateStatus updates the status of an optimization run.
func (r *optimizationRepo) UpdateStatus(
	ctx context.Context,
	id uuid.UUID,
	status domain.OptimizationStatus,
) error {
	statusStr := status.String()

	// For terminal statuses, also set completed_at
	var query string
	if status.IsTerminal() {
		query = `
			UPDATE optimization_runs SET
				status = $2,
				completed_at = NOW()
			WHERE id = $1
		`
	} else {
		query = `
			UPDATE optimization_runs SET
				status = $2
			WHERE id = $1
		`
	}

	result, err := r.pool.Exec(ctx, query, id, statusStr)
	if err != nil {
		return fmt.Errorf("failed to update optimization status: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("optimization_run", id.String())
	}

	return nil
}

// SetBestResult sets the best strategy and result for an optimization run.
func (r *optimizationRepo) SetBestResult(
	ctx context.Context,
	id uuid.UUID,
	strategyID, resultID uuid.UUID,
) error {
	query := `
		UPDATE optimization_runs SET
			best_strategy_id = $2,
			best_result_id = $3
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query, id, strategyID, resultID)
	if err != nil {
		return fmt.Errorf("failed to set best result: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("optimization_run", id.String())
	}

	return nil
}

// Complete marks an optimization run as completed with a termination reason.
func (r *optimizationRepo) Complete(
	ctx context.Context,
	id uuid.UUID,
	reason string,
	bestStrategyID, bestResultID *uuid.UUID,
) error {
	query := `
		UPDATE optimization_runs SET
			status = 'completed',
			termination_reason = $2,
			best_strategy_id = COALESCE($3, best_strategy_id),
			best_result_id = COALESCE($4, best_result_id),
			completed_at = NOW()
		WHERE id = $1 AND status IN ('running', 'paused')
	`

	result, err := r.pool.Exec(ctx, query, id, reason, bestStrategyID, bestResultID)
	if err != nil {
		return fmt.Errorf("failed to complete optimization run: %w", err)
	}

	if result.RowsAffected() == 0 {
		// Check if exists and status
		var status string
		err := r.pool.QueryRow(ctx, "SELECT status FROM optimization_runs WHERE id = $1", id).Scan(&status)
		if err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return domain.NewNotFoundError("optimization_run", id.String())
			}
			return fmt.Errorf("failed to check run status: %w", err)
		}
		return domain.ErrOptimizationNotRunning
	}

	return nil
}

// Fail marks an optimization run as failed with a reason.
func (r *optimizationRepo) Fail(ctx context.Context, id uuid.UUID, reason string) error {
	query := `
		UPDATE optimization_runs SET
			status = 'failed',
			termination_reason = $2,
			completed_at = NOW()
		WHERE id = $1 AND status IN ('pending', 'running', 'paused')
	`

	result, err := r.pool.Exec(ctx, query, id, reason)
	if err != nil {
		return fmt.Errorf("failed to fail optimization run: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("optimization_run", id.String())
	}

	return nil
}

// IncrementIteration increments the current iteration counter.
func (r *optimizationRepo) IncrementIteration(ctx context.Context, id uuid.UUID) error {
	query := `
		UPDATE optimization_runs SET
			current_iteration = current_iteration + 1
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to increment iteration: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("optimization_run", id.String())
	}

	return nil
}

// AddIteration adds a new iteration record.
func (r *optimizationRepo) AddIteration(ctx context.Context, iteration *domain.OptimizationIteration) error {
	query := `
		INSERT INTO optimization_iterations (
			id, optimization_run_id, iteration_number, strategy_id,
			backtest_job_id, result_id, engineer_changes, analyst_feedback,
			approval, created_at
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10
		)
	`

	_, err := r.pool.Exec(ctx, query,
		iteration.ID,
		iteration.OptimizationRunID,
		iteration.IterationNumber,
		iteration.StrategyID,
		iteration.BacktestJobID,
		iteration.ResultID,
		nullIfEmptyString(iteration.EngineerChanges),
		nullIfEmptyString(iteration.AnalystFeedback),
		iteration.Approval.String(),
		iteration.CreatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to add iteration: %w", err)
	}

	return nil
}

// GetIterations retrieves all iterations for an optimization run.
func (r *optimizationRepo) GetIterations(ctx context.Context, runID uuid.UUID) ([]*domain.OptimizationIteration, error) {
	query := `
		SELECT
			id, optimization_run_id, iteration_number, strategy_id,
			backtest_job_id, result_id, engineer_changes, analyst_feedback,
			approval, created_at
		FROM optimization_iterations
		WHERE optimization_run_id = $1
		ORDER BY iteration_number ASC
	`

	rows, err := r.pool.Query(ctx, query, runID)
	if err != nil {
		return nil, fmt.Errorf("failed to query iterations: %w", err)
	}
	defer rows.Close()

	var iterations []*domain.OptimizationIteration
	for rows.Next() {
		iter := &domain.OptimizationIteration{}
		var engineerChanges, analystFeedback *string
		var approvalStr string

		err := rows.Scan(
			&iter.ID,
			&iter.OptimizationRunID,
			&iter.IterationNumber,
			&iter.StrategyID,
			&iter.BacktestJobID,
			&iter.ResultID,
			&engineerChanges,
			&analystFeedback,
			&approvalStr,
			&iter.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan iteration row: %w", err)
		}

		if engineerChanges != nil {
			iter.EngineerChanges = *engineerChanges
		}
		if analystFeedback != nil {
			iter.AnalystFeedback = *analystFeedback
		}
		iter.Approval = domain.ApprovalStatusFromString(approvalStr)

		iterations = append(iterations, iter)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating iteration rows: %w", err)
	}

	return iterations, nil
}

// UpdateIterationResult updates the result ID for an iteration.
func (r *optimizationRepo) UpdateIterationResult(ctx context.Context, iterID, resultID uuid.UUID) error {
	query := `
		UPDATE optimization_iterations SET
			result_id = $2
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query, iterID, resultID)
	if err != nil {
		return fmt.Errorf("failed to update iteration result: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("optimization_iteration", iterID.String())
	}

	return nil
}

// UpdateIterationFeedback updates the engineer and analyst feedback for an iteration.
func (r *optimizationRepo) UpdateIterationFeedback(
	ctx context.Context,
	iterID uuid.UUID,
	engineerChanges, analystFeedback string,
	approval domain.ApprovalStatus,
) error {
	query := `
		UPDATE optimization_iterations SET
			engineer_changes = $2,
			analyst_feedback = $3,
			approval = $4
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query, iterID, engineerChanges, analystFeedback, approval.String())
	if err != nil {
		return fmt.Errorf("failed to update iteration feedback: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("optimization_iteration", iterID.String())
	}

	return nil
}

// GetIterationsInTimeRange retrieves iterations within a time range (for performance charts).
func (r *optimizationRepo) GetIterationsInTimeRange(ctx context.Context, start, end time.Time) ([]*domain.OptimizationIteration, error) {
	query := `
		SELECT
			oi.id, oi.optimization_run_id, oi.iteration_number, oi.strategy_id,
			oi.backtest_job_id, oi.result_id, oi.engineer_changes, oi.analyst_feedback,
			oi.approval, oi.created_at
		FROM optimization_iterations oi
		WHERE oi.created_at >= $1 AND oi.created_at <= $2
		ORDER BY oi.created_at ASC
	`

	rows, err := r.pool.Query(ctx, query, start, end)
	if err != nil {
		return nil, fmt.Errorf("failed to query iterations in time range: %w", err)
	}
	defer rows.Close()

	var iterations []*domain.OptimizationIteration
	for rows.Next() {
		iter := &domain.OptimizationIteration{}
		var engineerChanges, analystFeedback *string
		var approvalStr string

		err := rows.Scan(
			&iter.ID,
			&iter.OptimizationRunID,
			&iter.IterationNumber,
			&iter.StrategyID,
			&iter.BacktestJobID,
			&iter.ResultID,
			&engineerChanges,
			&analystFeedback,
			&approvalStr,
			&iter.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan iteration row: %w", err)
		}

		if engineerChanges != nil {
			iter.EngineerChanges = *engineerChanges
		}
		if analystFeedback != nil {
			iter.AnalystFeedback = *analystFeedback
		}
		iter.Approval = domain.ApprovalStatusFromString(approvalStr)

		iterations = append(iterations, iter)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating iteration rows: %w", err)
	}

	return iterations, nil
}

// scanRun scans a single row into an OptimizationRun.
func (r *optimizationRepo) scanRun(row pgx.Row) (*domain.OptimizationRun, error) {
	run := &domain.OptimizationRun{}
	var configJSON []byte
	var modeStr, statusStr string
	var minSharpe, minProfitPct, maxDrawdownPct, minWinRate *float64
	var minTrades *int
	var terminationReason *string

	err := row.Scan(
		&run.ID,
		&run.Name,
		&run.BaseStrategyID,
		&configJSON,
		&modeStr,
		&minSharpe,
		&minProfitPct,
		&maxDrawdownPct,
		&minTrades,
		&minWinRate,
		&statusStr,
		&run.CurrentIteration,
		&run.MaxIterations,
		&run.BestStrategyID,
		&run.BestResultID,
		&terminationReason,
		&run.CreatedAt,
		&run.UpdatedAt,
		&run.CompletedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domain.ErrNotFound
		}
		return nil, fmt.Errorf("failed to scan optimization run: %w", err)
	}

	if err := json.Unmarshal(configJSON, &run.Config); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	run.Mode = domain.OptimizationModeFromString(modeStr)
	run.Status = domain.OptimizationStatusFromString(statusStr)

	// Populate criteria from individual columns
	run.Criteria = domain.OptimizationCriteria{}
	if minSharpe != nil {
		run.Criteria.MinSharpe = *minSharpe
	}
	if minProfitPct != nil {
		run.Criteria.MinProfitPct = *minProfitPct
	}
	if maxDrawdownPct != nil {
		run.Criteria.MaxDrawdownPct = *maxDrawdownPct
	}
	if minTrades != nil {
		run.Criteria.MinTrades = *minTrades
	}
	if minWinRate != nil {
		run.Criteria.MinWinRate = *minWinRate
	}
	if terminationReason != nil {
		run.TerminationReason = *terminationReason
	}

	return run, nil
}

// scanRuns scans multiple rows into a slice of OptimizationRun.
func (r *optimizationRepo) scanRuns(rows pgx.Rows) ([]*domain.OptimizationRun, error) {
	var runs []*domain.OptimizationRun

	for rows.Next() {
		run := &domain.OptimizationRun{}
		var configJSON []byte
		var modeStr, statusStr string
		var minSharpe, minProfitPct, maxDrawdownPct, minWinRate *float64
		var minTrades *int
		var terminationReason *string

		err := rows.Scan(
			&run.ID,
			&run.Name,
			&run.BaseStrategyID,
			&configJSON,
			&modeStr,
			&minSharpe,
			&minProfitPct,
			&maxDrawdownPct,
			&minTrades,
			&minWinRate,
			&statusStr,
			&run.CurrentIteration,
			&run.MaxIterations,
			&run.BestStrategyID,
			&run.BestResultID,
			&terminationReason,
			&run.CreatedAt,
			&run.UpdatedAt,
			&run.CompletedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan optimization run row: %w", err)
		}

		if err := json.Unmarshal(configJSON, &run.Config); err != nil {
			return nil, fmt.Errorf("failed to unmarshal config: %w", err)
		}

		run.Mode = domain.OptimizationModeFromString(modeStr)
		run.Status = domain.OptimizationStatusFromString(statusStr)

		run.Criteria = domain.OptimizationCriteria{}
		if minSharpe != nil {
			run.Criteria.MinSharpe = *minSharpe
		}
		if minProfitPct != nil {
			run.Criteria.MinProfitPct = *minProfitPct
		}
		if maxDrawdownPct != nil {
			run.Criteria.MaxDrawdownPct = *maxDrawdownPct
		}
		if minTrades != nil {
			run.Criteria.MinTrades = *minTrades
		}
		if minWinRate != nil {
			run.Criteria.MinWinRate = *minWinRate
		}
		if terminationReason != nil {
			run.TerminationReason = *terminationReason
		}

		runs = append(runs, run)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating optimization run rows: %w", err)
	}

	return runs, nil
}

// Helper functions to handle zero values as NULL.
func nullIfZeroFloat(v float64) *float64 {
	if v == 0 {
		return nil
	}
	return &v
}

func nullIfZeroInt(v int) *int {
	if v == 0 {
		return nil
	}
	return &v
}

func nullIfEmptyString(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

// Ensure interface implementations at compile time.
var _ OptimizationRepository = (*optimizationRepo)(nil)
