// Package config provides configuration management for the FreqSearch backend.
package config

import "time"

// Config is the root configuration structure.
type Config struct {
	Env       string          `yaml:"env"`
	GoBackend GoBackendConfig `yaml:"go_backend"`
	Logging   LoggingConfig   `yaml:"logging"`
}

// GoBackendConfig contains all backend service configurations.
type GoBackendConfig struct {
	GRPCPort         int             `yaml:"grpc_port"`
	HTTPPort         int             `yaml:"http_port"`
	Database         DatabaseConfig  `yaml:"database"`
	RabbitMQ         RabbitMQConfig  `yaml:"rabbitmq"`
	Scheduler        SchedulerConfig `yaml:"scheduler"`
	Docker           DockerConfig    `yaml:"docker"`
	ContainerBackend string          `yaml:"container_backend"` // "docker" | "aci" | "hybrid"
	ACI              ACIConfig       `yaml:"aci"`
}

// DatabaseConfig contains PostgreSQL connection settings.
type DatabaseConfig struct {
	Host               string `yaml:"host"`
	Port               int    `yaml:"port"`
	User               string `yaml:"user"`
	Password           string `yaml:"password"`
	Name               string `yaml:"name"`
	SSLMode            string `yaml:"sslmode"`
	MaxConnections     int    `yaml:"max_connections"`
	MaxIdleConnections int    `yaml:"max_idle_connections"`
	ConnMaxLifetime    string `yaml:"conn_max_lifetime"`
}

// ConnectionString returns the PostgreSQL connection string.
func (d *DatabaseConfig) ConnectionString() string {
	return "postgres://" + d.User + ":" + d.Password + "@" + d.Host + ":" +
		itoa(d.Port) + "/" + d.Name + "?sslmode=" + d.SSLMode
}

// RabbitMQConfig contains RabbitMQ connection settings.
type RabbitMQConfig struct {
	URL              string `yaml:"url"`
	Exchange         string `yaml:"exchange"`
	PrefetchCount    int    `yaml:"prefetch_count"`
	ReconnectDelay   string `yaml:"reconnect_delay"`
	MaxReconnectWait string `yaml:"max_reconnect_wait"`
}

// SchedulerConfig contains task scheduler settings.
type SchedulerConfig struct {
	MaxConcurrentBacktests int    `yaml:"max_concurrent_backtests"`
	PollIntervalSeconds    int    `yaml:"poll_interval_seconds"`
	JobTimeoutMinutes      int    `yaml:"job_timeout_minutes"`
	MaxRetries             int    `yaml:"max_retries"`
	ShutdownTimeout        string `yaml:"shutdown_timeout"`
}

// JobTimeout returns the job timeout as a time.Duration.
func (s *SchedulerConfig) JobTimeout() time.Duration {
	return time.Duration(s.JobTimeoutMinutes) * time.Minute
}

// PollInterval returns the poll interval as a time.Duration.
func (s *SchedulerConfig) PollInterval() time.Duration {
	return time.Duration(s.PollIntervalSeconds) * time.Second
}

// DockerConfig contains Docker container settings.
type DockerConfig struct {
	Image            string `yaml:"image"`
	Network          string `yaml:"network"`
	DataMount        string `yaml:"data_mount"`
	StrategyMount    string `yaml:"strategy_mount"`
	ConfigMount      string `yaml:"config_mount"`
	CPULimit         string `yaml:"cpu_limit"`
	MemoryLimit      string `yaml:"memory_limit"`
	BaseConfigPath   string `yaml:"base_config_path"`
	ContainerTimeout string `yaml:"container_timeout"`
}

// ACIConfig contains Azure Container Instances settings.
type ACIConfig struct {
	SubscriptionID     string  `yaml:"subscription_id"`
	ResourceGroup      string  `yaml:"resource_group"`
	Location           string  `yaml:"location"`
	Image              string  `yaml:"image"`
	RegistryServer     string  `yaml:"registry_server"`
	RegistryUsername   string  `yaml:"registry_username"`
	RegistryPassword   string  `yaml:"registry_password"`
	ManagedIdentityID  string  `yaml:"managed_identity_id"`
	CPUCores           float64 `yaml:"cpu_cores"`
	MemoryGB           float64 `yaml:"memory_gb"`
	StorageAccountName string  `yaml:"storage_account_name"`
	StorageAccountKey  string  `yaml:"storage_account_key"`
	FileShareName      string  `yaml:"file_share_name"`
	BaseConfigPath     string  `yaml:"base_config_path"`
	ContainerTimeout   string  `yaml:"container_timeout"`
	PollInterval       string  `yaml:"poll_interval"`
	AuthMethod         string  `yaml:"auth_method"`
	TenantID           string  `yaml:"tenant_id"`
	ClientID           string  `yaml:"client_id"`
	ClientSecret       string  `yaml:"client_secret"`
}

// GetContainerTimeout returns the container timeout as a time.Duration.
func (a *ACIConfig) GetContainerTimeout() time.Duration {
	d, err := time.ParseDuration(a.ContainerTimeout)
	if err != nil {
		return 15 * time.Minute
	}
	return d
}

// GetPollInterval returns the poll interval as a time.Duration.
func (a *ACIConfig) GetPollInterval() time.Duration {
	d, err := time.ParseDuration(a.PollInterval)
	if err != nil {
		return 5 * time.Second
	}
	return d
}

// LoggingConfig contains logging settings.
type LoggingConfig struct {
	Level      string `yaml:"level"`
	Format     string `yaml:"format"`
	OutputPath string `yaml:"output_path"`
}

// Default returns the default configuration.
func Default() *Config {
	return &Config{
		Env: "development",
		GoBackend: GoBackendConfig{
			GRPCPort: 50051,
			HTTPPort: 8083,
			Database: DatabaseConfig{
				Host:               "localhost",
				Port:               5432,
				User:               "postgres",
				Password:           "postgres",
				Name:               "freqsearch_dev",
				SSLMode:            "disable",
				MaxConnections:     25,
				MaxIdleConnections: 5,
				ConnMaxLifetime:    "1h",
			},
			RabbitMQ: RabbitMQConfig{
				URL:              "amqp://guest:guest@localhost:5672/",
				Exchange:         "freqsearch.events",
				PrefetchCount:    10,
				ReconnectDelay:   "5s",
				MaxReconnectWait: "30s",
			},
			Scheduler: SchedulerConfig{
				MaxConcurrentBacktests: 8,
				PollIntervalSeconds:    1,
				JobTimeoutMinutes:      10,
				MaxRetries:             1,
				ShutdownTimeout:        "30s",
			},
			Docker: DockerConfig{
				Image:            "freqtradeorg/freqtrade:2025.4_freqai",
				Network:          "freqsearch_network",
				DataMount:        "./data/market",
				StrategyMount:    "./data/strategies",
				ConfigMount:      "/tmp/freqsearch/configs",
				CPULimit:         "2.0",
				MemoryLimit:      "2g",
				BaseConfigPath:   "configs/freqtrade/base_config.json",
				ContainerTimeout: "15m",
			},
			ContainerBackend: "docker",
			ACI: ACIConfig{
				CPUCores:         2.0,
				MemoryGB:         2.0,
				ContainerTimeout: "15m",
				PollInterval:     "5s",
				AuthMethod:       "default",
			},
		},
		Logging: LoggingConfig{
			Level:      "info",
			Format:     "json",
			OutputPath: "stdout",
		},
	}
}

// itoa converts int to string (simple helper to avoid importing strconv).
func itoa(i int) string {
	if i == 0 {
		return "0"
	}
	var b [20]byte
	n := len(b)
	negative := i < 0
	if negative {
		i = -i
	}
	for i > 0 {
		n--
		b[n] = byte('0' + i%10)
		i /= 10
	}
	if negative {
		n--
		b[n] = '-'
	}
	return string(b[n:])
}
