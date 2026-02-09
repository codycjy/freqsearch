package docker

import (
	"context"
	"fmt"
	"strings"
	"sync/atomic"
	"time"

	"go.uber.org/zap"
)

// hybridManager routes backtest execution between local Docker and Azure ACI.
//
// Design:
//   - Local Docker is preferred for up to N concurrent jobs (configurable slots)
//   - Overflow and failures automatically route to Azure ACI
//   - Container IDs are prefixed with "local:" or "aci:" for routing
//   - activeLocal counter tracks current local usage and is decremented when:
//     * WaitContainer completes (normal flow)
//     * RemoveContainer is called on a running container (cleanup flow)
//
// Thread-safety:
//   - Uses atomic.Int32 for activeLocal counter
//   - Safe for concurrent RunBacktest/WaitContainer calls
//
// hybridManager routes between local Docker and Azure ACI managers.
// It uses local Docker when slots are available and falls back to ACI
// when local is full or fails.
type hybridManager struct {
	local       Manager
	remote      Manager
	logger      *zap.Logger
	localSlots  int32
	activeLocal atomic.Int32
}

// NewHybridManager creates a manager that routes between local and remote backends.
// localSlots defines max concurrent local jobs before overflow to remote.
func NewHybridManager(local, remote Manager, localSlots int, logger *zap.Logger) Manager {
	logger.Info("Hybrid container manager initialized",
		zap.Int("local_slots", localSlots),
	)
	return &hybridManager{
		local:      local,
		remote:     remote,
		logger:     logger,
		localSlots: int32(localSlots),
	}
}

// RunBacktest starts a backtest container, preferring local Docker when slots are available.
func (m *hybridManager) RunBacktest(ctx context.Context, params *RunBacktestParams) (string, error) {
	// Try local first if slots available
	current := m.activeLocal.Load()
	if current < m.localSlots {
		// Optimistically increment
		m.activeLocal.Add(1)

		containerID, err := m.local.RunBacktest(ctx, params)
		if err != nil {
			// Failed, decrement and fall through to remote
			m.activeLocal.Add(-1)
			m.logger.Warn("Local backtest failed, falling back to remote",
				zap.String("job_id", params.JobID.String()),
				zap.Error(err),
			)
		} else {
			m.logger.Info("Started local backtest",
				zap.String("container_id", containerID),
				zap.String("job_id", params.JobID.String()),
				zap.Int32("active_local", m.activeLocal.Load()),
			)
			return "local:" + containerID, nil
		}
	}

	// Local is full or failed, use remote
	m.logger.Info("Using remote backend for backtest",
		zap.String("job_id", params.JobID.String()),
		zap.Int32("active_local", m.activeLocal.Load()),
		zap.Int32("local_slots", m.localSlots),
	)

	containerID, err := m.remote.RunBacktest(ctx, params)
	if err != nil {
		return "", fmt.Errorf("remote backtest failed: %w", err)
	}

	m.logger.Info("Started remote backtest",
		zap.String("container_id", containerID),
		zap.String("job_id", params.JobID.String()),
	)

	return "aci:" + containerID, nil
}

// ValidateStrategy validates strategy code using local Docker.
// Validation is fast and doesn't warrant using ACI.
func (m *hybridManager) ValidateStrategy(ctx context.Context, params *ValidateStrategyParams) (*ValidationResult, error) {
	result, err := m.local.ValidateStrategy(ctx, params)
	if err != nil {
		// If local validation fails, return a safe pass-through result
		// rather than failing completely
		m.logger.Warn("Local validation failed, returning pass-through result",
			zap.String("strategy", params.StrategyName),
			zap.Error(err),
		)
		return &ValidationResult{
			Valid:    true, // Optimistic pass-through
			Warnings: []string{"Local validation unavailable: " + err.Error()},
		}, nil
	}
	return result, nil
}

// WaitContainer waits for a container to finish and returns logs.
// Decrements activeLocal counter for local containers.
func (m *hybridManager) WaitContainer(ctx context.Context, containerID string) (int64, string, error) {
	backend, realID := parseContainerID(containerID)

	var mgr Manager
	if backend == "local" {
		mgr = m.local
		defer func() {
			// Decrement active local count when container finishes
			newCount := m.activeLocal.Add(-1)
			m.logger.Debug("Decremented active local count",
				zap.String("container_id", realID),
				zap.Int32("active_local", newCount),
			)
		}()
	} else {
		mgr = m.remote
	}

	exitCode, logs, err := mgr.WaitContainer(ctx, realID)
	if err != nil {
		return exitCode, logs, fmt.Errorf("%s backend wait failed: %w", backend, err)
	}

	m.logger.Info("Container finished",
		zap.String("backend", backend),
		zap.String("container_id", realID),
		zap.Int64("exit_code", exitCode),
	)

	return exitCode, logs, nil
}

// StopContainer stops a running container.
func (m *hybridManager) StopContainer(ctx context.Context, containerID string) error {
	backend, realID := parseContainerID(containerID)

	var mgr Manager
	if backend == "local" {
		mgr = m.local
	} else {
		mgr = m.remote
	}

	if err := mgr.StopContainer(ctx, realID); err != nil {
		return fmt.Errorf("%s backend stop failed: %w", backend, err)
	}

	m.logger.Info("Stopped container",
		zap.String("backend", backend),
		zap.String("container_id", realID),
	)

	return nil
}

// RemoveContainer removes a container.
// Decrements activeLocal counter for local containers if not already decremented.
func (m *hybridManager) RemoveContainer(ctx context.Context, containerID string) error {
	backend, realID := parseContainerID(containerID)

	var mgr Manager
	decrementLocal := false
	if backend == "local" {
		mgr = m.local
		// Check if container is still running - if so, we need to decrement
		// (WaitContainer may not have been called)
		running, err := mgr.IsContainerRunning(ctx, realID)
		if err == nil && running {
			decrementLocal = true
		}
	} else {
		mgr = m.remote
	}

	if err := mgr.RemoveContainer(ctx, realID); err != nil {
		return fmt.Errorf("%s backend remove failed: %w", backend, err)
	}

	if decrementLocal {
		newCount := m.activeLocal.Add(-1)
		m.logger.Debug("Decremented active local count on remove",
			zap.String("container_id", realID),
			zap.Int32("active_local", newCount),
		)
	}

	m.logger.Debug("Removed container",
		zap.String("backend", backend),
		zap.String("container_id", realID),
	)

	return nil
}

// GetContainerLogs retrieves logs from a container.
func (m *hybridManager) GetContainerLogs(ctx context.Context, containerID string) (string, error) {
	backend, realID := parseContainerID(containerID)

	var mgr Manager
	if backend == "local" {
		mgr = m.local
	} else {
		mgr = m.remote
	}

	logs, err := mgr.GetContainerLogs(ctx, realID)
	if err != nil {
		return "", fmt.Errorf("%s backend get logs failed: %w", backend, err)
	}

	return logs, nil
}

// CleanupStaleContainers removes stale containers from both backends.
func (m *hybridManager) CleanupStaleContainers(ctx context.Context, maxAge time.Duration) (int, error) {
	localCleaned := 0
	remoteCleaned := 0

	// Clean local
	if count, err := m.local.CleanupStaleContainers(ctx, maxAge); err != nil {
		m.logger.Warn("Failed to cleanup local containers",
			zap.Error(err),
		)
	} else {
		localCleaned = count
	}

	// Clean remote
	if count, err := m.remote.CleanupStaleContainers(ctx, maxAge); err != nil {
		m.logger.Warn("Failed to cleanup remote containers",
			zap.Error(err),
		)
	} else {
		remoteCleaned = count
	}

	total := localCleaned + remoteCleaned
	m.logger.Info("Cleaned up stale containers",
		zap.Int("local", localCleaned),
		zap.Int("remote", remoteCleaned),
		zap.Int("total", total),
	)

	return total, nil
}

// IsContainerRunning checks if a container is still running.
func (m *hybridManager) IsContainerRunning(ctx context.Context, containerID string) (bool, error) {
	backend, realID := parseContainerID(containerID)

	var mgr Manager
	if backend == "local" {
		mgr = m.local
	} else {
		mgr = m.remote
	}

	running, err := mgr.IsContainerRunning(ctx, realID)
	if err != nil {
		return false, fmt.Errorf("%s backend is running check failed: %w", backend, err)
	}

	return running, nil
}

// parseContainerID extracts the backend type and real container ID from a prefixed ID.
// Returns ("local", realID) for "local:" prefix, ("aci", realID) for "aci:" prefix.
// Legacy IDs without prefix default to "local".
func parseContainerID(id string) (backend string, realID string) {
	if strings.HasPrefix(id, "local:") {
		return "local", strings.TrimPrefix(id, "local:")
	}
	if strings.HasPrefix(id, "aci:") {
		return "aci", strings.TrimPrefix(id, "aci:")
	}
	// Legacy: no prefix means local
	return "local", id
}

// Ensure interface compliance at compile time.
var _ Manager = (*hybridManager)(nil)
