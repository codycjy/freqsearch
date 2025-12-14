// Package docker provides Docker container management for running Freqtrade backtests.
package docker

import (
	"context"
	"time"

	"github.com/google/uuid"

	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// Manager defines the interface for Docker container operations.
type Manager interface {
	// RunBacktest starts a Freqtrade backtest container.
	RunBacktest(ctx context.Context, params *RunBacktestParams) (containerID string, err error)

	// WaitContainer waits for a container to finish and returns logs.
	WaitContainer(ctx context.Context, containerID string) (exitCode int64, logs string, err error)

	// StopContainer stops a running container.
	StopContainer(ctx context.Context, containerID string) error

	// RemoveContainer removes a container.
	RemoveContainer(ctx context.Context, containerID string) error

	// GetContainerLogs retrieves logs from a container.
	GetContainerLogs(ctx context.Context, containerID string) (string, error)

	// CleanupStaleContainers removes containers that exceed the maximum age.
	CleanupStaleContainers(ctx context.Context, maxAge time.Duration) (int, error)

	// IsContainerRunning checks if a container is still running.
	IsContainerRunning(ctx context.Context, containerID string) (bool, error)
}

// RunBacktestParams contains parameters for running a backtest.
type RunBacktestParams struct {
	// JobID is the unique identifier for this backtest job.
	JobID uuid.UUID

	// StrategyCode is the Python source code for the strategy.
	StrategyCode string

	// StrategyName is the class name of the strategy.
	StrategyName string

	// Config contains the backtest configuration.
	Config domain.BacktestConfig
}

// ContainerResult represents the result of a container execution.
type ContainerResult struct {
	// ExitCode is the exit code from the container.
	ExitCode int64

	// Logs contains the combined stdout/stderr from the container.
	Logs string

	// Duration is how long the container ran.
	Duration time.Duration
}
