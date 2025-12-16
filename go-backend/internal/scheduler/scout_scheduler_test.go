package scheduler

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap/zaptest"

	"github.com/saltfish/freqsearch/go-backend/internal/db/repository"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
	"github.com/saltfish/freqsearch/go-backend/internal/events"
)

// mockScoutRepository is a mock implementation of ScoutRepository for testing.
type mockScoutRepository struct {
	schedules       []*domain.ScoutSchedule
	runs            []*domain.ScoutRun
	lastRunUpdates  map[uuid.UUID]uuid.UUID
	nextRunUpdates  map[uuid.UUID]time.Time
	createRunErr    error
	getSchedulesErr error
}

func newMockScoutRepository() *mockScoutRepository {
	return &mockScoutRepository{
		schedules:      []*domain.ScoutSchedule{},
		runs:           []*domain.ScoutRun{},
		lastRunUpdates: make(map[uuid.UUID]uuid.UUID),
		nextRunUpdates: make(map[uuid.UUID]time.Time),
	}
}

func (m *mockScoutRepository) CreateRun(ctx context.Context, run *domain.ScoutRun) error {
	if m.createRunErr != nil {
		return m.createRunErr
	}
	m.runs = append(m.runs, run)
	return nil
}

func (m *mockScoutRepository) GetActiveSchedules(ctx context.Context) ([]*domain.ScoutSchedule, error) {
	if m.getSchedulesErr != nil {
		return nil, m.getSchedulesErr
	}
	return m.schedules, nil
}

func (m *mockScoutRepository) UpdateScheduleLastRun(ctx context.Context, scheduleID, runID uuid.UUID) error {
	m.lastRunUpdates[scheduleID] = runID
	return nil
}

func (m *mockScoutRepository) UpdateScheduleNextRun(ctx context.Context, scheduleID uuid.UUID, nextRunAt time.Time) error {
	m.nextRunUpdates[scheduleID] = nextRunAt
	return nil
}

// Implement remaining ScoutRepository methods (not used in tests)
func (m *mockScoutRepository) GetRunByID(ctx context.Context, id uuid.UUID) (*domain.ScoutRun, error) {
	return nil, nil
}
func (m *mockScoutRepository) UpdateRun(ctx context.Context, run *domain.ScoutRun) error {
	return nil
}
func (m *mockScoutRepository) UpdateRunStatus(ctx context.Context, id uuid.UUID, status domain.ScoutRunStatus, errorMsg *string) error {
	return nil
}
func (m *mockScoutRepository) CompleteRun(ctx context.Context, id uuid.UUID, metrics *domain.ScoutMetrics) error {
	return nil
}
func (m *mockScoutRepository) FailRun(ctx context.Context, id uuid.UUID, errorMsg string) error {
	return nil
}
func (m *mockScoutRepository) ListRuns(ctx context.Context, query domain.ScoutRunQuery) ([]*domain.ScoutRun, int, error) {
	return nil, 0, nil
}
func (m *mockScoutRepository) GetActiveRun(ctx context.Context) (*domain.ScoutRun, error) {
	return nil, nil
}
func (m *mockScoutRepository) CreateSchedule(ctx context.Context, schedule *domain.ScoutSchedule) error {
	return nil
}
func (m *mockScoutRepository) GetScheduleByID(ctx context.Context, id uuid.UUID) (*domain.ScoutSchedule, error) {
	return nil, nil
}
func (m *mockScoutRepository) GetScheduleByName(ctx context.Context, name string) (*domain.ScoutSchedule, error) {
	return nil, nil
}
func (m *mockScoutRepository) UpdateSchedule(ctx context.Context, schedule *domain.ScoutSchedule) error {
	return nil
}
func (m *mockScoutRepository) DeleteSchedule(ctx context.Context, id uuid.UUID) error {
	return nil
}
func (m *mockScoutRepository) ListSchedules(ctx context.Context, query domain.ScoutScheduleQuery) ([]*domain.ScoutSchedule, int, error) {
	return nil, 0, nil
}

// Helper to create mock Repositories
func newMockRepositories(scout *mockScoutRepository) *repository.Repositories {
	return &repository.Repositories{
		Scout: scout,
		// Other repositories can be nil for these tests
		Strategy:     nil,
		BacktestJob:  nil,
		Result:       nil,
		Optimization: nil,
	}
}

// mockEventPublisher is a mock implementation of events.Publisher for testing.
type mockEventPublisher struct {
	publishedEvents []interface{}
}

func newMockEventPublisher() *mockEventPublisher {
	return &mockEventPublisher{
		publishedEvents: []interface{}{},
	}
}

func (m *mockEventPublisher) Publish(ctx context.Context, routingKey string, event interface{}) error {
	m.publishedEvents = append(m.publishedEvents, event)
	return nil
}

func (m *mockEventPublisher) PublishTaskRunning(job *domain.BacktestJob) error {
	return nil
}

func (m *mockEventPublisher) PublishTaskCompleted(job *domain.BacktestJob, result *domain.BacktestResult) error {
	return nil
}

func (m *mockEventPublisher) PublishTaskFailed(job *domain.BacktestJob, errMsg string) error {
	return nil
}

func (m *mockEventPublisher) PublishTaskCancelled(job *domain.BacktestJob) error {
	return nil
}

func (m *mockEventPublisher) PublishScoutTrigger(event *events.ScoutTriggerEvent) error {
	m.publishedEvents = append(m.publishedEvents, event)
	return nil
}

func (m *mockEventPublisher) PublishScoutCancelled(runID uuid.UUID) error {
	return nil
}

func (m *mockEventPublisher) Close() error {
	return nil
}

func TestNewScoutScheduler(t *testing.T) {
	logger := zaptest.NewLogger(t)
	mockRepos := newMockRepositories(newMockScoutRepository())
	publisher := newMockEventPublisher()

	scheduler := NewScoutScheduler(mockRepos, publisher, logger)

	assert.NotNil(t, scheduler)
	assert.NotNil(t, scheduler.cronParser)
	assert.NotNil(t, scheduler.schedules)
	assert.Equal(t, 30*time.Second, scheduler.pollInterval)
}

func TestScoutScheduler_LoadSchedules(t *testing.T) {
	logger := zaptest.NewLogger(t)
	mockScout := newMockScoutRepository()
	mockRepos := newMockRepositories(mockScout)
	publisher := newMockEventPublisher()

	// Add test schedule
	schedule := domain.NewScoutSchedule("test-schedule", "*/5 * * * *", "stratninja", 10)
	mockScout.schedules = []*domain.ScoutSchedule{schedule}

	scheduler := NewScoutScheduler(mockRepos, publisher, logger)
	err := scheduler.Start()
	require.NoError(t, err)
	defer scheduler.Stop()

	// Verify schedule was loaded
	scheduler.mu.RLock()
	assert.Equal(t, 1, len(scheduler.schedules))
	task, exists := scheduler.schedules[schedule.ID]
	assert.True(t, exists)
	assert.Equal(t, schedule.ID, task.Schedule.ID)
	assert.False(t, task.NextRun.IsZero())
	scheduler.mu.RUnlock()

	// Verify next run was updated in database
	nextRun, exists := mockScout.nextRunUpdates[schedule.ID]
	assert.True(t, exists)
	assert.False(t, nextRun.IsZero())
}

func TestScoutScheduler_ReloadSchedules(t *testing.T) {
	logger := zaptest.NewLogger(t)
	mockScout := newMockScoutRepository()
	mockRepos := newMockRepositories(mockScout)
	publisher := newMockEventPublisher()

	scheduler := NewScoutScheduler(mockRepos, publisher, logger)
	err := scheduler.Start()
	require.NoError(t, err)
	defer scheduler.Stop()

	// Add new schedule
	schedule := domain.NewScoutSchedule("new-schedule", "0 0 * * *", "github", 20)
	mockScout.schedules = []*domain.ScoutSchedule{schedule}

	// Reload schedules
	err = scheduler.ReloadSchedules()
	require.NoError(t, err)

	// Verify new schedule was loaded
	scheduler.mu.RLock()
	assert.Equal(t, 1, len(scheduler.schedules))
	task, exists := scheduler.schedules[schedule.ID]
	assert.True(t, exists)
	assert.Equal(t, "new-schedule", task.Schedule.Name)
	scheduler.mu.RUnlock()
}

func TestScoutScheduler_ExecuteSchedule(t *testing.T) {
	logger := zaptest.NewLogger(t)
	mockScout := newMockScoutRepository()
	mockRepos := newMockRepositories(mockScout)
	publisher := newMockEventPublisher()

	schedule := domain.NewScoutSchedule("test-exec", "* * * * *", "stratninja", 15)

	scheduler := NewScoutScheduler(mockRepos, publisher, logger)
	scheduler.ctx, scheduler.cancel = context.WithCancel(context.Background())
	defer scheduler.cancel()

	// Execute schedule
	scheduler.executeSchedule(schedule)

	// Verify run was created
	assert.Equal(t, 1, len(mockScout.runs))
	run := mockScout.runs[0]
	assert.Equal(t, domain.ScoutTriggerTypeScheduled, run.TriggerType)
	assert.Equal(t, schedule.Name, run.TriggeredBy)
	assert.Equal(t, schedule.Source, run.Source)
	assert.Equal(t, schedule.MaxStrategies, run.MaxStrategies)
	assert.Equal(t, domain.ScoutRunStatusPending, run.Status)

	// Verify last run was updated
	lastRunID, exists := mockScout.lastRunUpdates[schedule.ID]
	assert.True(t, exists)
	assert.Equal(t, run.ID, lastRunID)

	// Verify event was published
	assert.Equal(t, 1, len(publisher.publishedEvents))
	event, ok := publisher.publishedEvents[0].(*events.ScoutTriggerEvent)
	assert.True(t, ok)
	assert.Equal(t, run.ID, event.RunID)
	assert.Equal(t, schedule.Source, event.Source)
	assert.Equal(t, schedule.MaxStrategies, event.MaxStrategies)
}

func TestScoutScheduler_CalculateNextRun(t *testing.T) {
	logger := zaptest.NewLogger(t)
	mockScout := newMockScoutRepository()
	mockRepos := newMockRepositories(mockScout)
	publisher := newMockEventPublisher()

	scheduler := NewScoutScheduler(mockRepos, publisher, logger)

	tests := []struct {
		name        string
		cronExpr    string
		expectError bool
	}{
		{
			name:        "valid every 5 minutes",
			cronExpr:    "*/5 * * * *",
			expectError: false,
		},
		{
			name:        "valid daily at midnight",
			cronExpr:    "0 0 * * *",
			expectError: false,
		},
		{
			name:        "valid hourly",
			cronExpr:    "0 * * * *",
			expectError: false,
		},
		{
			name:        "invalid expression",
			cronExpr:    "invalid",
			expectError: true,
		},
		{
			name:        "invalid too many fields",
			cronExpr:    "0 0 0 * * * *",
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			nextRun, err := scheduler.calculateNextRun(tt.cronExpr)

			if tt.expectError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
				assert.True(t, nextRun.After(time.Now()))
			}
		})
	}
}

func TestScoutScheduler_CheckSchedules(t *testing.T) {
	logger := zaptest.NewLogger(t)
	mockScout := newMockScoutRepository()
	mockRepos := newMockRepositories(mockScout)
	publisher := newMockEventPublisher()

	scheduler := NewScoutScheduler(mockRepos, publisher, logger)
	scheduler.ctx, scheduler.cancel = context.WithCancel(context.Background())
	defer scheduler.cancel()

	// Create a schedule that's due now
	schedule := domain.NewScoutSchedule("due-schedule", "* * * * *", "stratninja", 5)
	pastTime := time.Now().Add(-1 * time.Minute)

	// Parse cron and add to scheduler
	cronSpec, err := scheduler.cronParser.Parse(schedule.CronExpression)
	require.NoError(t, err)

	scheduler.schedules[schedule.ID] = &scheduledTask{
		Schedule: schedule,
		NextRun:  pastTime,
		CronSpec: cronSpec,
	}

	// Check schedules
	scheduler.checkSchedules()

	// Give goroutines time to execute
	time.Sleep(100 * time.Millisecond)

	// Verify run was created
	assert.GreaterOrEqual(t, len(mockScout.runs), 1)
}

func TestScoutScheduler_StartStop(t *testing.T) {
	logger := zaptest.NewLogger(t)
	mockScout := newMockScoutRepository()
	mockRepos := newMockRepositories(mockScout)
	publisher := newMockEventPublisher()

	scheduler := NewScoutScheduler(mockRepos, publisher, logger)

	// Start scheduler
	err := scheduler.Start()
	require.NoError(t, err)

	// Verify context and ticker are created
	assert.NotNil(t, scheduler.ctx)
	assert.NotNil(t, scheduler.cancel)
	assert.NotNil(t, scheduler.ticker)

	// Stop scheduler
	err = scheduler.Stop()
	require.NoError(t, err)

	// Verify context is cancelled
	select {
	case <-scheduler.ctx.Done():
		// Context cancelled as expected
	default:
		t.Error("Context should be cancelled after Stop()")
	}
}

func TestScoutScheduler_InvalidCronExpression(t *testing.T) {
	logger := zaptest.NewLogger(t)
	mockScout := newMockScoutRepository()
	mockRepos := newMockRepositories(mockScout)
	publisher := newMockEventPublisher()

	// Add schedule with invalid cron expression
	schedule := domain.NewScoutSchedule("invalid-cron", "invalid-expression", "stratninja", 10)
	mockScout.schedules = []*domain.ScoutSchedule{schedule}

	scheduler := NewScoutScheduler(mockRepos, publisher, logger)
	err := scheduler.Start()
	require.NoError(t, err)
	defer scheduler.Stop()

	// Verify invalid schedule was not loaded
	scheduler.mu.RLock()
	assert.Equal(t, 0, len(scheduler.schedules))
	scheduler.mu.RUnlock()
}
