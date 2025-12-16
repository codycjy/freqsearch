package scheduler

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/robfig/cron/v3"
	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/db/repository"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
	"github.com/saltfish/freqsearch/go-backend/internal/events"
)

// ScoutScheduler manages cron-based Scout runs.
type ScoutScheduler struct {
	repos          *repository.Repositories
	eventPublisher events.Publisher
	logger         *zap.Logger

	cronParser   cron.Parser
	schedules    map[uuid.UUID]*scheduledTask
	mu           sync.RWMutex
	pollInterval time.Duration

	ticker *time.Ticker
	ctx    context.Context
	cancel context.CancelFunc
	wg     sync.WaitGroup
}

// scheduledTask tracks a scheduled Scout run.
type scheduledTask struct {
	Schedule *domain.ScoutSchedule
	NextRun  time.Time
	CronSpec cron.Schedule
}

// NewScoutScheduler creates a new Scout scheduler.
func NewScoutScheduler(
	repos *repository.Repositories,
	publisher events.Publisher,
	logger *zap.Logger,
) *ScoutScheduler {
	return &ScoutScheduler{
		repos:          repos,
		eventPublisher: publisher,
		logger:         logger,
		cronParser:     cron.NewParser(cron.Minute | cron.Hour | cron.Dom | cron.Month | cron.Dow),
		schedules:      make(map[uuid.UUID]*scheduledTask),
		pollInterval:   30 * time.Second,
	}
}

// Start starts the scheduler.
func (s *ScoutScheduler) Start() error {
	s.logger.Info("Starting Scout scheduler",
		zap.Duration("poll_interval", s.pollInterval),
	)

	// Create cancellable context
	s.ctx, s.cancel = context.WithCancel(context.Background())

	// Load schedules from database
	if err := s.loadSchedules(); err != nil {
		return fmt.Errorf("failed to load schedules: %w", err)
	}

	// Start ticker loop
	s.ticker = time.NewTicker(s.pollInterval)
	s.wg.Add(1)
	go s.schedulerLoop()

	s.logger.Info("Scout scheduler started",
		zap.Int("active_schedules", len(s.schedules)),
	)

	return nil
}

// Stop gracefully stops the scheduler.
func (s *ScoutScheduler) Stop() error {
	s.logger.Info("Stopping Scout scheduler")

	// Cancel context
	if s.cancel != nil {
		s.cancel()
	}

	// Stop ticker
	if s.ticker != nil {
		s.ticker.Stop()
	}

	// Wait for goroutines
	s.wg.Wait()

	s.logger.Info("Scout scheduler stopped")
	return nil
}

// ReloadSchedules reloads schedules from the database.
func (s *ScoutScheduler) ReloadSchedules() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.logger.Info("Reloading Scout schedules")

	// Fetch active schedules from database
	schedules, err := s.repos.Scout.GetActiveSchedules(s.ctx)
	if err != nil {
		return fmt.Errorf("failed to fetch active schedules: %w", err)
	}

	// Clear existing schedules
	s.schedules = make(map[uuid.UUID]*scheduledTask)

	// Parse and store schedules
	for _, schedule := range schedules {
		cronSpec, err := s.cronParser.Parse(schedule.CronExpression)
		if err != nil {
			s.logger.Warn("Failed to parse cron expression, skipping schedule",
				zap.String("schedule_id", schedule.ID.String()),
				zap.String("schedule_name", schedule.Name),
				zap.String("cron_expression", schedule.CronExpression),
				zap.Error(err),
			)
			continue
		}

		// Calculate next run time
		now := time.Now()
		nextRun := cronSpec.Next(now)

		// Update next_run_at in database if it's different
		if schedule.NextRunAt == nil || !schedule.NextRunAt.Equal(nextRun) {
			if err := s.repos.Scout.UpdateScheduleNextRun(s.ctx, schedule.ID, nextRun); err != nil {
				s.logger.Warn("Failed to update next run time",
					zap.String("schedule_id", schedule.ID.String()),
					zap.Error(err),
				)
			}
			schedule.NextRunAt = &nextRun
		}

		s.schedules[schedule.ID] = &scheduledTask{
			Schedule: schedule,
			NextRun:  nextRun,
			CronSpec: cronSpec,
		}

		s.logger.Debug("Loaded schedule",
			zap.String("schedule_id", schedule.ID.String()),
			zap.String("schedule_name", schedule.Name),
			zap.String("cron_expression", schedule.CronExpression),
			zap.Time("next_run", nextRun),
		)
	}

	s.logger.Info("Scout schedules reloaded",
		zap.Int("active_schedules", len(s.schedules)),
	)

	return nil
}

// loadSchedules loads schedules from the database (internal).
func (s *ScoutScheduler) loadSchedules() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.logger.Debug("Loading Scout schedules from database")

	// Fetch enabled schedules
	schedules, err := s.repos.Scout.GetActiveSchedules(s.ctx)
	if err != nil {
		return fmt.Errorf("failed to fetch active schedules: %w", err)
	}

	// Parse cron expressions and calculate next run times
	for _, schedule := range schedules {
		cronSpec, err := s.cronParser.Parse(schedule.CronExpression)
		if err != nil {
			s.logger.Warn("Failed to parse cron expression, skipping schedule",
				zap.String("schedule_id", schedule.ID.String()),
				zap.String("schedule_name", schedule.Name),
				zap.String("cron_expression", schedule.CronExpression),
				zap.Error(err),
			)
			continue
		}

		// Calculate next run time
		now := time.Now()
		nextRun := cronSpec.Next(now)

		// Update next_run_at in database if it's different
		if schedule.NextRunAt == nil || !schedule.NextRunAt.Equal(nextRun) {
			if err := s.repos.Scout.UpdateScheduleNextRun(s.ctx, schedule.ID, nextRun); err != nil {
				s.logger.Warn("Failed to update next run time",
					zap.String("schedule_id", schedule.ID.String()),
					zap.Error(err),
				)
			}
			schedule.NextRunAt = &nextRun
		}

		// Store in map
		s.schedules[schedule.ID] = &scheduledTask{
			Schedule: schedule,
			NextRun:  nextRun,
			CronSpec: cronSpec,
		}

		s.logger.Debug("Loaded schedule",
			zap.String("schedule_id", schedule.ID.String()),
			zap.String("schedule_name", schedule.Name),
			zap.String("cron_expression", schedule.CronExpression),
			zap.Time("next_run", nextRun),
		)
	}

	s.logger.Info("Loaded Scout schedules",
		zap.Int("count", len(s.schedules)),
	)

	return nil
}

// schedulerLoop runs the scheduler loop.
func (s *ScoutScheduler) schedulerLoop() {
	defer s.wg.Done()

	for {
		select {
		case <-s.ctx.Done():
			return
		case <-s.ticker.C:
			s.checkSchedules()
		}
	}
}

// checkSchedules checks if any schedules are due and executes them.
func (s *ScoutScheduler) checkSchedules() {
	s.mu.RLock()
	now := time.Now()

	// Find due schedules
	var dueSchedules []*domain.ScoutSchedule
	for _, task := range s.schedules {
		if task.NextRun.Before(now) || task.NextRun.Equal(now) {
			dueSchedules = append(dueSchedules, task.Schedule)
		}
	}
	s.mu.RUnlock()

	// Execute due schedules
	for _, schedule := range dueSchedules {
		s.logger.Info("Executing scheduled Scout run",
			zap.String("schedule_id", schedule.ID.String()),
			zap.String("schedule_name", schedule.Name),
			zap.String("source", schedule.Source),
		)

		// Execute in goroutine to avoid blocking
		s.wg.Add(1)
		go func(sched *domain.ScoutSchedule) {
			defer s.wg.Done()
			s.executeSchedule(sched)
		}(schedule)
	}
}

// executeSchedule executes a scheduled Scout run.
func (s *ScoutScheduler) executeSchedule(schedule *domain.ScoutSchedule) {
	// Create new ScoutRun
	run := domain.NewScoutRun(
		domain.ScoutTriggerTypeScheduled,
		schedule.Name,
		schedule.Source,
		schedule.MaxStrategies,
	)

	// Save to database
	if err := s.repos.Scout.CreateRun(s.ctx, run); err != nil {
		s.logger.Error("Failed to create Scout run",
			zap.String("schedule_id", schedule.ID.String()),
			zap.String("schedule_name", schedule.Name),
			zap.Error(err),
		)
		return
	}

	// Update schedule last run
	if err := s.repos.Scout.UpdateScheduleLastRun(s.ctx, schedule.ID, run.ID); err != nil {
		s.logger.Warn("Failed to update schedule last run",
			zap.String("schedule_id", schedule.ID.String()),
			zap.Error(err),
		)
	}

	// Calculate next run time
	s.mu.Lock()
	task, exists := s.schedules[schedule.ID]
	if exists {
		nextRun := task.CronSpec.Next(time.Now())
		task.NextRun = nextRun

		// Update in database
		if err := s.repos.Scout.UpdateScheduleNextRun(s.ctx, schedule.ID, nextRun); err != nil {
			s.logger.Warn("Failed to update schedule next run",
				zap.String("schedule_id", schedule.ID.String()),
				zap.Error(err),
			)
		}

		s.logger.Debug("Updated next run time",
			zap.String("schedule_id", schedule.ID.String()),
			zap.Time("next_run", nextRun),
		)
	}
	s.mu.Unlock()

	// Publish scout.trigger event
	if s.eventPublisher != nil {
		event := events.NewScoutTriggerEvent(run)
		if err := s.eventPublisher.PublishScoutTrigger(event); err != nil {
			s.logger.Error("Failed to publish scout trigger event",
				zap.String("run_id", run.ID.String()),
				zap.Error(err),
			)
		}
	}

	s.logger.Info("Scout run triggered",
		zap.String("run_id", run.ID.String()),
		zap.String("schedule_id", schedule.ID.String()),
		zap.String("schedule_name", schedule.Name),
		zap.String("source", schedule.Source),
		zap.Int("max_strategies", schedule.MaxStrategies),
	)
}

// calculateNextRun calculates the next run time for a cron expression.
func (s *ScoutScheduler) calculateNextRun(cronExpr string) (time.Time, error) {
	cronSpec, err := s.cronParser.Parse(cronExpr)
	if err != nil {
		return time.Time{}, fmt.Errorf("failed to parse cron expression: %w", err)
	}

	return cronSpec.Next(time.Now()), nil
}
