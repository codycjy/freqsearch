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

// scoutRepo implements ScoutRepository using PostgreSQL.
type scoutRepo struct {
	pool *db.Pool
}

// NewScoutRepository creates a new PostgreSQL scout repository.
func NewScoutRepository(pool *db.Pool) ScoutRepository {
	return &scoutRepo{pool: pool}
}

// =============================================================================
// Run Operations
// =============================================================================

// CreateRun creates a new scout run.
func (r *scoutRepo) CreateRun(ctx context.Context, run *domain.ScoutRun) error {
	var metricsJSON []byte
	var err error
	if run.Metrics != nil {
		metricsJSON, err = json.Marshal(run.Metrics)
		if err != nil {
			return fmt.Errorf("failed to marshal metrics: %w", err)
		}
	}

	query := `
		INSERT INTO scout_runs (
			id, trigger_type, triggered_by, source, max_strategies,
			status, error_message, metrics,
			created_at, started_at, completed_at
		) VALUES (
			$1, $2, $3, $4, $5,
			$6, $7, $8,
			$9, $10, $11
		)
	`

	_, err = r.pool.Exec(ctx, query,
		run.ID,
		run.TriggerType.String(),
		nullIfEmptyString(run.TriggeredBy),
		run.Source,
		run.MaxStrategies,
		run.Status.String(),
		run.ErrorMessage,
		metricsJSON,
		run.CreatedAt,
		run.StartedAt,
		run.CompletedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to create scout run: %w", err)
	}

	return nil
}

// GetRunByID retrieves a scout run by ID.
func (r *scoutRepo) GetRunByID(ctx context.Context, id uuid.UUID) (*domain.ScoutRun, error) {
	query := `
		SELECT
			id, trigger_type, triggered_by, source, max_strategies,
			status, error_message, metrics,
			created_at, started_at, completed_at
		FROM scout_runs
		WHERE id = $1
	`

	return r.scanRun(r.pool.QueryRow(ctx, query, id))
}

// UpdateRun updates an existing scout run.
func (r *scoutRepo) UpdateRun(ctx context.Context, run *domain.ScoutRun) error {
	var metricsJSON []byte
	var err error
	if run.Metrics != nil {
		metricsJSON, err = json.Marshal(run.Metrics)
		if err != nil {
			return fmt.Errorf("failed to marshal metrics: %w", err)
		}
	}

	query := `
		UPDATE scout_runs SET
			trigger_type = $2,
			triggered_by = $3,
			source = $4,
			max_strategies = $5,
			status = $6,
			error_message = $7,
			metrics = $8,
			started_at = $9,
			completed_at = $10
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query,
		run.ID,
		run.TriggerType.String(),
		nullIfEmptyString(run.TriggeredBy),
		run.Source,
		run.MaxStrategies,
		run.Status.String(),
		run.ErrorMessage,
		metricsJSON,
		run.StartedAt,
		run.CompletedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to update scout run: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("scout_run", run.ID.String())
	}

	return nil
}

// UpdateRunStatus updates the status of a scout run with optional error message.
func (r *scoutRepo) UpdateRunStatus(
	ctx context.Context,
	id uuid.UUID,
	status domain.ScoutRunStatus,
	errorMsg *string,
) error {
	query := `
		UPDATE scout_runs SET
			status = $2,
			error_message = $3,
			started_at = CASE
				WHEN $2 = 'running' AND started_at IS NULL THEN NOW()
				ELSE started_at
			END,
			completed_at = CASE
				WHEN $2 IN ('completed', 'failed', 'cancelled') THEN NOW()
				ELSE completed_at
			END
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query, id, status.String(), errorMsg)
	if err != nil {
		return fmt.Errorf("failed to update scout run status: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("scout_run", id.String())
	}

	return nil
}

// CompleteRun marks a scout run as completed with metrics.
func (r *scoutRepo) CompleteRun(ctx context.Context, id uuid.UUID, metrics *domain.ScoutMetrics) error {
	var metricsJSON []byte
	var err error
	if metrics != nil {
		metricsJSON, err = json.Marshal(metrics)
		if err != nil {
			return fmt.Errorf("failed to marshal metrics: %w", err)
		}
	}

	query := `
		UPDATE scout_runs SET
			status = 'completed',
			metrics = $2,
			completed_at = NOW()
		WHERE id = $1 AND status IN ('pending', 'running')
	`

	result, err := r.pool.Exec(ctx, query, id, metricsJSON)
	if err != nil {
		return fmt.Errorf("failed to complete scout run: %w", err)
	}

	if result.RowsAffected() == 0 {
		// Check if run exists and its status
		var status string
		err := r.pool.QueryRow(ctx, "SELECT status FROM scout_runs WHERE id = $1", id).Scan(&status)
		if err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				return domain.NewNotFoundError("scout_run", id.String())
			}
			return fmt.Errorf("failed to check run status: %w", err)
		}
		return fmt.Errorf("cannot complete scout run in status: %s", status)
	}

	return nil
}

// FailRun marks a scout run as failed with an error message.
func (r *scoutRepo) FailRun(ctx context.Context, id uuid.UUID, errorMsg string) error {
	query := `
		UPDATE scout_runs SET
			status = 'failed',
			error_message = $2,
			completed_at = NOW()
		WHERE id = $1 AND status IN ('pending', 'running')
	`

	result, err := r.pool.Exec(ctx, query, id, errorMsg)
	if err != nil {
		return fmt.Errorf("failed to fail scout run: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("scout_run", id.String())
	}

	return nil
}

// ListRuns lists scout runs with filters and pagination.
func (r *scoutRepo) ListRuns(
	ctx context.Context,
	query domain.ScoutRunQuery,
) ([]*domain.ScoutRun, int, error) {
	query.SetDefaults()

	var conditions []string
	var args []interface{}
	argNum := 1

	if query.Status != nil {
		conditions = append(conditions, fmt.Sprintf("status = $%d", argNum))
		args = append(args, query.Status.String())
		argNum++
	}

	if query.Source != nil {
		conditions = append(conditions, fmt.Sprintf("source = $%d", argNum))
		args = append(args, *query.Source)
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
	case "created_at", "":
		orderColumn = "created_at"
	case "started_at":
		orderColumn = "started_at"
	case "completed_at":
		orderColumn = "completed_at"
	case "status":
		orderColumn = "status"
	}

	orderDir := "DESC"
	if query.Ascending {
		orderDir = "ASC"
	}

	// Count total
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM scout_runs %s", whereClause)
	var totalCount int
	err := r.pool.QueryRow(ctx, countQuery, args...).Scan(&totalCount)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to count scout runs: %w", err)
	}

	// Query runs
	selectQuery := fmt.Sprintf(`
		SELECT
			id, trigger_type, triggered_by, source, max_strategies,
			status, error_message, metrics,
			created_at, started_at, completed_at
		FROM scout_runs
		%s
		ORDER BY %s %s
		LIMIT $%d OFFSET $%d
	`, whereClause, orderColumn, orderDir, argNum, argNum+1)

	args = append(args, query.PageSize, query.Offset())

	rows, err := r.pool.Query(ctx, selectQuery, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to query scout runs: %w", err)
	}
	defer rows.Close()

	runs, err := r.scanRuns(rows)
	if err != nil {
		return nil, 0, err
	}

	return runs, totalCount, nil
}

// GetActiveRun retrieves the currently active (pending or running) scout run.
func (r *scoutRepo) GetActiveRun(ctx context.Context) (*domain.ScoutRun, error) {
	query := `
		SELECT
			id, trigger_type, triggered_by, source, max_strategies,
			status, error_message, metrics,
			created_at, started_at, completed_at
		FROM scout_runs
		WHERE status IN ('pending', 'running')
		ORDER BY created_at DESC
		LIMIT 1
	`

	run, err := r.scanRun(r.pool.QueryRow(ctx, query))
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			return nil, nil // No active run is not an error
		}
		return nil, err
	}

	return run, nil
}

// =============================================================================
// Schedule Operations
// =============================================================================

// CreateSchedule creates a new scout schedule.
func (r *scoutRepo) CreateSchedule(ctx context.Context, schedule *domain.ScoutSchedule) error {
	query := `
		INSERT INTO scout_schedules (
			id, name, cron_expression, source, max_strategies,
			enabled, last_run_id, last_run_at, next_run_at,
			created_at, updated_at
		) VALUES (
			$1, $2, $3, $4, $5,
			$6, $7, $8, $9,
			$10, $11
		)
	`

	_, err := r.pool.Exec(ctx, query,
		schedule.ID,
		schedule.Name,
		schedule.CronExpression,
		schedule.Source,
		schedule.MaxStrategies,
		schedule.Enabled,
		schedule.LastRunID,
		schedule.LastRunAt,
		schedule.NextRunAt,
		schedule.CreatedAt,
		schedule.UpdatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to create scout schedule: %w", err)
	}

	return nil
}

// GetScheduleByID retrieves a scout schedule by ID.
func (r *scoutRepo) GetScheduleByID(ctx context.Context, id uuid.UUID) (*domain.ScoutSchedule, error) {
	query := `
		SELECT
			id, name, cron_expression, source, max_strategies,
			enabled, last_run_id, last_run_at, next_run_at,
			created_at, updated_at
		FROM scout_schedules
		WHERE id = $1
	`

	return r.scanSchedule(r.pool.QueryRow(ctx, query, id))
}

// GetScheduleByName retrieves a scout schedule by name.
func (r *scoutRepo) GetScheduleByName(ctx context.Context, name string) (*domain.ScoutSchedule, error) {
	query := `
		SELECT
			id, name, cron_expression, source, max_strategies,
			enabled, last_run_id, last_run_at, next_run_at,
			created_at, updated_at
		FROM scout_schedules
		WHERE name = $1
	`

	return r.scanSchedule(r.pool.QueryRow(ctx, query, name))
}

// UpdateSchedule updates an existing scout schedule.
func (r *scoutRepo) UpdateSchedule(ctx context.Context, schedule *domain.ScoutSchedule) error {
	query := `
		UPDATE scout_schedules SET
			name = $2,
			cron_expression = $3,
			source = $4,
			max_strategies = $5,
			enabled = $6,
			last_run_id = $7,
			last_run_at = $8,
			next_run_at = $9,
			updated_at = NOW()
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query,
		schedule.ID,
		schedule.Name,
		schedule.CronExpression,
		schedule.Source,
		schedule.MaxStrategies,
		schedule.Enabled,
		schedule.LastRunID,
		schedule.LastRunAt,
		schedule.NextRunAt,
	)
	if err != nil {
		return fmt.Errorf("failed to update scout schedule: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("scout_schedule", schedule.ID.String())
	}

	return nil
}

// DeleteSchedule deletes a scout schedule.
func (r *scoutRepo) DeleteSchedule(ctx context.Context, id uuid.UUID) error {
	query := `DELETE FROM scout_schedules WHERE id = $1`

	result, err := r.pool.Exec(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to delete scout schedule: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("scout_schedule", id.String())
	}

	return nil
}

// ListSchedules lists scout schedules with filters and pagination.
func (r *scoutRepo) ListSchedules(
	ctx context.Context,
	query domain.ScoutScheduleQuery,
) ([]*domain.ScoutSchedule, int, error) {
	query.SetDefaults()

	var conditions []string
	var args []interface{}
	argNum := 1

	if query.Enabled != nil {
		conditions = append(conditions, fmt.Sprintf("enabled = $%d", argNum))
		args = append(args, *query.Enabled)
		argNum++
	}

	if query.Source != nil {
		conditions = append(conditions, fmt.Sprintf("source = $%d", argNum))
		args = append(args, *query.Source)
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
	case "created_at", "":
		orderColumn = "created_at"
	case "last_run_at":
		orderColumn = "last_run_at"
	case "next_run_at":
		orderColumn = "next_run_at"
	}

	orderDir := "DESC"
	if query.Ascending {
		orderDir = "ASC"
	}

	// Count total
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM scout_schedules %s", whereClause)
	var totalCount int
	err := r.pool.QueryRow(ctx, countQuery, args...).Scan(&totalCount)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to count scout schedules: %w", err)
	}

	// Query schedules
	selectQuery := fmt.Sprintf(`
		SELECT
			id, name, cron_expression, source, max_strategies,
			enabled, last_run_id, last_run_at, next_run_at,
			created_at, updated_at
		FROM scout_schedules
		%s
		ORDER BY %s %s
		LIMIT $%d OFFSET $%d
	`, whereClause, orderColumn, orderDir, argNum, argNum+1)

	args = append(args, query.PageSize, query.Offset())

	rows, err := r.pool.Query(ctx, selectQuery, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to query scout schedules: %w", err)
	}
	defer rows.Close()

	schedules, err := r.scanSchedules(rows)
	if err != nil {
		return nil, 0, err
	}

	return schedules, totalCount, nil
}

// GetActiveSchedules retrieves all enabled schedules.
func (r *scoutRepo) GetActiveSchedules(ctx context.Context) ([]*domain.ScoutSchedule, error) {
	query := `
		SELECT
			id, name, cron_expression, source, max_strategies,
			enabled, last_run_id, last_run_at, next_run_at,
			created_at, updated_at
		FROM scout_schedules
		WHERE enabled = true
		ORDER BY next_run_at ASC NULLS LAST
	`

	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query active scout schedules: %w", err)
	}
	defer rows.Close()

	return r.scanSchedules(rows)
}

// UpdateScheduleLastRun updates the last run information for a schedule.
func (r *scoutRepo) UpdateScheduleLastRun(ctx context.Context, scheduleID, runID uuid.UUID) error {
	query := `
		UPDATE scout_schedules SET
			last_run_id = $2,
			last_run_at = NOW(),
			updated_at = NOW()
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query, scheduleID, runID)
	if err != nil {
		return fmt.Errorf("failed to update schedule last run: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("scout_schedule", scheduleID.String())
	}

	return nil
}

// UpdateScheduleNextRun updates the next run time for a schedule.
func (r *scoutRepo) UpdateScheduleNextRun(ctx context.Context, scheduleID uuid.UUID, nextRunAt time.Time) error {
	query := `
		UPDATE scout_schedules SET
			next_run_at = $2,
			updated_at = NOW()
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query, scheduleID, nextRunAt)
	if err != nil {
		return fmt.Errorf("failed to update schedule next run: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("scout_schedule", scheduleID.String())
	}

	return nil
}

// =============================================================================
// Helper Functions
// =============================================================================

// scanRun scans a single row into a ScoutRun.
func (r *scoutRepo) scanRun(row pgx.Row) (*domain.ScoutRun, error) {
	run := &domain.ScoutRun{}
	var triggerTypeStr, statusStr string
	var triggeredBy *string
	var metricsJSON []byte

	err := row.Scan(
		&run.ID,
		&triggerTypeStr,
		&triggeredBy,
		&run.Source,
		&run.MaxStrategies,
		&statusStr,
		&run.ErrorMessage,
		&metricsJSON,
		&run.CreatedAt,
		&run.StartedAt,
		&run.CompletedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domain.ErrNotFound
		}
		return nil, fmt.Errorf("failed to scan scout run: %w", err)
	}

	if triggeredBy != nil {
		run.TriggeredBy = *triggeredBy
	}

	run.TriggerType = domain.ScoutTriggerTypeFromString(triggerTypeStr)
	run.Status = domain.ScoutRunStatusFromString(statusStr)

	if len(metricsJSON) > 0 {
		run.Metrics = &domain.ScoutMetrics{}
		if err := json.Unmarshal(metricsJSON, run.Metrics); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metrics: %w", err)
		}
	}

	return run, nil
}

// scanRuns scans multiple rows into a slice of ScoutRun.
func (r *scoutRepo) scanRuns(rows pgx.Rows) ([]*domain.ScoutRun, error) {
	var runs []*domain.ScoutRun

	for rows.Next() {
		run := &domain.ScoutRun{}
		var triggerTypeStr, statusStr string
		var triggeredBy *string
		var metricsJSON []byte

		err := rows.Scan(
			&run.ID,
			&triggerTypeStr,
			&triggeredBy,
			&run.Source,
			&run.MaxStrategies,
			&statusStr,
			&run.ErrorMessage,
			&metricsJSON,
			&run.CreatedAt,
			&run.StartedAt,
			&run.CompletedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan scout run row: %w", err)
		}

		if triggeredBy != nil {
			run.TriggeredBy = *triggeredBy
		}

		run.TriggerType = domain.ScoutTriggerTypeFromString(triggerTypeStr)
		run.Status = domain.ScoutRunStatusFromString(statusStr)

		if len(metricsJSON) > 0 {
			run.Metrics = &domain.ScoutMetrics{}
			if err := json.Unmarshal(metricsJSON, run.Metrics); err != nil {
				return nil, fmt.Errorf("failed to unmarshal metrics: %w", err)
			}
		}

		runs = append(runs, run)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating scout run rows: %w", err)
	}

	return runs, nil
}

// scanSchedule scans a single row into a ScoutSchedule.
func (r *scoutRepo) scanSchedule(row pgx.Row) (*domain.ScoutSchedule, error) {
	schedule := &domain.ScoutSchedule{}

	err := row.Scan(
		&schedule.ID,
		&schedule.Name,
		&schedule.CronExpression,
		&schedule.Source,
		&schedule.MaxStrategies,
		&schedule.Enabled,
		&schedule.LastRunID,
		&schedule.LastRunAt,
		&schedule.NextRunAt,
		&schedule.CreatedAt,
		&schedule.UpdatedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domain.ErrNotFound
		}
		return nil, fmt.Errorf("failed to scan scout schedule: %w", err)
	}

	return schedule, nil
}

// scanSchedules scans multiple rows into a slice of ScoutSchedule.
func (r *scoutRepo) scanSchedules(rows pgx.Rows) ([]*domain.ScoutSchedule, error) {
	var schedules []*domain.ScoutSchedule

	for rows.Next() {
		schedule := &domain.ScoutSchedule{}

		err := rows.Scan(
			&schedule.ID,
			&schedule.Name,
			&schedule.CronExpression,
			&schedule.Source,
			&schedule.MaxStrategies,
			&schedule.Enabled,
			&schedule.LastRunID,
			&schedule.LastRunAt,
			&schedule.NextRunAt,
			&schedule.CreatedAt,
			&schedule.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan scout schedule row: %w", err)
		}

		schedules = append(schedules, schedule)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating scout schedule rows: %w", err)
	}

	return schedules, nil
}

// Ensure interface implementation at compile time.
var _ ScoutRepository = (*scoutRepo)(nil)
