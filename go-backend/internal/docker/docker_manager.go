package docker

import (
	"archive/tar"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/stdcopy"
	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/config"
)

const (
	// Validator image name
	validatorImage = "freqsearch/strategy-validator:latest"
)

// toAbsolutePath converts a relative path to absolute path.
// If the path is already absolute, it returns as-is.
func toAbsolutePath(path string) string {
	if filepath.IsAbs(path) {
		return path
	}
	// Get current working directory
	cwd, err := os.Getwd()
	if err != nil {
		return path // fallback to original
	}
	return filepath.Join(cwd, path)
}

const (
	// Label keys for container management
	labelJobID   = "freqsearch.job_id"
	labelManaged = "freqsearch.managed"

	// Default resource limits
	defaultCPUQuota  = 200000 // 2 CPUs (100000 per CPU)
	defaultMemoryMB  = 2048   // 2 GB
)

// dockerManager implements Manager using the Docker SDK.
type dockerManager struct {
	client         *client.Client
	config         *config.DockerConfig
	configBuilder  *ConfigBuilder
	injector       *StrategyInjector
	logger         *zap.Logger
}

// NewDockerManager creates a new Docker manager.
func NewDockerManager(cfg *config.DockerConfig, logger *zap.Logger) (Manager, error) {
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, fmt.Errorf("failed to create Docker client: %w", err)
	}

	// Verify connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err = cli.Ping(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to Docker daemon: %w", err)
	}

	logger.Info("Docker client connected",
		zap.String("image", cfg.Image),
	)

	return &dockerManager{
		client:        cli,
		config:        cfg,
		configBuilder: NewConfigBuilder(cfg.BaseConfigPath, logger),
		injector:      NewStrategyInjector(logger),
		logger:        logger,
	}, nil
}

// RunBacktest starts a Freqtrade backtest container.
func (m *dockerManager) RunBacktest(ctx context.Context, params *RunBacktestParams) (string, error) {
	// 1. Prepare strategy file
	strategyResult, err := m.injector.InjectStrategy(params.StrategyCode, params.StrategyName)
	if err != nil {
		return "", fmt.Errorf("failed to inject strategy: %w", err)
	}
	// Note: Cleanup is called by the scheduler after container completion

	// 2. Build runtime config
	configResult, err := m.configBuilder.BuildRuntimeConfig(params.Config)
	if err != nil {
		strategyResult.Cleanup()
		return "", fmt.Errorf("failed to build config: %w", err)
	}
	// Note: Cleanup is called by the scheduler after container completion

	// 3. Build timerange
	timerange := params.Config.Timerange()

	// 4. Transform pairs for futures trading mode and build pairs string
	// Futures pairs need format: "BTC/USDT:USDT" instead of "BTC/USDT"
	pairs := params.Config.Pairs
	if params.Config.GetTradingMode() == "futures" {
		pairs = transformPairsForFutures(pairs, "USDT")
	}

	// 5. Get pairs from config file if not specified in params
	// This allows us to use the base_config.json's pair_whitelist
	if len(pairs) == 0 {
		pairs = configResult.Pairs
	}
	pairsArg := strings.Join(pairs, " ")

	// 6. Determine timeframe - use config file's timeframe if not specified
	// Default to "5m" if no timeframe is specified anywhere
	timeframe := params.Config.Timeframe
	if timeframe == "" {
		timeframe = configResult.Timeframe
	}
	if timeframe == "" {
		timeframe = "5m" // Default timeframe
	}

	// 7. Create container with download + backtest command
	// First download data, then run backtest
	downloadCmd := fmt.Sprintf(
		"freqtrade download-data --config /freqtrade/config.json --pairs %s --timeframes %s --timerange %s --trading-mode futures || true",
		pairsArg,
		timeframe,
		timerange,
	)
	backtestCmd := fmt.Sprintf(
		"freqtrade backtesting --strategy %s --config /freqtrade/config.json --timerange %s --export none",
		params.StrategyName,
		timerange,
	)

	containerConfig := &container.Config{
		Image:      m.config.Image,
		Entrypoint: []string{"/bin/sh", "-c"},
		Cmd:        []string{downloadCmd + " && " + backtestCmd},
		Labels: map[string]string{
			labelJobID:   params.JobID.String(),
			labelManaged: "true",
		},
		Env: []string{
			"FREQTRADE_STRATEGY=" + params.StrategyName,
		},
	}

	// 6. Configure host settings (convert relative paths to absolute)
	dataMount := toAbsolutePath(m.config.DataMount)
	hostConfig := &container.HostConfig{
		Binds: []string{
			dataMount + ":/freqtrade/user_data/data:rw", // rw needed for leverage_tiers cache and download
			strategyResult.StrategyPath + ":/freqtrade/user_data/strategies/" + params.StrategyName + ".py:rw",
			configResult.ConfigPath + ":/freqtrade/config.json:ro",
		},
		Resources: container.Resources{
			CPUQuota: defaultCPUQuota,
			Memory:   int64(defaultMemoryMB) * 1024 * 1024,
		},
		NetworkMode: container.NetworkMode(m.config.Network),
		AutoRemove:  false, // We handle removal manually
	}

	// 6. Ensure image exists
	if err := m.ensureImage(ctx); err != nil {
		strategyResult.Cleanup()
		configResult.Cleanup()
		return "", fmt.Errorf("failed to ensure image: %w", err)
	}

	// 7. Create and start container
	resp, err := m.client.ContainerCreate(ctx, containerConfig, hostConfig, nil, nil, "")
	if err != nil {
		strategyResult.Cleanup()
		configResult.Cleanup()
		return "", fmt.Errorf("failed to create container: %w", err)
	}

	containerID := resp.ID

	if err := m.client.ContainerStart(ctx, containerID, container.StartOptions{}); err != nil {
		// Cleanup container
		m.client.ContainerRemove(ctx, containerID, container.RemoveOptions{Force: true})
		strategyResult.Cleanup()
		configResult.Cleanup()
		return "", fmt.Errorf("failed to start container: %w", err)
	}

	m.logger.Info("Started backtest container",
		zap.String("container_id", containerID[:12]),
		zap.String("job_id", params.JobID.String()),
		zap.String("strategy", params.StrategyName),
		zap.String("timerange", timerange),
	)

	// Store cleanup functions for later (will be called by scheduler)
	// Note: In production, these should be stored and called appropriately

	return containerID, nil
}

// ValidateStrategy validates a strategy using the validator container.
// This is much faster than running a full backtest as it only checks:
// - Python syntax
// - Import availability
// - IStrategy class presence
// - Required methods
func (m *dockerManager) ValidateStrategy(ctx context.Context, params *ValidateStrategyParams) (*ValidationResult, error) {
	// 1. Prepare strategy file
	strategyResult, err := m.injector.InjectStrategy(params.StrategyCode, params.StrategyName)
	if err != nil {
		return nil, fmt.Errorf("failed to inject strategy: %w", err)
	}
	defer strategyResult.Cleanup()

	// 2. Ensure validator image exists
	if err := m.ensureValidatorImage(ctx); err != nil {
		return nil, fmt.Errorf("failed to ensure validator image: %w", err)
	}

	// 3. Create container config
	containerConfig := &container.Config{
		Image: validatorImage,
		Cmd:   []string{"/strategy.py"},
		Labels: map[string]string{
			labelManaged: "true",
		},
	}

	hostConfig := &container.HostConfig{
		Binds: []string{
			strategyResult.StrategyPath + ":/strategy.py:ro",
		},
		Resources: container.Resources{
			CPUQuota: 100000, // 1 CPU
			Memory:   512 * 1024 * 1024, // 512 MB
		},
		NetworkMode: container.NetworkMode(m.config.Network),
		AutoRemove:  true,
	}

	// 4. Create and start container
	resp, err := m.client.ContainerCreate(ctx, containerConfig, hostConfig, nil, nil, "")
	if err != nil {
		return nil, fmt.Errorf("failed to create validator container: %w", err)
	}

	containerID := resp.ID

	if err := m.client.ContainerStart(ctx, containerID, container.StartOptions{}); err != nil {
		m.client.ContainerRemove(ctx, containerID, container.RemoveOptions{Force: true})
		return nil, fmt.Errorf("failed to start validator container: %w", err)
	}

	// 5. Wait for completion (with timeout)
	waitCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	statusCh, errCh := m.client.ContainerWait(waitCtx, containerID, container.WaitConditionNotRunning)

	var logs string
	select {
	case err := <-errCh:
		if err != nil {
			return nil, fmt.Errorf("error waiting for validator: %w", err)
		}
	case <-statusCh:
		logs, _ = m.GetContainerLogs(ctx, containerID)
	case <-waitCtx.Done():
		m.client.ContainerKill(ctx, containerID, "SIGKILL")
		return nil, fmt.Errorf("validation timeout")
	}

	// 6. Parse JSON result from logs
	var result ValidationResult
	if err := json.Unmarshal([]byte(strings.TrimSpace(logs)), &result); err != nil {
		// Fallback: treat logs as error message
		return &ValidationResult{
			Valid:  false,
			Errors: []string{"Validation failed: " + logs},
		}, nil
	}

	m.logger.Info("Strategy validation completed",
		zap.String("strategy", params.StrategyName),
		zap.Bool("valid", result.Valid),
		zap.Strings("errors", result.Errors),
	)

	return &result, nil
}

// ensureValidatorImage ensures the validator image is available locally.
// If not found, it will build the image automatically.
func (m *dockerManager) ensureValidatorImage(ctx context.Context) error {
	// Check if image exists
	_, _, err := m.client.ImageInspectWithRaw(ctx, validatorImage)
	if err == nil {
		return nil // Image exists
	}

	if !client.IsErrNotFound(err) {
		return fmt.Errorf("failed to check validator image: %w", err)
	}

	// Image not found - build it
	m.logger.Info("Validator image not found, building...", zap.String("image", validatorImage))

	return m.buildValidatorImage(ctx)
}

// buildValidatorImage builds the validator image from Dockerfile.
func (m *dockerManager) buildValidatorImage(ctx context.Context) error {
	// Get the docker directory path (relative to working directory)
	dockerfilePath := "docker/freqtrade"

	// Check if Dockerfile exists
	dockerfileFullPath := filepath.Join(dockerfilePath, "Dockerfile")
	if _, err := os.Stat(dockerfileFullPath); os.IsNotExist(err) {
		return fmt.Errorf("Dockerfile not found at %s. Please ensure docker/freqtrade/Dockerfile exists", dockerfileFullPath)
	}

	// Create tar archive of the build context
	buildCtx, err := createBuildContext(dockerfilePath)
	if err != nil {
		return fmt.Errorf("failed to create build context: %w", err)
	}
	defer buildCtx.Close()

	// Build the image
	buildOptions := types.ImageBuildOptions{
		Tags:       []string{validatorImage},
		Dockerfile: "Dockerfile",
		Remove:     true,
	}

	resp, err := m.client.ImageBuild(ctx, buildCtx, buildOptions)
	if err != nil {
		return fmt.Errorf("failed to build validator image: %w", err)
	}
	defer resp.Body.Close()

	// Wait for build to complete and check for errors
	var lastLine string
	decoder := json.NewDecoder(resp.Body)
	for {
		var msg struct {
			Stream string `json:"stream"`
			Error  string `json:"error"`
		}
		if err := decoder.Decode(&msg); err != nil {
			if err == io.EOF {
				break
			}
			return fmt.Errorf("failed to read build output: %w", err)
		}
		if msg.Error != "" {
			return fmt.Errorf("build error: %s", msg.Error)
		}
		if msg.Stream != "" {
			lastLine = msg.Stream
		}
	}

	m.logger.Info("Validator image built successfully",
		zap.String("image", validatorImage),
		zap.String("last_output", strings.TrimSpace(lastLine)),
	)

	return nil
}

// createBuildContext creates a tar archive of the build directory.
func createBuildContext(dir string) (io.ReadCloser, error) {
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)

	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		// Get relative path
		relPath, err := filepath.Rel(dir, path)
		if err != nil {
			return err
		}

		// Skip the root directory itself
		if relPath == "." {
			return nil
		}

		// Create tar header
		header, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}
		header.Name = relPath

		if err := tw.WriteHeader(header); err != nil {
			return err
		}

		// Write file content if it's a regular file
		if !info.IsDir() {
			file, err := os.Open(path)
			if err != nil {
				return err
			}
			defer file.Close()

			if _, err := io.Copy(tw, file); err != nil {
				return err
			}
		}

		return nil
	})

	if err != nil {
		return nil, err
	}

	if err := tw.Close(); err != nil {
		return nil, err
	}

	return io.NopCloser(&buf), nil
}

// WaitContainer waits for a container to finish and returns logs.
func (m *dockerManager) WaitContainer(ctx context.Context, containerID string) (int64, string, error) {
	// Wait for container to exit
	statusCh, errCh := m.client.ContainerWait(ctx, containerID, container.WaitConditionNotRunning)

	select {
	case err := <-errCh:
		if err != nil {
			return -1, "", fmt.Errorf("error waiting for container: %w", err)
		}
	case status := <-statusCh:
		// Get logs
		logs, err := m.GetContainerLogs(ctx, containerID)
		if err != nil {
			m.logger.Warn("Failed to get container logs",
				zap.String("container_id", containerID[:12]),
				zap.Error(err),
			)
		}

		m.logger.Info("Container finished",
			zap.String("container_id", containerID[:12]),
			zap.Int64("exit_code", status.StatusCode),
		)

		return status.StatusCode, logs, nil
	case <-ctx.Done():
		return -1, "", ctx.Err()
	}

	return -1, "", fmt.Errorf("unexpected state")
}

// StopContainer stops a running container.
func (m *dockerManager) StopContainer(ctx context.Context, containerID string) error {
	timeout := 10 // seconds
	stopOptions := container.StopOptions{
		Timeout: &timeout,
	}

	if err := m.client.ContainerStop(ctx, containerID, stopOptions); err != nil {
		return fmt.Errorf("failed to stop container: %w", err)
	}

	m.logger.Info("Stopped container",
		zap.String("container_id", containerID[:12]),
	)

	return nil
}

// RemoveContainer removes a container.
func (m *dockerManager) RemoveContainer(ctx context.Context, containerID string) error {
	removeOptions := container.RemoveOptions{
		Force:         true,
		RemoveVolumes: true,
	}

	if err := m.client.ContainerRemove(ctx, containerID, removeOptions); err != nil {
		return fmt.Errorf("failed to remove container: %w", err)
	}

	m.logger.Debug("Removed container",
		zap.String("container_id", containerID[:12]),
	)

	return nil
}

// GetContainerLogs retrieves logs from a container.
func (m *dockerManager) GetContainerLogs(ctx context.Context, containerID string) (string, error) {
	options := container.LogsOptions{
		ShowStdout: true,
		ShowStderr: true,
		Timestamps: false,
		Follow:     false,
	}

	reader, err := m.client.ContainerLogs(ctx, containerID, options)
	if err != nil {
		return "", fmt.Errorf("failed to get container logs: %w", err)
	}
	defer reader.Close()

	// Docker multiplexes stdout/stderr, need to demux
	var stdout, stderr bytes.Buffer
	_, err = stdcopy.StdCopy(&stdout, &stderr, reader)
	if err != nil {
		// Try reading directly if demux fails (for TTY containers)
		reader, _ = m.client.ContainerLogs(ctx, containerID, options)
		data, _ := io.ReadAll(reader)
		return string(data), nil
	}

	// Combine stdout and stderr
	var combined strings.Builder
	combined.WriteString(stdout.String())
	if stderr.Len() > 0 {
		combined.WriteString("\n=== STDERR ===\n")
		combined.WriteString(stderr.String())
	}

	return combined.String(), nil
}

// CleanupStaleContainers removes containers that exceed the maximum age.
func (m *dockerManager) CleanupStaleContainers(ctx context.Context, maxAge time.Duration) (int, error) {
	// List containers with our label
	filterArgs := filters.NewArgs()
	filterArgs.Add("label", labelManaged+"=true")

	containers, err := m.client.ContainerList(ctx, container.ListOptions{
		All:     true,
		Filters: filterArgs,
	})
	if err != nil {
		return 0, fmt.Errorf("failed to list containers: %w", err)
	}

	cutoff := time.Now().Add(-maxAge)
	cleaned := 0

	for _, c := range containers {
		created := time.Unix(c.Created, 0)
		if created.Before(cutoff) {
			// Stop if running
			if c.State == "running" {
				m.StopContainer(ctx, c.ID)
			}

			// Remove container
			if err := m.RemoveContainer(ctx, c.ID); err != nil {
				m.logger.Warn("Failed to remove stale container",
					zap.String("container_id", c.ID[:12]),
					zap.Error(err),
				)
				continue
			}

			cleaned++
			m.logger.Info("Cleaned up stale container",
				zap.String("container_id", c.ID[:12]),
				zap.Time("created", created),
			)
		}
	}

	return cleaned, nil
}

// IsContainerRunning checks if a container is still running.
func (m *dockerManager) IsContainerRunning(ctx context.Context, containerID string) (bool, error) {
	inspect, err := m.client.ContainerInspect(ctx, containerID)
	if err != nil {
		if client.IsErrNotFound(err) {
			return false, nil
		}
		return false, fmt.Errorf("failed to inspect container: %w", err)
	}

	return inspect.State.Running, nil
}

// ensureImage ensures the Freqtrade image is available locally.
func (m *dockerManager) ensureImage(ctx context.Context) error {
	// Check if image exists
	_, _, err := m.client.ImageInspectWithRaw(ctx, m.config.Image)
	if err == nil {
		return nil // Image exists
	}

	if !client.IsErrNotFound(err) {
		return fmt.Errorf("failed to check image: %w", err)
	}

	// Pull the image
	m.logger.Info("Pulling Freqtrade image",
		zap.String("image", m.config.Image),
	)

	reader, err := m.client.ImagePull(ctx, m.config.Image, image.PullOptions{})
	if err != nil {
		return fmt.Errorf("failed to pull image: %w", err)
	}
	defer reader.Close()

	// Wait for pull to complete
	_, err = io.Copy(io.Discard, reader)
	if err != nil {
		return fmt.Errorf("failed to complete image pull: %w", err)
	}

	m.logger.Info("Successfully pulled image",
		zap.String("image", m.config.Image),
	)

	return nil
}

// Ensure interface compliance at compile time.
var _ Manager = (*dockerManager)(nil)
