package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"

	"gopkg.in/yaml.v3"
)

// Load loads configuration from a YAML file and applies environment variable overrides.
func Load(configPath string) (*Config, error) {
	cfg := Default()

	// Load from YAML file if exists
	if configPath != "" {
		if err := loadFromYAML(configPath, cfg); err != nil {
			return nil, fmt.Errorf("failed to load config from %s: %w", configPath, err)
		}
	}

	// Apply environment variable overrides
	applyEnvOverrides(cfg)

	// Validate configuration
	if err := Validate(cfg); err != nil {
		return nil, fmt.Errorf("config validation failed: %w", err)
	}

	return cfg, nil
}

// loadFromYAML loads configuration from a YAML file.
func loadFromYAML(path string, cfg *Config) error {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			// File doesn't exist, use defaults
			return nil
		}
		return err
	}

	if err := yaml.Unmarshal(data, cfg); err != nil {
		return fmt.Errorf("failed to parse YAML: %w", err)
	}

	return nil
}

// applyEnvOverrides applies environment variable overrides to the configuration.
func applyEnvOverrides(cfg *Config) {
	// Environment
	if v := os.Getenv("ENV"); v != "" {
		cfg.Env = v
	}

	// gRPC/HTTP ports
	if v := os.Getenv("GRPC_PORT"); v != "" {
		if port, err := strconv.Atoi(v); err == nil {
			cfg.GoBackend.GRPCPort = port
		}
	}
	if v := os.Getenv("HTTP_PORT"); v != "" {
		if port, err := strconv.Atoi(v); err == nil {
			cfg.GoBackend.HTTPPort = port
		}
	}

	// Database
	if v := os.Getenv("DB_HOST"); v != "" {
		cfg.GoBackend.Database.Host = v
	}
	if v := os.Getenv("DB_PORT"); v != "" {
		if port, err := strconv.Atoi(v); err == nil {
			cfg.GoBackend.Database.Port = port
		}
	}
	if v := os.Getenv("DB_USER"); v != "" {
		cfg.GoBackend.Database.User = v
	}
	if v := os.Getenv("DB_PASSWORD"); v != "" {
		cfg.GoBackend.Database.Password = v
	}
	if v := os.Getenv("DB_NAME"); v != "" {
		cfg.GoBackend.Database.Name = v
	}
	if v := os.Getenv("DB_SSLMODE"); v != "" {
		cfg.GoBackend.Database.SSLMode = v
	}
	if v := os.Getenv("DB_MAX_CONNECTIONS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.GoBackend.Database.MaxConnections = n
		}
	}

	// RabbitMQ
	if v := os.Getenv("RABBITMQ_URL"); v != "" {
		cfg.GoBackend.RabbitMQ.URL = v
	}
	if v := os.Getenv("RABBITMQ_EXCHANGE"); v != "" {
		cfg.GoBackend.RabbitMQ.Exchange = v
	}

	// Scheduler
	if v := os.Getenv("MAX_CONCURRENT_BACKTESTS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.GoBackend.Scheduler.MaxConcurrentBacktests = n
		}
	}
	if v := os.Getenv("JOB_TIMEOUT_MINUTES"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.GoBackend.Scheduler.JobTimeoutMinutes = n
		}
	}
	if v := os.Getenv("MAX_RETRIES"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			cfg.GoBackend.Scheduler.MaxRetries = n
		}
	}

	// Docker
	if v := os.Getenv("DOCKER_IMAGE"); v != "" {
		cfg.GoBackend.Docker.Image = v
	}
	if v := os.Getenv("DOCKER_NETWORK"); v != "" {
		cfg.GoBackend.Docker.Network = v
	}
	if v := os.Getenv("DOCKER_DATA_MOUNT"); v != "" {
		cfg.GoBackend.Docker.DataMount = v
	}
	if v := os.Getenv("DOCKER_CPU_LIMIT"); v != "" {
		cfg.GoBackend.Docker.CPULimit = v
	}
	if v := os.Getenv("DOCKER_MEMORY_LIMIT"); v != "" {
		cfg.GoBackend.Docker.MemoryLimit = v
	}
	if v := os.Getenv("FREQTRADE_BASE_CONFIG"); v != "" {
		cfg.GoBackend.Docker.BaseConfigPath = v
	}

	// Container Backend
	if v := os.Getenv("CONTAINER_BACKEND"); v != "" {
		cfg.GoBackend.ContainerBackend = v
	}

	// ACI
	if v := os.Getenv("ACI_SUBSCRIPTION_ID"); v != "" {
		cfg.GoBackend.ACI.SubscriptionID = v
	}
	if v := os.Getenv("ACI_RESOURCE_GROUP"); v != "" {
		cfg.GoBackend.ACI.ResourceGroup = v
	}
	if v := os.Getenv("ACI_LOCATION"); v != "" {
		cfg.GoBackend.ACI.Location = v
	}
	if v := os.Getenv("ACI_IMAGE"); v != "" {
		cfg.GoBackend.ACI.Image = v
	}
	if v := os.Getenv("ACI_REGISTRY_SERVER"); v != "" {
		cfg.GoBackend.ACI.RegistryServer = v
	}
	if v := os.Getenv("ACI_REGISTRY_USERNAME"); v != "" {
		cfg.GoBackend.ACI.RegistryUsername = v
	}
	if v := os.Getenv("ACI_REGISTRY_PASSWORD"); v != "" {
		cfg.GoBackend.ACI.RegistryPassword = v
	}
	if v := os.Getenv("ACI_STORAGE_ACCOUNT_NAME"); v != "" {
		cfg.GoBackend.ACI.StorageAccountName = v
	}
	if v := os.Getenv("ACI_STORAGE_ACCOUNT_KEY"); v != "" {
		cfg.GoBackend.ACI.StorageAccountKey = v
	}
	if v := os.Getenv("ACI_FILE_SHARE_NAME"); v != "" {
		cfg.GoBackend.ACI.FileShareName = v
	}
	if v := os.Getenv("ACI_AUTH_METHOD"); v != "" {
		cfg.GoBackend.ACI.AuthMethod = v
	}
	if v := os.Getenv("ACI_TENANT_ID"); v != "" {
		cfg.GoBackend.ACI.TenantID = v
	}
	if v := os.Getenv("ACI_CLIENT_ID"); v != "" {
		cfg.GoBackend.ACI.ClientID = v
	}
	if v := os.Getenv("ACI_CLIENT_SECRET"); v != "" {
		cfg.GoBackend.ACI.ClientSecret = v
	}

	// Logging
	if v := os.Getenv("LOG_LEVEL"); v != "" {
		cfg.Logging.Level = strings.ToLower(v)
	}
	if v := os.Getenv("LOG_FORMAT"); v != "" {
		cfg.Logging.Format = strings.ToLower(v)
	}
}

// MustLoad loads configuration and panics on error.
func MustLoad(configPath string) *Config {
	cfg, err := Load(configPath)
	if err != nil {
		panic(fmt.Sprintf("failed to load config: %v", err))
	}
	return cfg
}
