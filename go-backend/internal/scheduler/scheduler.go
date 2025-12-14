// Package scheduler provides backtest job scheduling and worker pool management.
package scheduler

import (
	"context"
	"errors"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/config"
	"github.com/saltfish/freqsearch/go-backend/internal/db/repository"
	"github.com/saltfish/freqsearch/go-backend/internal/docker"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
	"github.com/saltfish/freqsearch/go-backend/internal/parser"
)

// EventPublisher defines the interface for publishing events.
type EventPublisher interface {
	PublishTaskRunning(job *domain.BacktestJob) error
	PublishTaskCompleted(job *domain.BacktestJob, result *domain.BacktestResult) error
	PublishTaskFailed(job *domain.BacktestJob, errMsg string) error
	PublishTaskCancelled(job *domain.BacktestJob) error
}

// Scheduler manages backtest job execution.
type Scheduler struct {
	config         *config.SchedulerConfig
	repos          *repository.Repositories
	dockerManager  docker.Manager
	eventPublisher EventPublisher
	parser         *parser.Parser
	logger         *zap.Logger

	workers    []*Worker
	jobChan    chan *domain.BacktestJob
	resultChan chan *JobResult

	activeJobs sync.Map // jobID -> *RunningJob
	wg         sync.WaitGroup
	ctx        context.Context
	cancel     context.CancelFunc
}

// RunningJob tracks a job that's currently being executed.
type RunningJob struct {
	Job         *domain.BacktestJob
	ContainerID string
	StartedAt   time.Time
	Cancel      context.CancelFunc
}

// JobResult represents the result of processing a job.
type JobResult struct {
	Job     *domain.BacktestJob
	Result  *domain.BacktestResult
	Success bool
	Error   error
}

// Config holds scheduler configuration.
type Config struct {
	MaxConcurrentBacktests int
	PollInterval           time.Duration
	JobTimeout             time.Duration
	MaxRetries             int
	ShutdownTimeout        time.Duration
}

// NewScheduler creates a new Scheduler.
func NewScheduler(
	cfg *config.SchedulerConfig,
	repos *repository.Repositories,
	dockerManager docker.Manager,
	eventPublisher EventPublisher,
	logger *zap.Logger,
) *Scheduler {
	ctx, cancel := context.WithCancel(context.Background())

	return &Scheduler{
		config:         cfg,
		repos:          repos,
		dockerManager:  dockerManager,
		eventPublisher: eventPublisher,
		parser:         parser.NewParser(logger),
		logger:         logger,
		jobChan:        make(chan *domain.BacktestJob, cfg.MaxConcurrentBacktests),
		resultChan:     make(chan *JobResult, cfg.MaxConcurrentBacktests),
		ctx:            ctx,
		cancel:         cancel,
	}
}

// Start starts the scheduler and workers.
func (s *Scheduler) Start() error {
	s.logger.Info("Starting scheduler",
		zap.Int("workers", s.config.MaxConcurrentBacktests),
		zap.Int("poll_interval_seconds", s.config.PollIntervalSeconds),
	)

	// Start workers
	for i := 0; i < s.config.MaxConcurrentBacktests; i++ {
		worker := NewWorker(i, s, s.logger)
		s.workers = append(s.workers, worker)
		s.wg.Add(1)
		go worker.Run(s.ctx, &s.wg)
	}

	// Start job fetcher
	s.wg.Add(1)
	go s.fetchJobs()

	// Start result handler
	s.wg.Add(1)
	go s.handleResults()

	// Start timeout watcher
	s.wg.Add(1)
	go s.watchTimeouts()

	s.logger.Info("Scheduler started")
	return nil
}

// Stop gracefully stops the scheduler.
func (s *Scheduler) Stop() error {
	s.logger.Info("Stopping scheduler")

	// Signal all goroutines to stop
	s.cancel()

	// Parse shutdown timeout
	timeout := 30 * time.Second
	if s.config.ShutdownTimeout != "" {
		if parsed, err := time.ParseDuration(s.config.ShutdownTimeout); err == nil {
			timeout = parsed
		}
	}

	// Wait for workers with timeout
	done := make(chan struct{})
	go func() {
		s.wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		s.logger.Info("Scheduler stopped gracefully")
	case <-time.After(timeout):
		s.logger.Warn("Scheduler shutdown timed out")
		// Force stop any running containers
		s.forceStopRunningJobs()
	}

	return nil
}

// fetchJobs periodically fetches pending jobs from the database.
func (s *Scheduler) fetchJobs() {
	defer s.wg.Done()

	ticker := time.NewTicker(time.Duration(s.config.PollIntervalSeconds) * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-s.ctx.Done():
			return
		case <-ticker.C:
			s.fetchAndDispatch()
		}
	}
}

// fetchAndDispatch fetches pending jobs and dispatches them to workers.
func (s *Scheduler) fetchAndDispatch() {
	// Calculate how many jobs we can take
	available := cap(s.jobChan) - len(s.jobChan)
	if available <= 0 {
		return
	}

	// Fetch pending jobs using FOR UPDATE SKIP LOCKED
	jobs, err := s.repos.BacktestJob.GetPendingJobs(s.ctx, available)
	if err != nil {
		s.logger.Error("Failed to fetch pending jobs", zap.Error(err))
		return
	}

	for _, job := range jobs {
		// Mark job as running
		if err := s.repos.BacktestJob.MarkRunning(s.ctx, job.ID, "pending"); err != nil {
			s.logger.Error("Failed to mark job as running",
				zap.String("job_id", job.ID.String()),
				zap.Error(err),
			)
			continue
		}

		// Update job status
		job.Status = domain.JobStatusRunning
		now := time.Now()
		job.StartedAt = &now

		// Publish event
		if s.eventPublisher != nil {
			s.eventPublisher.PublishTaskRunning(job)
		}

		// Dispatch to worker
		select {
		case s.jobChan <- job:
			s.logger.Debug("Dispatched job",
				zap.String("job_id", job.ID.String()),
				zap.Int("priority", job.Priority),
			)
		case <-s.ctx.Done():
			return
		}
	}
}

// handleResults processes job results from workers.
func (s *Scheduler) handleResults() {
	defer s.wg.Done()

	for {
		select {
		case <-s.ctx.Done():
			return
		case result := <-s.resultChan:
			s.processResult(result)
		}
	}
}

// processResult handles a completed job result.
func (s *Scheduler) processResult(result *JobResult) {
	job := result.Job

	// Remove from active jobs
	s.activeJobs.Delete(job.ID)

	if result.Success && result.Result != nil {
		// Save result to database
		if err := s.repos.Result.Create(s.ctx, result.Result); err != nil {
			s.logger.Error("Failed to save backtest result",
				zap.String("job_id", job.ID.String()),
				zap.Error(err),
			)
		}

		// Mark job as completed
		if err := s.repos.BacktestJob.MarkCompleted(s.ctx, job.ID); err != nil {
			s.logger.Error("Failed to mark job completed",
				zap.String("job_id", job.ID.String()),
				zap.Error(err),
			)
		}

		// Publish event
		if s.eventPublisher != nil {
			s.eventPublisher.PublishTaskCompleted(job, result.Result)
		}

		s.logger.Info("Job completed successfully",
			zap.String("job_id", job.ID.String()),
			zap.Float64("profit_pct", result.Result.ProfitPct),
		)
	} else {
		// Mark job as failed
		errMsg := "unknown error"
		if result.Error != nil {
			errMsg = result.Error.Error()
		}

		if err := s.repos.BacktestJob.MarkFailed(s.ctx, job.ID, errMsg); err != nil {
			s.logger.Error("Failed to mark job failed",
				zap.String("job_id", job.ID.String()),
				zap.Error(err),
			)
		}

		// Publish event
		if s.eventPublisher != nil {
			s.eventPublisher.PublishTaskFailed(job, errMsg)
		}

		s.logger.Warn("Job failed",
			zap.String("job_id", job.ID.String()),
			zap.Error(result.Error),
		)
	}
}

// watchTimeouts monitors for jobs that have exceeded timeout.
func (s *Scheduler) watchTimeouts() {
	defer s.wg.Done()

	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	timeout := time.Duration(s.config.JobTimeoutMinutes) * time.Minute

	for {
		select {
		case <-s.ctx.Done():
			return
		case <-ticker.C:
			s.checkTimeouts(timeout)
		}
	}
}

// checkTimeouts checks for and handles timed out jobs.
func (s *Scheduler) checkTimeouts(timeout time.Duration) {
	timedOut, err := s.repos.BacktestJob.GetTimedOutJobs(s.ctx, timeout)
	if err != nil {
		s.logger.Error("Failed to check timed out jobs", zap.Error(err))
		return
	}

	for _, job := range timedOut {
		s.logger.Warn("Job timed out",
			zap.String("job_id", job.ID.String()),
			zap.Duration("timeout", timeout),
		)

		// Try to stop the container
		if job.ContainerID != nil && *job.ContainerID != "" {
			if err := s.dockerManager.StopContainer(s.ctx, *job.ContainerID); err != nil {
				s.logger.Error("Failed to stop timed out container",
					zap.String("job_id", job.ID.String()),
					zap.String("container_id", *job.ContainerID),
					zap.Error(err),
				)
			}
		}

		// Cancel if in active jobs
		if running, ok := s.activeJobs.Load(job.ID); ok {
			if rj, ok := running.(*RunningJob); ok && rj.Cancel != nil {
				rj.Cancel()
			}
		}

		// Mark as failed
		if err := s.repos.BacktestJob.MarkFailed(s.ctx, job.ID, "job timed out"); err != nil {
			s.logger.Error("Failed to mark timed out job as failed",
				zap.String("job_id", job.ID.String()),
				zap.Error(err),
			)
		}

		// Publish event
		if s.eventPublisher != nil {
			s.eventPublisher.PublishTaskFailed(job, "job timed out")
		}
	}
}

// forceStopRunningJobs stops all running containers during shutdown.
func (s *Scheduler) forceStopRunningJobs() {
	s.activeJobs.Range(func(key, value interface{}) bool {
		if rj, ok := value.(*RunningJob); ok {
			if rj.ContainerID != "" {
				s.logger.Warn("Force stopping container",
					zap.String("job_id", rj.Job.ID.String()),
					zap.String("container_id", rj.ContainerID),
				)
				s.dockerManager.StopContainer(context.Background(), rj.ContainerID)
			}
			if rj.Cancel != nil {
				rj.Cancel()
			}
		}
		return true
	})
}

// GetStats returns current scheduler statistics.
func (s *Scheduler) GetStats() map[string]interface{} {
	var activeCount int
	s.activeJobs.Range(func(key, value interface{}) bool {
		activeCount++
		return true
	})

	queueStats, _ := s.repos.BacktestJob.GetQueueStats(s.ctx)

	stats := map[string]interface{}{
		"active_jobs":  activeCount,
		"queue_length": len(s.jobChan),
		"worker_count": len(s.workers),
	}

	if queueStats != nil {
		stats["pending_jobs"] = queueStats.PendingJobs
		stats["running_jobs"] = queueStats.RunningJobs
		stats["completed_today"] = queueStats.CompletedToday
		stats["failed_today"] = queueStats.FailedToday
		stats["avg_wait_time_ms"] = queueStats.AvgWaitTimeMs
		stats["avg_run_time_ms"] = queueStats.AvgRunTimeMs
	}

	return stats
}

// Scheduler errors
var (
	ErrContainerStartFailed = errors.New("container failed to start")
	ErrDockerDaemonError    = errors.New("docker daemon error")
	ErrStrategyCodeError    = errors.New("strategy code error")
)
