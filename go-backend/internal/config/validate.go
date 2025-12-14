package config

import (
	"errors"
	"fmt"
	"strings"
)

// ValidationError represents a configuration validation error.
type ValidationError struct {
	Field   string
	Message string
}

func (e ValidationError) Error() string {
	return fmt.Sprintf("%s: %s", e.Field, e.Message)
}

// ValidationErrors is a collection of validation errors.
type ValidationErrors []ValidationError

func (e ValidationErrors) Error() string {
	if len(e) == 0 {
		return ""
	}
	var msgs []string
	for _, err := range e {
		msgs = append(msgs, err.Error())
	}
	return "validation errors: " + strings.Join(msgs, "; ")
}

// Validate validates the configuration and returns any errors.
func Validate(cfg *Config) error {
	var errs ValidationErrors

	// Validate environment
	validEnvs := map[string]bool{
		"development": true,
		"staging":     true,
		"production":  true,
		"test":        true,
	}
	if !validEnvs[cfg.Env] {
		errs = append(errs, ValidationError{
			Field:   "env",
			Message: "must be one of: development, staging, production, test",
		})
	}

	// Validate ports
	if cfg.GoBackend.GRPCPort <= 0 || cfg.GoBackend.GRPCPort > 65535 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.grpc_port",
			Message: "must be a valid port number (1-65535)",
		})
	}
	if cfg.GoBackend.HTTPPort <= 0 || cfg.GoBackend.HTTPPort > 65535 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.http_port",
			Message: "must be a valid port number (1-65535)",
		})
	}
	if cfg.GoBackend.GRPCPort == cfg.GoBackend.HTTPPort {
		errs = append(errs, ValidationError{
			Field:   "go_backend.grpc_port/http_port",
			Message: "gRPC and HTTP ports must be different",
		})
	}

	// Validate database
	errs = append(errs, validateDatabase(&cfg.GoBackend.Database)...)

	// Validate RabbitMQ
	errs = append(errs, validateRabbitMQ(&cfg.GoBackend.RabbitMQ)...)

	// Validate Scheduler
	errs = append(errs, validateScheduler(&cfg.GoBackend.Scheduler)...)

	// Validate Docker
	errs = append(errs, validateDocker(&cfg.GoBackend.Docker)...)

	// Validate Logging
	errs = append(errs, validateLogging(&cfg.Logging)...)

	if len(errs) > 0 {
		return errs
	}
	return nil
}

func validateDatabase(db *DatabaseConfig) ValidationErrors {
	var errs ValidationErrors

	if db.Host == "" {
		errs = append(errs, ValidationError{
			Field:   "go_backend.database.host",
			Message: "is required",
		})
	}
	if db.Port <= 0 || db.Port > 65535 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.database.port",
			Message: "must be a valid port number (1-65535)",
		})
	}
	if db.User == "" {
		errs = append(errs, ValidationError{
			Field:   "go_backend.database.user",
			Message: "is required",
		})
	}
	if db.Password == "" {
		errs = append(errs, ValidationError{
			Field:   "go_backend.database.password",
			Message: "is required",
		})
	}
	if db.Name == "" {
		errs = append(errs, ValidationError{
			Field:   "go_backend.database.name",
			Message: "is required",
		})
	}

	validSSLModes := map[string]bool{
		"disable":     true,
		"require":     true,
		"verify-ca":   true,
		"verify-full": true,
	}
	if !validSSLModes[db.SSLMode] {
		errs = append(errs, ValidationError{
			Field:   "go_backend.database.sslmode",
			Message: "must be one of: disable, require, verify-ca, verify-full",
		})
	}

	if db.MaxConnections <= 0 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.database.max_connections",
			Message: "must be greater than 0",
		})
	}
	if db.MaxIdleConnections < 0 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.database.max_idle_connections",
			Message: "must be non-negative",
		})
	}
	if db.MaxIdleConnections > db.MaxConnections {
		errs = append(errs, ValidationError{
			Field:   "go_backend.database.max_idle_connections",
			Message: "must not exceed max_connections",
		})
	}

	return errs
}

func validateRabbitMQ(mq *RabbitMQConfig) ValidationErrors {
	var errs ValidationErrors

	if mq.URL == "" {
		errs = append(errs, ValidationError{
			Field:   "go_backend.rabbitmq.url",
			Message: "is required",
		})
	} else if !strings.HasPrefix(mq.URL, "amqp://") && !strings.HasPrefix(mq.URL, "amqps://") {
		errs = append(errs, ValidationError{
			Field:   "go_backend.rabbitmq.url",
			Message: "must start with amqp:// or amqps://",
		})
	}

	if mq.Exchange == "" {
		errs = append(errs, ValidationError{
			Field:   "go_backend.rabbitmq.exchange",
			Message: "is required",
		})
	}

	if mq.PrefetchCount <= 0 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.rabbitmq.prefetch_count",
			Message: "must be greater than 0",
		})
	}

	return errs
}

func validateScheduler(s *SchedulerConfig) ValidationErrors {
	var errs ValidationErrors

	if s.MaxConcurrentBacktests <= 0 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.scheduler.max_concurrent_backtests",
			Message: "must be greater than 0",
		})
	}
	if s.MaxConcurrentBacktests > 100 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.scheduler.max_concurrent_backtests",
			Message: "should not exceed 100 for reasonable resource usage",
		})
	}

	if s.PollIntervalSeconds <= 0 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.scheduler.poll_interval_seconds",
			Message: "must be greater than 0",
		})
	}

	if s.JobTimeoutMinutes <= 0 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.scheduler.job_timeout_minutes",
			Message: "must be greater than 0",
		})
	}

	if s.MaxRetries < 0 {
		errs = append(errs, ValidationError{
			Field:   "go_backend.scheduler.max_retries",
			Message: "must be non-negative",
		})
	}

	return errs
}

func validateDocker(d *DockerConfig) ValidationErrors {
	var errs ValidationErrors

	if d.Image == "" {
		errs = append(errs, ValidationError{
			Field:   "go_backend.docker.image",
			Message: "is required",
		})
	}

	if d.DataMount == "" {
		errs = append(errs, ValidationError{
			Field:   "go_backend.docker.data_mount",
			Message: "is required",
		})
	}

	if d.CPULimit == "" {
		errs = append(errs, ValidationError{
			Field:   "go_backend.docker.cpu_limit",
			Message: "is required",
		})
	}

	if d.MemoryLimit == "" {
		errs = append(errs, ValidationError{
			Field:   "go_backend.docker.memory_limit",
			Message: "is required",
		})
	}

	return errs
}

func validateLogging(l *LoggingConfig) ValidationErrors {
	var errs ValidationErrors

	validLevels := map[string]bool{
		"debug": true,
		"info":  true,
		"warn":  true,
		"error": true,
	}
	if !validLevels[l.Level] {
		errs = append(errs, ValidationError{
			Field:   "logging.level",
			Message: "must be one of: debug, info, warn, error",
		})
	}

	validFormats := map[string]bool{
		"json":    true,
		"console": true,
	}
	if !validFormats[l.Format] {
		errs = append(errs, ValidationError{
			Field:   "logging.format",
			Message: "must be one of: json, console",
		})
	}

	return errs
}

// IsValidationError checks if an error is a validation error.
func IsValidationError(err error) bool {
	var ve ValidationError
	var ves ValidationErrors
	return errors.As(err, &ve) || errors.As(err, &ves)
}
