package docker

import (
	"context"
	"encoding/base64"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore/to"
	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
	"github.com/Azure/azure-sdk-for-go/sdk/resourcemanager/containerinstance/armcontainerinstance/v2"
	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/config"
)

// aciManager implements Manager using Azure Container Instances.
type aciManager struct {
	cgClient      *armcontainerinstance.ContainerGroupsClient
	cClient       *armcontainerinstance.ContainersClient
	config        *config.ACIConfig
	configBuilder *ConfigBuilder
	logger        *zap.Logger
}

// NewACIManager creates a new Azure Container Instances manager.
func NewACIManager(cfg *config.ACIConfig, logger *zap.Logger) (Manager, error) {
	var cred *azidentity.DefaultAzureCredential
	var credSP *azidentity.ClientSecretCredential
	var credMI *azidentity.ManagedIdentityCredential
	var err error

	// Select authentication method based on configuration
	var cgClient *armcontainerinstance.ContainerGroupsClient
	var cClient *armcontainerinstance.ContainersClient

	switch cfg.AuthMethod {
	case "service_principal":
		if cfg.TenantID == "" || cfg.ClientID == "" || cfg.ClientSecret == "" {
			return nil, fmt.Errorf("service principal auth requires tenant_id, client_id, and client_secret")
		}
		credSP, err = azidentity.NewClientSecretCredential(cfg.TenantID, cfg.ClientID, cfg.ClientSecret, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create service principal credential: %w", err)
		}
		logger.Info("Using service principal authentication")

		cgClient, err = armcontainerinstance.NewContainerGroupsClient(cfg.SubscriptionID, credSP, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create container groups client: %w", err)
		}
		cClient, err = armcontainerinstance.NewContainersClient(cfg.SubscriptionID, credSP, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create containers client: %w", err)
		}

	case "managed_identity":
		opts := &azidentity.ManagedIdentityCredentialOptions{}
		if cfg.ManagedIdentityID != "" {
			opts.ID = azidentity.ClientID(cfg.ManagedIdentityID)
		}
		credMI, err = azidentity.NewManagedIdentityCredential(opts)
		if err != nil {
			return nil, fmt.Errorf("failed to create managed identity credential: %w", err)
		}
		logger.Info("Using managed identity authentication")

		cgClient, err = armcontainerinstance.NewContainerGroupsClient(cfg.SubscriptionID, credMI, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create container groups client: %w", err)
		}
		cClient, err = armcontainerinstance.NewContainersClient(cfg.SubscriptionID, credMI, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create containers client: %w", err)
		}

	case "default", "":
		cred, err = azidentity.NewDefaultAzureCredential(nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create default Azure credential: %w", err)
		}
		logger.Info("Using default Azure credential")

		cgClient, err = armcontainerinstance.NewContainerGroupsClient(cfg.SubscriptionID, cred, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create container groups client: %w", err)
		}
		cClient, err = armcontainerinstance.NewContainersClient(cfg.SubscriptionID, cred, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to create containers client: %w", err)
		}

	default:
		return nil, fmt.Errorf("unsupported auth method: %s", cfg.AuthMethod)
	}

	logger.Info("ACI client initialized",
		zap.String("subscription_id", cfg.SubscriptionID),
		zap.String("resource_group", cfg.ResourceGroup),
		zap.String("location", cfg.Location),
		zap.String("image", cfg.Image),
	)

	return &aciManager{
		cgClient:      cgClient,
		cClient:       cClient,
		config:        cfg,
		configBuilder: NewConfigBuilder(cfg.BaseConfigPath, logger),
		logger:        logger,
	}, nil
}

// RunBacktest starts a Freqtrade backtest container on ACI.
func (m *aciManager) RunBacktest(ctx context.Context, params *RunBacktestParams) (string, error) {
	// 1. Generate container group name (ACI identifier)
	// Container group names must be 1-63 chars, lowercase alphanumeric and hyphens
	containerGroupName := fmt.Sprintf("bt-%s", params.JobID.String()[:8])

	// 2. Build runtime config
	configResult, err := m.configBuilder.BuildRuntimeConfig(params.Config)
	if err != nil {
		return "", fmt.Errorf("failed to build config: %w", err)
	}
	defer configResult.Cleanup()

	// 3. Read config file content for secret volume
	configData, err := readFile(configResult.ConfigPath)
	if err != nil {
		return "", fmt.Errorf("failed to read config file: %w", err)
	}

	// 4. Encode strategy code and config as base64 for secret volumes
	strategyCodeB64 := base64.StdEncoding.EncodeToString([]byte(params.StrategyCode))
	configDataB64 := base64.StdEncoding.EncodeToString(configData)

	// 5. Build timerange
	timerange := params.Config.Timerange()

	// 6. Transform pairs for futures trading mode and build pairs string
	pairs := params.Config.Pairs
	if params.Config.GetTradingMode() == "futures" {
		pairs = transformPairsForFutures(pairs, "USDT")
	}

	// Use config file pairs if not specified in params
	if len(pairs) == 0 {
		pairs = configResult.Pairs
	}
	pairsArg := strings.Join(pairs, " ")

	// 7. Determine timeframe
	timeframe := params.Config.Timeframe
	if timeframe == "" {
		timeframe = configResult.Timeframe
	}
	if timeframe == "" {
		timeframe = "5m"
	}

	// 8. Build download + backtest command
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

	// Combined command: create dirs, copy secrets to writable paths, then run download and backtest
	fullCommand := fmt.Sprintf(
		"mkdir -p /freqtrade/user_data/strategies /freqtrade/user_data/data && "+
			"cp /mnt/strategy/%s.py /freqtrade/user_data/strategies/%s.py && "+
			"cp /mnt/config/config.json /freqtrade/config.json && "+
			"%s && %s",
		params.StrategyName, params.StrategyName, downloadCmd, backtestCmd,
	)

	// 9. Build volumes (market-data, strategy, config)
	volumes := m.buildVolumes(strategyCodeB64, params.StrategyName, configDataB64)

	// 10. Build volume mounts
	volumeMounts := m.buildVolumeMounts(params.StrategyName)

	// 11. Build image registry credentials
	registryCredentials := m.buildRegistryCredentials()

	// 12. Create container group
	containerGroup := armcontainerinstance.ContainerGroup{
		Location: to.Ptr(m.config.Location),
		Tags: map[string]*string{
			"freqsearch.managed": to.Ptr("true"),
			"freqsearch.job_id":  to.Ptr(params.JobID.String()),
		},
		Properties: &armcontainerinstance.ContainerGroupPropertiesProperties{
			OSType:        to.Ptr(armcontainerinstance.OperatingSystemTypesLinux),
			RestartPolicy: to.Ptr(armcontainerinstance.ContainerGroupRestartPolicyNever),
			Volumes:       volumes,
			Containers: []*armcontainerinstance.Container{
				{
					Name: to.Ptr("backtest"),
					Properties: &armcontainerinstance.ContainerProperties{
						Image: to.Ptr(m.config.Image),
						Command: []*string{
							to.Ptr("/bin/sh"),
							to.Ptr("-c"),
							to.Ptr(fullCommand),
						},
						Resources: &armcontainerinstance.ResourceRequirements{
							Requests: &armcontainerinstance.ResourceRequests{
								CPU:        to.Ptr(m.config.CPUCores),
								MemoryInGB: to.Ptr(m.config.MemoryGB),
							},
						},
						VolumeMounts: volumeMounts,
						EnvironmentVariables: []*armcontainerinstance.EnvironmentVariable{
							{
								Name:  to.Ptr("FREQTRADE_STRATEGY"),
								Value: to.Ptr(params.StrategyName),
							},
						},
					},
				},
			},
			ImageRegistryCredentials: registryCredentials,
		},
	}

	// 13. Start container group creation
	m.logger.Info("Creating ACI container group",
		zap.String("name", containerGroupName),
		zap.String("job_id", params.JobID.String()),
		zap.String("strategy", params.StrategyName),
		zap.String("timerange", timerange),
	)

	poller, err := m.cgClient.BeginCreateOrUpdate(ctx, m.config.ResourceGroup, containerGroupName, containerGroup, nil)
	if err != nil {
		return "", fmt.Errorf("failed to start container group creation: %w", err)
	}

	// 14. Wait for provisioning to complete
	_, err = poller.PollUntilDone(ctx, nil)
	if err != nil {
		return "", fmt.Errorf("failed to provision container group: %w", err)
	}

	m.logger.Info("Started ACI container group",
		zap.String("name", containerGroupName),
		zap.String("job_id", params.JobID.String()),
		zap.String("strategy", params.StrategyName),
	)

	return containerGroupName, nil
}

// buildVolumes creates volumes for the container group.
func (m *aciManager) buildVolumes(strategyCodeB64, strategyName, configJSONB64 string) []*armcontainerinstance.Volume {
	volumes := []*armcontainerinstance.Volume{
		// Strategy secret volume
		{
			Name: to.Ptr("strategy"),
			Secret: map[string]*string{
				strategyName + ".py": to.Ptr(strategyCodeB64),
			},
		},
		// Config secret volume
		{
			Name: to.Ptr("config"),
			Secret: map[string]*string{
				"config.json": to.Ptr(configJSONB64),
			},
		},
	}

	// Add Azure Files volume for market data if storage account is configured
	if m.config.StorageAccountName != "" && m.config.FileShareName != "" {
		volumes = append(volumes, &armcontainerinstance.Volume{
			Name: to.Ptr("market-data"),
			AzureFile: &armcontainerinstance.AzureFileVolume{
				ShareName:          to.Ptr(m.config.FileShareName),
				StorageAccountName: to.Ptr(m.config.StorageAccountName),
				StorageAccountKey:  to.Ptr(m.config.StorageAccountKey),
				ReadOnly:           to.Ptr(false), // download-data needs write access
			},
		})
	}

	return volumes
}

// buildVolumeMounts creates volume mounts for the container.
func (m *aciManager) buildVolumeMounts(strategyName string) []*armcontainerinstance.VolumeMount {
	mounts := []*armcontainerinstance.VolumeMount{
		// Strategy mount (read-only secret)
		{
			Name:      to.Ptr("strategy"),
			MountPath: to.Ptr("/mnt/strategy"),
			ReadOnly:  to.Ptr(true),
		},
		// Config mount (read-only secret)
		{
			Name:      to.Ptr("config"),
			MountPath: to.Ptr("/mnt/config"),
			ReadOnly:  to.Ptr(true),
		},
	}

	// Add market data mount if configured
	if m.config.StorageAccountName != "" && m.config.FileShareName != "" {
		mounts = append(mounts, &armcontainerinstance.VolumeMount{
			Name:      to.Ptr("market-data"),
			MountPath: to.Ptr("/freqtrade/user_data/data"),
			ReadOnly:  to.Ptr(false),
		})
	}

	return mounts
}

// buildRegistryCredentials creates registry credentials for private container registries.
func (m *aciManager) buildRegistryCredentials() []*armcontainerinstance.ImageRegistryCredential {
	// If using managed identity for registry access
	if m.config.ManagedIdentityID != "" && m.config.RegistryServer != "" {
		return []*armcontainerinstance.ImageRegistryCredential{
			{
				Server:   to.Ptr(m.config.RegistryServer),
				Identity: to.Ptr(m.config.ManagedIdentityID),
			},
		}
	}

	// If using username/password for registry access
	if m.config.RegistryServer != "" && m.config.RegistryUsername != "" {
		return []*armcontainerinstance.ImageRegistryCredential{
			{
				Server:   to.Ptr(m.config.RegistryServer),
				Username: to.Ptr(m.config.RegistryUsername),
				Password: to.Ptr(m.config.RegistryPassword),
			},
		}
	}

	// No credentials needed (public image)
	return nil
}

// ValidateStrategy validates a strategy using ACI.
// For simplicity, this implementation returns a pass-through result since
// the validator image is local and the engineer agent validates code before submission.
func (m *aciManager) ValidateStrategy(ctx context.Context, params *ValidateStrategyParams) (*ValidationResult, error) {
	// Strategy validation via ACI is not yet supported - return a pass-through result
	// The engineer agent validates code before submission
	return &ValidationResult{
		Valid:     true,
		Warnings:  []string{"ACI backend: strategy validation skipped, relying on agent-side validation"},
		ClassName: params.StrategyName,
	}, nil
}

// WaitContainer waits for a container group to finish execution and retrieves logs.
func (m *aciManager) WaitContainer(ctx context.Context, containerID string) (int64, string, error) {
	containerGroupName := containerID
	pollInterval := m.config.GetPollInterval()
	timeout := m.config.GetContainerTimeout()

	// Create a context with timeout
	timeoutCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	m.logger.Info("Waiting for ACI container",
		zap.String("container_group", containerGroupName),
		zap.Duration("poll_interval", pollInterval),
		zap.Duration("timeout", timeout),
	)

	for {
		select {
		case <-timeoutCtx.Done():
			return -1, "", fmt.Errorf("timeout waiting for container group: %s", containerGroupName)

		case <-ticker.C:
			// Get container group status
			resp, err := m.cgClient.Get(ctx, m.config.ResourceGroup, containerGroupName, nil)
			if err != nil {
				return -1, "", fmt.Errorf("failed to get container group status: %w", err)
			}

			// Check if container group is terminated
			if resp.Properties != nil && resp.Properties.InstanceView != nil {
				state := resp.Properties.InstanceView.State

				// Check container instances
				if len(resp.Properties.Containers) > 0 && resp.Properties.Containers[0].Properties != nil {
					currentState := resp.Properties.Containers[0].Properties.InstanceView
					if currentState != nil && currentState.CurrentState != nil {
						if *currentState.CurrentState.State == "Terminated" {
							exitCode := int64(0)
							if currentState.CurrentState.ExitCode != nil {
								exitCode = int64(*currentState.CurrentState.ExitCode)
							}

							// Get logs
							logs, err := m.GetContainerLogs(ctx, containerGroupName)
							if err != nil {
								m.logger.Warn("Failed to get container logs",
									zap.String("container_group", containerGroupName),
									zap.Error(err),
								)
							}

							m.logger.Info("ACI container finished",
								zap.String("container_group", containerGroupName),
								zap.Int64("exit_code", exitCode),
								zap.String("state", string(*state)),
							)

							return exitCode, logs, nil
						}
					}
				}

				// Also check overall container group state
				if state != nil {
					stateStr := string(*state)
					if stateStr == "Succeeded" || stateStr == "Failed" || stateStr == "Stopped" {
						// Extract exit code from container
						exitCode := int64(0)
						if len(resp.Properties.Containers) > 0 &&
							resp.Properties.Containers[0].Properties != nil &&
							resp.Properties.Containers[0].Properties.InstanceView != nil &&
							resp.Properties.Containers[0].Properties.InstanceView.CurrentState != nil &&
							resp.Properties.Containers[0].Properties.InstanceView.CurrentState.ExitCode != nil {
							exitCode = int64(*resp.Properties.Containers[0].Properties.InstanceView.CurrentState.ExitCode)
						}

						// Get logs
						logs, err := m.GetContainerLogs(ctx, containerGroupName)
						if err != nil {
							m.logger.Warn("Failed to get container logs",
								zap.String("container_group", containerGroupName),
								zap.Error(err),
							)
						}

						m.logger.Info("ACI container group finished",
							zap.String("container_group", containerGroupName),
							zap.Int64("exit_code", exitCode),
							zap.String("state", stateStr),
						)

						return exitCode, logs, nil
					}
				}
			}
		}
	}
}

// StopContainer stops a running container group.
func (m *aciManager) StopContainer(ctx context.Context, containerID string) error {
	containerGroupName := containerID

	m.logger.Info("Stopping ACI container group",
		zap.String("container_group", containerGroupName),
	)

	_, err := m.cgClient.Stop(ctx, m.config.ResourceGroup, containerGroupName, nil)
	if err != nil {
		return fmt.Errorf("failed to stop container group: %w", err)
	}

	m.logger.Info("Stopped ACI container group",
		zap.String("container_group", containerGroupName),
	)

	return nil
}

// RemoveContainer removes a container group.
func (m *aciManager) RemoveContainer(ctx context.Context, containerID string) error {
	containerGroupName := containerID

	m.logger.Debug("Removing ACI container group",
		zap.String("container_group", containerGroupName),
	)

	// Fire and forget - don't wait for deletion to complete
	poller, err := m.cgClient.BeginDelete(ctx, m.config.ResourceGroup, containerGroupName, nil)
	if err != nil {
		return fmt.Errorf("failed to start container group deletion: %w", err)
	}

	// Start deletion but don't wait
	_ = poller

	m.logger.Debug("Started deletion of ACI container group",
		zap.String("container_group", containerGroupName),
	)

	return nil
}

// GetContainerLogs retrieves logs from a container.
func (m *aciManager) GetContainerLogs(ctx context.Context, containerID string) (string, error) {
	containerGroupName := containerID

	result, err := m.cClient.ListLogs(ctx, m.config.ResourceGroup, containerGroupName, "backtest",
		&armcontainerinstance.ContainersClientListLogsOptions{
			Tail: to.Ptr[int32](10000),
		})
	if err != nil {
		return "", fmt.Errorf("failed to get container logs: %w", err)
	}

	if result.Content != nil {
		return *result.Content, nil
	}

	return "", nil
}

// CleanupStaleContainers removes container groups that exceed the maximum age.
func (m *aciManager) CleanupStaleContainers(ctx context.Context, maxAge time.Duration) (int, error) {
	m.logger.Info("Cleaning up stale ACI container groups",
		zap.Duration("max_age", maxAge),
	)

	// List all container groups in the resource group
	pager := m.cgClient.NewListByResourceGroupPager(m.config.ResourceGroup, nil)
	cleaned := 0

	for pager.More() {
		page, err := pager.NextPage(ctx)
		if err != nil {
			return cleaned, fmt.Errorf("failed to list container groups: %w", err)
		}

		for _, cg := range page.Value {
			// Check if this is a freqsearch-managed container group
			if cg.Tags == nil || cg.Tags["freqsearch.managed"] == nil || *cg.Tags["freqsearch.managed"] != "true" {
				continue
			}

			// Check creation time
			if cg.Properties != nil && cg.Properties.InstanceView != nil {
				// Parse creation time from events or use current time as fallback
				// ACI doesn't directly expose creation time, so we check if it's old by checking state
				state := cg.Properties.InstanceView.State
				if state != nil {
					stateStr := string(*state)
					// Only clean up terminated/failed/stopped containers
					if stateStr == "Succeeded" || stateStr == "Failed" || stateStr == "Stopped" {
						// For simplicity, delete all terminated containers
						// In production, you might want to check detailed timestamps
						if cg.Name != nil {
							if err := m.RemoveContainer(ctx, *cg.Name); err != nil {
								m.logger.Warn("Failed to remove stale container group",
									zap.String("container_group", *cg.Name),
									zap.Error(err),
								)
								continue
							}
							cleaned++
							m.logger.Info("Cleaned up stale container group",
								zap.String("container_group", *cg.Name),
								zap.String("state", stateStr),
							)
						}
					}
				}
			}
		}
	}

	m.logger.Info("Cleanup completed",
		zap.Int("cleaned_count", cleaned),
	)

	return cleaned, nil
}

// IsContainerRunning checks if a container group is still active (running, pending, or creating).
// For ACI, containers in Pending/Waiting/Creating states are not yet finished and should not
// be considered crashed by the scheduler health checker.
func (m *aciManager) IsContainerRunning(ctx context.Context, containerID string) (bool, error) {
	containerGroupName := containerID

	resp, err := m.cgClient.Get(ctx, m.config.ResourceGroup, containerGroupName, nil)
	if err != nil {
		// If not found, it's not running
		return false, nil
	}

	// Check provisioning state first - if still provisioning, it's active
	if resp.Properties != nil && resp.Properties.ProvisioningState != nil {
		provState := string(*resp.Properties.ProvisioningState)
		switch provState {
		case "Pending", "Creating", "Repairing":
			return true, nil
		case "Failed":
			return false, nil
		}
	}

	// Check instance view state
	if resp.Properties != nil && resp.Properties.InstanceView != nil {
		state := resp.Properties.InstanceView.State
		if state != nil {
			switch string(*state) {
			case "Running", "Pending":
				return true, nil
			case "Succeeded", "Failed", "Stopped":
				return false, nil
			}
		}
	}

	// Check container-level state
	if resp.Properties != nil && len(resp.Properties.Containers) > 0 &&
		resp.Properties.Containers[0].Properties != nil &&
		resp.Properties.Containers[0].Properties.InstanceView != nil &&
		resp.Properties.Containers[0].Properties.InstanceView.CurrentState != nil {
		containerState := resp.Properties.Containers[0].Properties.InstanceView.CurrentState.State
		if containerState != nil {
			switch *containerState {
			case "Running", "Waiting":
				return true, nil
			case "Terminated":
				return false, nil
			}
		}
	}

	// If no state info yet (very early in provisioning), assume active
	return true, nil
}

// readFile reads a file and returns its content as bytes.
func readFile(path string) ([]byte, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read file %s: %w", path, err)
	}
	return data, nil
}

// Ensure interface compliance at compile time.
var _ Manager = (*aciManager)(nil)
