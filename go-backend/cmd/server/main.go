// FreqSearch Backend Server
// Entry point for the Go backend service

package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/api/grpc"
	httpapi "github.com/saltfish/freqsearch/go-backend/internal/api/http"
	"github.com/saltfish/freqsearch/go-backend/internal/config"
	"github.com/saltfish/freqsearch/go-backend/internal/db"
	"github.com/saltfish/freqsearch/go-backend/internal/db/repository"
	"github.com/saltfish/freqsearch/go-backend/internal/docker"
	"github.com/saltfish/freqsearch/go-backend/internal/events"
	"github.com/saltfish/freqsearch/go-backend/internal/scheduler"
)

// Build-time variables (set via ldflags)
var (
	Version   = "dev"
	BuildTime = "unknown"
)

func main() {
	// Parse command line flags
	configPath := flag.String("config", "", "Path to configuration file (YAML)")
	flag.Parse()

	fmt.Println("FreqSearch Backend", *configPath)
	// Load configuration
	cfg, err := config.Load(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to load configuration: %v\n", err)
		os.Exit(1)
	}

	// Initialize logger
	logger, err := initLogger(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to initialize logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()

	logger.Info("Starting FreqSearch Backend",
		zap.String("version", Version),
		zap.String("build_time", BuildTime),
		zap.String("environment", cfg.Env),
		zap.String("log_level", cfg.Logging.Level),
	)

	// Create root context
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Handle shutdown signals
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		sig := <-sigCh
		logger.Info("Received shutdown signal", zap.String("signal", sig.String()))
		cancel()
	}()

	// Initialize components
	if err := run(ctx, cfg, logger); err != nil {
		logger.Error("Application error", zap.Error(err))
		os.Exit(1)
	}

	logger.Info("FreqSearch Backend stopped")
}

// run initializes and runs all application components.
func run(ctx context.Context, cfg *config.Config, logger *zap.Logger) error {
	// 1. Connect to PostgreSQL
	logger.Info("Connecting to PostgreSQL...")
	pool, err := db.NewPool(ctx, &cfg.GoBackend.Database, logger)
	if err != nil {
		return fmt.Errorf("failed to connect to database: %w", err)
	}
	defer pool.Close()
	logger.Info("Connected to PostgreSQL")

	// 2. Initialize repositories
	repos := repository.NewRepositories(pool)

	// 3. Initialize Docker manager
	logger.Info("Initializing Docker manager...")
	dockerManager, err := docker.NewDockerManager(&cfg.GoBackend.Docker, logger)
	if err != nil {
		return fmt.Errorf("failed to initialize Docker manager: %w", err)
	}
	logger.Info("Docker manager initialized")

	// 4. Initialize event publisher (RabbitMQ)
	var eventPublisher events.Publisher
	if cfg.GoBackend.RabbitMQ.URL != "" {
		logger.Info("Connecting to RabbitMQ...")
		publisher, err := events.NewRabbitMQPublisher(&cfg.GoBackend.RabbitMQ, logger)
		if err != nil {
			logger.Warn("Failed to connect to RabbitMQ, using no-op publisher", zap.Error(err))
			eventPublisher = events.NewNoOpPublisher()
		} else {
			eventPublisher = publisher
			defer publisher.Close()
			logger.Info("Connected to RabbitMQ")
		}
	} else {
		logger.Info("RabbitMQ not configured, using no-op publisher")
		eventPublisher = events.NewNoOpPublisher()
	}

	// 5. Initialize Scout Scheduler
	logger.Info("Initializing Scout scheduler...")
	scoutSched := scheduler.NewScoutScheduler(repos, eventPublisher, logger)
	if err := scoutSched.Start(); err != nil {
		return fmt.Errorf("failed to start scout scheduler: %w", err)
	}
	logger.Info("Scout scheduler started")

	// 6. Initialize scheduler
	logger.Info("Initializing scheduler...")
	sched := scheduler.NewScheduler(
		&cfg.GoBackend.Scheduler,
		repos,
		dockerManager,
		eventPublisher,
		logger,
	)

	if err := sched.Start(); err != nil {
		return fmt.Errorf("failed to start scheduler: %w", err)
	}
	logger.Info("Scheduler started")

	// 7. Initialize event subscriber (RabbitMQ) for receiving events from Python agents
	var eventSubscriber events.Subscriber
	if cfg.GoBackend.RabbitMQ.URL != "" {
		logger.Info("Initializing RabbitMQ subscriber...")
		subscriber, err := events.NewRabbitMQSubscriber(
			&cfg.GoBackend.RabbitMQ,
			"go-backend-events",
			logger,
		)
		if err != nil {
			logger.Warn("Failed to create RabbitMQ subscriber, scout events will not be processed", zap.Error(err))
		} else {
			eventSubscriber = subscriber
			defer subscriber.Close()
			logger.Info("RabbitMQ subscriber created")
		}
	}

	// 8. Start HTTP server (health/metrics + REST API)
	httpAddr := fmt.Sprintf(":%d", cfg.GoBackend.HTTPPort)
	httpServer := httpapi.NewServer(httpAddr, pool, repos, sched, logger)

	// Set event publisher, scout scheduler, and subscriber for HTTP handlers
	httpServer.SetEventPublisher(eventPublisher)
	httpServer.SetScoutScheduler(scoutSched)
	if eventSubscriber != nil {
		httpServer.SetSubscriber(eventSubscriber)
	}

	go func() {
		logger.Info("HTTP server starting", zap.String("address", httpAddr))
		if err := httpServer.Start(); err != nil && err != http.ErrServerClosed {
			logger.Error("HTTP server error", zap.Error(err))
		}
	}()

	// 9. Start gRPC server
	grpcAddr := fmt.Sprintf(":%d", cfg.GoBackend.GRPCPort)
	grpcServer := grpc.NewServer(repos, sched, eventPublisher, logger)

	go func() {
		logger.Info("gRPC server starting", zap.String("address", grpcAddr))
		if err := grpcServer.Start(grpcAddr); err != nil {
			logger.Error("gRPC server error", zap.Error(err))
		}
	}()

	logger.Info("FreqSearch Backend initialized and running",
		zap.String("grpc_address", grpcAddr),
		zap.String("http_address", httpAddr),
	)

	// Wait for shutdown signal
	<-ctx.Done()

	logger.Info("Shutting down FreqSearch Backend...")

	// Graceful shutdown with timeout
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	// Stop accepting new gRPC requests
	grpcServer.Stop()
	logger.Info("gRPC server stopped")

	// Stop HTTP server
	if err := httpServer.Stop(shutdownCtx); err != nil {
		logger.Error("Error stopping HTTP server", zap.Error(err))
	}
	logger.Info("HTTP server stopped")

	// Stop scheduler (waits for active jobs)
	if err := sched.Stop(); err != nil {
		logger.Error("Error stopping scheduler", zap.Error(err))
	}
	logger.Info("Scheduler stopped")

	// Stop Scout scheduler
	logger.Info("Stopping Scout scheduler...")
	if err := scoutSched.Stop(); err != nil {
		logger.Error("Error stopping scout scheduler", zap.Error(err))
	}
	logger.Info("Scout scheduler stopped")

	return nil
}

// initLogger initializes the zap logger based on configuration.
func initLogger(cfg *config.Config) (*zap.Logger, error) {
	var zapCfg zap.Config

	if cfg.Logging.Format == "json" {
		zapCfg = zap.NewProductionConfig()
	} else {
		zapCfg = zap.NewDevelopmentConfig()
	}

	// Set log level
	switch cfg.Logging.Level {
	case "debug":
		zapCfg.Level = zap.NewAtomicLevelAt(zap.DebugLevel)
	case "info":
		zapCfg.Level = zap.NewAtomicLevelAt(zap.InfoLevel)
	case "warn":
		zapCfg.Level = zap.NewAtomicLevelAt(zap.WarnLevel)
	case "error":
		zapCfg.Level = zap.NewAtomicLevelAt(zap.ErrorLevel)
	default:
		zapCfg.Level = zap.NewAtomicLevelAt(zap.InfoLevel)
	}

	return zapCfg.Build()
}
