package scheduler

import (
	"context"
	"errors"
	"sync"
	"time"

	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/docker"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// Worker processes backtest jobs.
type Worker struct {
	id        int
	scheduler *Scheduler
	logger    *zap.Logger
}

// NewWorker creates a new Worker.
func NewWorker(id int, scheduler *Scheduler, logger *zap.Logger) *Worker {
	return &Worker{
		id:        id,
		scheduler: scheduler,
		logger:    logger.With(zap.Int("worker_id", id)),
	}
}

// Run starts the worker loop.
func (w *Worker) Run(ctx context.Context, wg *sync.WaitGroup) {
	defer wg.Done()

	w.logger.Info("Worker started")

	for {
		select {
		case <-ctx.Done():
			w.logger.Info("Worker stopped")
			return
		case job := <-w.scheduler.jobChan:
			result := w.processJobWithRetry(ctx, job)
			select {
			case w.scheduler.resultChan <- result:
			case <-ctx.Done():
				return
			}
		}
	}
}

// processJobWithRetry processes a job with retry logic.
func (w *Worker) processJobWithRetry(ctx context.Context, job *domain.BacktestJob) *JobResult {
	result := w.processJob(ctx, job)

	if !result.Success && w.shouldRetry(job, result.Error) {
		w.logger.Info("Retrying job",
			zap.String("job_id", job.ID.String()),
			zap.Int("retry_count", job.RetryCount),
		)

		// Increment retry count in database
		if err := w.scheduler.repos.BacktestJob.IncrementRetryCount(ctx, job.ID); err != nil {
			w.logger.Error("Failed to increment retry count",
				zap.String("job_id", job.ID.String()),
				zap.Error(err),
			)
		}
		job.RetryCount++

		// Wait before retry
		select {
		case <-ctx.Done():
			return result
		case <-time.After(5 * time.Second):
		}

		result = w.processJob(ctx, job)
	}

	return result
}

// processJob processes a single backtest job.
func (w *Worker) processJob(ctx context.Context, job *domain.BacktestJob) *JobResult {
	startTime := time.Now()

	// Create job-specific context with timeout
	timeout := time.Duration(w.scheduler.config.JobTimeoutMinutes) * time.Minute
	jobCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Track as active job
	running := &RunningJob{
		Job:       job,
		StartedAt: startTime,
		Cancel:    cancel,
	}
	w.scheduler.activeJobs.Store(job.ID, running)
	defer w.scheduler.activeJobs.Delete(job.ID)

	w.logger.Info("Processing job",
		zap.String("job_id", job.ID.String()),
		zap.String("strategy_id", job.StrategyID.String()),
	)

	// Get strategy code
	strategy, err := w.scheduler.repos.Strategy.GetByID(ctx, job.StrategyID)
	if err != nil {
		return &JobResult{
			Job:     job,
			Success: false,
			Error:   err,
		}
	}

	// Start Docker container
	params := &docker.RunBacktestParams{
		JobID:        job.ID,
		StrategyCode: strategy.Code,
		StrategyName: strategy.Name,
		Config:       job.Config,
	}

	containerID, err := w.scheduler.dockerManager.RunBacktest(jobCtx, params)
	if err != nil {
		w.logger.Error("Failed to start container",
			zap.String("job_id", job.ID.String()),
			zap.Error(err),
		)
		return &JobResult{
			Job:     job,
			Success: false,
			Error:   ErrContainerStartFailed,
		}
	}

	// Update running job with container ID
	running.ContainerID = containerID

	// Update database with container ID
	w.scheduler.repos.BacktestJob.UpdateStatus(ctx, job.ID, domain.JobStatusRunning, &containerID, nil)

	// Wait for container to complete
	exitCode, logs, err := w.scheduler.dockerManager.WaitContainer(jobCtx, containerID)
	if err != nil {
		if errors.Is(err, context.DeadlineExceeded) {
			w.logger.Warn("Job timed out",
				zap.String("job_id", job.ID.String()),
			)
			// Stop the container
			w.scheduler.dockerManager.StopContainer(context.Background(), containerID)
		}

		return &JobResult{
			Job:     job,
			Success: false,
			Error:   err,
		}
	}

	// Clean up container
	defer w.scheduler.dockerManager.RemoveContainer(context.Background(), containerID)

	// Check exit code
	if exitCode != 0 {
		w.logger.Warn("Container exited with non-zero code",
			zap.String("job_id", job.ID.String()),
			zap.Int64("exit_code", exitCode),
		)

		// Try to extract error from logs
		if len(logs) > 500 {
			logs = logs[len(logs)-500:]
		}
		return &JobResult{
			Job:     job,
			Success: false,
			Error:   ErrStrategyCodeError,
		}
	}

	// Parse results
	result, err := w.scheduler.parser.ParseResult(logs, job)
	if err != nil {
		w.logger.Error("Failed to parse backtest result",
			zap.String("job_id", job.ID.String()),
			zap.Error(err),
		)
		return &JobResult{
			Job:     job,
			Success: false,
			Error:   err,
		}
	}

	duration := time.Since(startTime)
	w.logger.Info("Job completed",
		zap.String("job_id", job.ID.String()),
		zap.Duration("duration", duration),
		zap.Int("total_trades", result.TotalTrades),
		zap.Float64("profit_pct", result.ProfitPct),
	)

	return &JobResult{
		Job:     job,
		Result:  result,
		Success: true,
	}
}

// shouldRetry determines if a job should be retried based on the error.
func (w *Worker) shouldRetry(job *domain.BacktestJob, err error) bool {
	// Check if already retried
	if job.RetryCount >= w.scheduler.config.MaxRetries {
		return false
	}

	// Only retry on container/infrastructure errors, not code errors
	switch {
	case errors.Is(err, ErrContainerStartFailed):
		return true
	case errors.Is(err, context.DeadlineExceeded):
		return true
	case errors.Is(err, ErrDockerDaemonError):
		return true
	default:
		// Strategy code errors should not be retried
		return false
	}
}
