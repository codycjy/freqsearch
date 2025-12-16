package repository

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/saltfish/freqsearch/go-backend/internal/db"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// TestScoutRepository_RunOperations tests the full lifecycle of scout run operations.
func TestScoutRepository_RunOperations(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	ctx := context.Background()
	pool := setupTestDB(t)
	defer pool.Close()

	repo := NewScoutRepository(pool)

	t.Run("CreateAndGetRun", func(t *testing.T) {
		run := domain.NewScoutRun(
			domain.ScoutTriggerTypeManual,
			"test-user",
			"stratninja",
			10,
		)

		// Create run
		err := repo.CreateRun(ctx, run)
		require.NoError(t, err)

		// Get run by ID
		retrieved, err := repo.GetRunByID(ctx, run.ID)
		require.NoError(t, err)
		assert.Equal(t, run.ID, retrieved.ID)
		assert.Equal(t, run.TriggerType, retrieved.TriggerType)
		assert.Equal(t, run.TriggeredBy, retrieved.TriggeredBy)
		assert.Equal(t, run.Source, retrieved.Source)
		assert.Equal(t, run.MaxStrategies, retrieved.MaxStrategies)
		assert.Equal(t, domain.ScoutRunStatusPending, retrieved.Status)
	})

	t.Run("UpdateRunStatus", func(t *testing.T) {
		run := domain.NewScoutRun(
			domain.ScoutTriggerTypeScheduled,
			"scheduler",
			"github",
			5,
		)
		err := repo.CreateRun(ctx, run)
		require.NoError(t, err)

		// Update to running
		err = repo.UpdateRunStatus(ctx, run.ID, domain.ScoutRunStatusRunning, nil)
		require.NoError(t, err)

		retrieved, err := repo.GetRunByID(ctx, run.ID)
		require.NoError(t, err)
		assert.Equal(t, domain.ScoutRunStatusRunning, retrieved.Status)
		assert.NotNil(t, retrieved.StartedAt)

		// Update to failed with error
		errMsg := "test error"
		err = repo.UpdateRunStatus(ctx, run.ID, domain.ScoutRunStatusFailed, &errMsg)
		require.NoError(t, err)

		retrieved, err = repo.GetRunByID(ctx, run.ID)
		require.NoError(t, err)
		assert.Equal(t, domain.ScoutRunStatusFailed, retrieved.Status)
		assert.NotNil(t, retrieved.ErrorMessage)
		assert.Equal(t, errMsg, *retrieved.ErrorMessage)
		assert.NotNil(t, retrieved.CompletedAt)
	})

	t.Run("CompleteRun", func(t *testing.T) {
		run := domain.NewScoutRun(
			domain.ScoutTriggerTypeManual,
			"test-user",
			"stratninja",
			10,
		)
		err := repo.CreateRun(ctx, run)
		require.NoError(t, err)

		// Start the run first
		err = repo.UpdateRunStatus(ctx, run.ID, domain.ScoutRunStatusRunning, nil)
		require.NoError(t, err)

		// Complete with metrics
		metrics := &domain.ScoutMetrics{
			TotalFetched:      15,
			Validated:         12,
			ValidationFailed:  3,
			DuplicatesRemoved: 2,
			Submitted:         10,
		}

		err = repo.CompleteRun(ctx, run.ID, metrics)
		require.NoError(t, err)

		retrieved, err := repo.GetRunByID(ctx, run.ID)
		require.NoError(t, err)
		assert.Equal(t, domain.ScoutRunStatusCompleted, retrieved.Status)
		assert.NotNil(t, retrieved.Metrics)
		assert.Equal(t, 15, retrieved.Metrics.TotalFetched)
		assert.Equal(t, 12, retrieved.Metrics.Validated)
		assert.Equal(t, 10, retrieved.Metrics.Submitted)
	})

	t.Run("FailRun", func(t *testing.T) {
		run := domain.NewScoutRun(
			domain.ScoutTriggerTypeManual,
			"test-user",
			"stratninja",
			10,
		)
		err := repo.CreateRun(ctx, run)
		require.NoError(t, err)

		err = repo.FailRun(ctx, run.ID, "connection timeout")
		require.NoError(t, err)

		retrieved, err := repo.GetRunByID(ctx, run.ID)
		require.NoError(t, err)
		assert.Equal(t, domain.ScoutRunStatusFailed, retrieved.Status)
		assert.NotNil(t, retrieved.ErrorMessage)
		assert.Equal(t, "connection timeout", *retrieved.ErrorMessage)
	})

	t.Run("ListRuns", func(t *testing.T) {
		// Create test runs
		for i := 0; i < 5; i++ {
			run := domain.NewScoutRun(
				domain.ScoutTriggerTypeManual,
				"test-user",
				"stratninja",
				10,
			)
			err := repo.CreateRun(ctx, run)
			require.NoError(t, err)

			if i%2 == 0 {
				err = repo.UpdateRunStatus(ctx, run.ID, domain.ScoutRunStatusCompleted, nil)
				require.NoError(t, err)
			}
		}

		// List all runs
		query := domain.ScoutRunQuery{
			Page:     1,
			PageSize: 10,
		}
		runs, total, err := repo.ListRuns(ctx, query)
		require.NoError(t, err)
		assert.GreaterOrEqual(t, total, 5)
		assert.GreaterOrEqual(t, len(runs), 5)

		// Filter by status
		completedStatus := domain.ScoutRunStatusCompleted
		query.Status = &completedStatus
		runs, total, err = repo.ListRuns(ctx, query)
		require.NoError(t, err)
		assert.GreaterOrEqual(t, total, 3)
		for _, run := range runs {
			assert.Equal(t, domain.ScoutRunStatusCompleted, run.Status)
		}
	})

	t.Run("GetActiveRun", func(t *testing.T) {
		// Clear any existing active runs first
		cleanupActiveRuns(t, ctx, pool)

		// Create a running run
		activeRun := domain.NewScoutRun(
			domain.ScoutTriggerTypeManual,
			"test-user",
			"stratninja",
			10,
		)
		err := repo.CreateRun(ctx, activeRun)
		require.NoError(t, err)

		err = repo.UpdateRunStatus(ctx, activeRun.ID, domain.ScoutRunStatusRunning, nil)
		require.NoError(t, err)

		// Get active run
		retrieved, err := repo.GetActiveRun(ctx)
		require.NoError(t, err)
		require.NotNil(t, retrieved)
		assert.Equal(t, activeRun.ID, retrieved.ID)
		assert.Equal(t, domain.ScoutRunStatusRunning, retrieved.Status)

		// Complete the run
		err = repo.CompleteRun(ctx, activeRun.ID, nil)
		require.NoError(t, err)

		// No active run should be found
		retrieved, err = repo.GetActiveRun(ctx)
		require.NoError(t, err)
		assert.Nil(t, retrieved)
	})
}

// TestScoutRepository_ScheduleOperations tests schedule CRUD operations.
func TestScoutRepository_ScheduleOperations(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	ctx := context.Background()
	pool := setupTestDB(t)
	defer pool.Close()

	repo := NewScoutRepository(pool)

	t.Run("CreateAndGetSchedule", func(t *testing.T) {
		schedule := domain.NewScoutSchedule(
			"Daily StratNinja Scan",
			"0 0 * * *",
			"stratninja",
			20,
		)

		err := repo.CreateSchedule(ctx, schedule)
		require.NoError(t, err)

		// Get by ID
		retrieved, err := repo.GetScheduleByID(ctx, schedule.ID)
		require.NoError(t, err)
		assert.Equal(t, schedule.ID, retrieved.ID)
		assert.Equal(t, schedule.Name, retrieved.Name)
		assert.Equal(t, schedule.CronExpression, retrieved.CronExpression)
		assert.Equal(t, schedule.Source, retrieved.Source)
		assert.True(t, retrieved.Enabled)

		// Get by name
		retrieved, err = repo.GetScheduleByName(ctx, schedule.Name)
		require.NoError(t, err)
		assert.Equal(t, schedule.ID, retrieved.ID)
	})

	t.Run("UpdateSchedule", func(t *testing.T) {
		schedule := domain.NewScoutSchedule(
			"Weekly GitHub Scan",
			"0 0 * * 0",
			"github",
			15,
		)
		err := repo.CreateSchedule(ctx, schedule)
		require.NoError(t, err)

		// Update schedule
		schedule.CronExpression = "0 12 * * 0"
		schedule.MaxStrategies = 25
		schedule.Enabled = false

		err = repo.UpdateSchedule(ctx, schedule)
		require.NoError(t, err)

		retrieved, err := repo.GetScheduleByID(ctx, schedule.ID)
		require.NoError(t, err)
		assert.Equal(t, "0 12 * * 0", retrieved.CronExpression)
		assert.Equal(t, 25, retrieved.MaxStrategies)
		assert.False(t, retrieved.Enabled)
	})

	t.Run("DeleteSchedule", func(t *testing.T) {
		schedule := domain.NewScoutSchedule(
			"Test Schedule",
			"0 0 * * *",
			"stratninja",
			10,
		)
		err := repo.CreateSchedule(ctx, schedule)
		require.NoError(t, err)

		err = repo.DeleteSchedule(ctx, schedule.ID)
		require.NoError(t, err)

		_, err = repo.GetScheduleByID(ctx, schedule.ID)
		assert.Error(t, err)
		assert.ErrorIs(t, err, domain.ErrNotFound)
	})

	t.Run("ListSchedules", func(t *testing.T) {
		// Create test schedules
		for i := 0; i < 5; i++ {
			schedule := domain.NewScoutSchedule(
				"Test Schedule "+string(rune('A'+i)),
				"0 0 * * *",
				"stratninja",
				10,
			)
			if i%2 == 0 {
				schedule.Enabled = false
			}
			err := repo.CreateSchedule(ctx, schedule)
			require.NoError(t, err)
		}

		// List all schedules
		query := domain.ScoutScheduleQuery{
			Page:     1,
			PageSize: 10,
		}
		schedules, total, err := repo.ListSchedules(ctx, query)
		require.NoError(t, err)
		assert.GreaterOrEqual(t, total, 5)
		assert.GreaterOrEqual(t, len(schedules), 5)

		// Filter by enabled
		enabled := true
		query.Enabled = &enabled
		schedules, total, err = repo.ListSchedules(ctx, query)
		require.NoError(t, err)
		for _, schedule := range schedules {
			assert.True(t, schedule.Enabled)
		}
	})

	t.Run("GetActiveSchedules", func(t *testing.T) {
		// Create some enabled schedules
		for i := 0; i < 3; i++ {
			schedule := domain.NewScoutSchedule(
				"Active Schedule "+string(rune('A'+i)),
				"0 0 * * *",
				"stratninja",
				10,
			)
			schedule.Enabled = true
			err := repo.CreateSchedule(ctx, schedule)
			require.NoError(t, err)
		}

		schedules, err := repo.GetActiveSchedules(ctx)
		require.NoError(t, err)
		assert.GreaterOrEqual(t, len(schedules), 3)
		for _, schedule := range schedules {
			assert.True(t, schedule.Enabled)
		}
	})

	t.Run("UpdateScheduleLastRun", func(t *testing.T) {
		schedule := domain.NewScoutSchedule(
			"Test Last Run",
			"0 0 * * *",
			"stratninja",
			10,
		)
		err := repo.CreateSchedule(ctx, schedule)
		require.NoError(t, err)

		runID := uuid.New()
		err = repo.UpdateScheduleLastRun(ctx, schedule.ID, runID)
		require.NoError(t, err)

		retrieved, err := repo.GetScheduleByID(ctx, schedule.ID)
		require.NoError(t, err)
		assert.NotNil(t, retrieved.LastRunID)
		assert.Equal(t, runID, *retrieved.LastRunID)
		assert.NotNil(t, retrieved.LastRunAt)
	})

	t.Run("UpdateScheduleNextRun", func(t *testing.T) {
		schedule := domain.NewScoutSchedule(
			"Test Next Run",
			"0 0 * * *",
			"stratninja",
			10,
		)
		err := repo.CreateSchedule(ctx, schedule)
		require.NoError(t, err)

		nextRun := time.Now().Add(24 * time.Hour)
		err = repo.UpdateScheduleNextRun(ctx, schedule.ID, nextRun)
		require.NoError(t, err)

		retrieved, err := repo.GetScheduleByID(ctx, schedule.ID)
		require.NoError(t, err)
		assert.NotNil(t, retrieved.NextRunAt)
		assert.WithinDuration(t, nextRun, *retrieved.NextRunAt, time.Second)
	})
}

// TestScoutRepository_NotFound tests error handling for non-existent records.
func TestScoutRepository_NotFound(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	ctx := context.Background()
	pool := setupTestDB(t)
	defer pool.Close()

	repo := NewScoutRepository(pool)
	nonExistentID := uuid.New()

	t.Run("GetRunByID_NotFound", func(t *testing.T) {
		_, err := repo.GetRunByID(ctx, nonExistentID)
		assert.Error(t, err)
		assert.ErrorIs(t, err, domain.ErrNotFound)
	})

	t.Run("UpdateRun_NotFound", func(t *testing.T) {
		run := domain.NewScoutRun(
			domain.ScoutTriggerTypeManual,
			"test",
			"stratninja",
			10,
		)
		run.ID = nonExistentID

		err := repo.UpdateRun(ctx, run)
		assert.Error(t, err)
	})

	t.Run("GetScheduleByID_NotFound", func(t *testing.T) {
		_, err := repo.GetScheduleByID(ctx, nonExistentID)
		assert.Error(t, err)
		assert.ErrorIs(t, err, domain.ErrNotFound)
	})

	t.Run("DeleteSchedule_NotFound", func(t *testing.T) {
		err := repo.DeleteSchedule(ctx, nonExistentID)
		assert.Error(t, err)
	})
}

// Helper function to clean up active runs in tests.
func cleanupActiveRuns(t *testing.T, ctx context.Context, pool *db.Pool) {
	_, err := pool.Exec(ctx, `
		UPDATE scout_runs
		SET status = 'cancelled', completed_at = NOW()
		WHERE status IN ('pending', 'running')
	`)
	require.NoError(t, err)
}
