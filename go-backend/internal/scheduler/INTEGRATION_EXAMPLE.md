# Scout Scheduler Integration Example

This document shows how to integrate the ScoutScheduler into your main application.

## Complete Integration in main.go

```go
package main

import (
    "context"
    "os"
    "os/signal"
    "syscall"
    "time"

    "go.uber.org/zap"

    "github.com/saltfish/freqsearch/go-backend/internal/config"
    "github.com/saltfish/freqsearch/go-backend/internal/db"
    "github.com/saltfish/freqsearch/go-backend/internal/db/repository"
    "github.com/saltfish/freqsearch/go-backend/internal/docker"
    "github.com/saltfish/freqsearch/go-backend/internal/events"
    "github.com/saltfish/freqsearch/go-backend/internal/scheduler"
)

func main() {
    // Load configuration
    cfg, err := config.Load()
    if err != nil {
        panic("Failed to load config: " + err.Error())
    }

    // Initialize logger
    logger, err := zap.NewProduction()
    if err != nil {
        panic("Failed to create logger: " + err.Error())
    }
    defer logger.Sync()

    // Connect to database
    pool, err := db.NewPool(&cfg.Database)
    if err != nil {
        logger.Fatal("Failed to connect to database", zap.Error(err))
    }
    defer pool.Close()

    // Initialize repositories
    repos := repository.NewRepositories(pool)

    // Initialize event publisher
    eventPublisher, err := events.NewRabbitMQPublisher(&cfg.RabbitMQ, logger)
    if err != nil {
        logger.Fatal("Failed to create event publisher", zap.Error(err))
    }
    defer eventPublisher.Close()

    // Initialize Docker manager (for backtest scheduler)
    dockerManager, err := docker.NewManager(&cfg.Docker, logger)
    if err != nil {
        logger.Fatal("Failed to create Docker manager", zap.Error(err))
    }
    defer dockerManager.Close()

    // ========================================
    // Initialize Backtest Scheduler
    // ========================================
    backtestScheduler := scheduler.NewScheduler(
        &cfg.Scheduler,
        repos,
        dockerManager,
        eventPublisher,
        logger,
    )

    if err := backtestScheduler.Start(); err != nil {
        logger.Fatal("Failed to start backtest scheduler", zap.Error(err))
    }
    defer backtestScheduler.Stop()

    logger.Info("Backtest scheduler started")

    // ========================================
    // Initialize Scout Scheduler
    // ========================================
    scoutScheduler := scheduler.NewScoutScheduler(
        repos,
        eventPublisher,
        logger,
    )

    if err := scoutScheduler.Start(); err != nil {
        logger.Fatal("Failed to start Scout scheduler", zap.Error(err))
    }
    defer scoutScheduler.Stop()

    logger.Info("Scout scheduler started")

    // ========================================
    // Setup HTTP API with scheduler access
    // ========================================
    router := setupRouter(repos, eventPublisher, scoutScheduler, backtestScheduler, logger)

    // Start HTTP server in goroutine
    srv := &http.Server{
        Addr:    ":" + cfg.Server.Port,
        Handler: router,
    }

    go func() {
        logger.Info("Starting HTTP server", zap.String("port", cfg.Server.Port))
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            logger.Fatal("HTTP server failed", zap.Error(err))
        }
    }()

    // ========================================
    // Graceful Shutdown
    // ========================================
    quit := make(chan os.Signal, 1)
    signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
    <-quit

    logger.Info("Shutting down gracefully...")

    // Shutdown HTTP server
    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()

    if err := srv.Shutdown(ctx); err != nil {
        logger.Error("HTTP server forced to shutdown", zap.Error(err))
    }

    // Stop schedulers (deferred, so they stop after HTTP server)
    logger.Info("Shutdown complete")
}

func setupRouter(
    repos *repository.Repositories,
    publisher events.Publisher,
    scoutScheduler *scheduler.ScoutScheduler,
    backtestScheduler *scheduler.Scheduler,
    logger *zap.Logger,
) *gin.Engine {
    router := gin.Default()

    // ... existing routes ...

    // ========================================
    // Scout Schedule Management API
    // ========================================
    scoutAPI := router.Group("/api/scout")
    {
        // Trigger manual Scout run
        scoutAPI.POST("/trigger", func(c *gin.Context) {
            var req struct {
                Source        string `json:"source" binding:"required"`
                MaxStrategies int    `json:"max_strategies" binding:"required,min=1"`
            }

            if err := c.ShouldBindJSON(&req); err != nil {
                c.JSON(400, gin.H{"error": err.Error()})
                return
            }

            // Create manual run
            run := domain.NewScoutRun(
                domain.ScoutTriggerTypeManual,
                "Manual trigger via API",
                req.Source,
                req.MaxStrategies,
            )

            if err := repos.Scout.CreateRun(c.Request.Context(), run); err != nil {
                logger.Error("Failed to create Scout run", zap.Error(err))
                c.JSON(500, gin.H{"error": "Failed to create run"})
                return
            }

            // Publish event
            event := events.NewScoutTriggerEvent(run)
            if err := publisher.PublishScoutTrigger(event); err != nil {
                logger.Error("Failed to publish scout trigger event", zap.Error(err))
            }

            c.JSON(200, run)
        })

        // List schedules
        scoutAPI.GET("/schedules", func(c *gin.Context) {
            query := domain.ScoutScheduleQuery{
                Page:     1,
                PageSize: 20,
            }
            // Parse query params...

            schedules, total, err := repos.Scout.ListSchedules(c.Request.Context(), query)
            if err != nil {
                c.JSON(500, gin.H{"error": "Failed to list schedules"})
                return
            }

            c.JSON(200, gin.H{
                "schedules": schedules,
                "total":     total,
                "page":      query.Page,
                "page_size": query.PageSize,
            })
        })

        // Create schedule
        scoutAPI.POST("/schedules", func(c *gin.Context) {
            var req struct {
                Name           string `json:"name" binding:"required"`
                CronExpression string `json:"cron_expression" binding:"required"`
                Source         string `json:"source" binding:"required"`
                MaxStrategies  int    `json:"max_strategies" binding:"required,min=1"`
            }

            if err := c.ShouldBindJSON(&req); err != nil {
                c.JSON(400, gin.H{"error": err.Error()})
                return
            }

            schedule := domain.NewScoutSchedule(
                req.Name,
                req.CronExpression,
                req.Source,
                req.MaxStrategies,
            )

            if err := repos.Scout.CreateSchedule(c.Request.Context(), schedule); err != nil {
                c.JSON(500, gin.H{"error": "Failed to create schedule"})
                return
            }

            // Reload scheduler to pick up new schedule
            if err := scoutScheduler.ReloadSchedules(); err != nil {
                logger.Error("Failed to reload schedules", zap.Error(err))
            }

            c.JSON(201, schedule)
        })

        // Update schedule
        scoutAPI.PUT("/schedules/:id", func(c *gin.Context) {
            id, err := uuid.Parse(c.Param("id"))
            if err != nil {
                c.JSON(400, gin.H{"error": "Invalid schedule ID"})
                return
            }

            schedule, err := repos.Scout.GetScheduleByID(c.Request.Context(), id)
            if err != nil {
                c.JSON(404, gin.H{"error": "Schedule not found"})
                return
            }

            var req struct {
                Name           *string `json:"name"`
                CronExpression *string `json:"cron_expression"`
                Source         *string `json:"source"`
                MaxStrategies  *int    `json:"max_strategies"`
                Enabled        *bool   `json:"enabled"`
            }

            if err := c.ShouldBindJSON(&req); err != nil {
                c.JSON(400, gin.H{"error": err.Error()})
                return
            }

            // Update fields
            if req.Name != nil {
                schedule.Name = *req.Name
            }
            if req.CronExpression != nil {
                schedule.CronExpression = *req.CronExpression
            }
            if req.Source != nil {
                schedule.Source = *req.Source
            }
            if req.MaxStrategies != nil {
                schedule.MaxStrategies = *req.MaxStrategies
            }
            if req.Enabled != nil {
                schedule.Enabled = *req.Enabled
            }

            if err := repos.Scout.UpdateSchedule(c.Request.Context(), schedule); err != nil {
                c.JSON(500, gin.H{"error": "Failed to update schedule"})
                return
            }

            // Reload scheduler
            if err := scoutScheduler.ReloadSchedules(); err != nil {
                logger.Error("Failed to reload schedules", zap.Error(err))
            }

            c.JSON(200, schedule)
        })

        // Delete schedule
        scoutAPI.DELETE("/schedules/:id", func(c *gin.Context) {
            id, err := uuid.Parse(c.Param("id"))
            if err != nil {
                c.JSON(400, gin.H{"error": "Invalid schedule ID"})
                return
            }

            if err := repos.Scout.DeleteSchedule(c.Request.Context(), id); err != nil {
                c.JSON(500, gin.H{"error": "Failed to delete schedule"})
                return
            }

            // Reload scheduler
            if err := scoutScheduler.ReloadSchedules(); err != nil {
                logger.Error("Failed to reload schedules", zap.Error(err))
            }

            c.JSON(204, nil)
        })

        // Get Scout runs
        scoutAPI.GET("/runs", func(c *gin.Context) {
            query := domain.ScoutRunQuery{
                Page:     1,
                PageSize: 20,
            }
            // Parse query params...

            runs, total, err := repos.Scout.ListRuns(c.Request.Context(), query)
            if err != nil {
                c.JSON(500, gin.H{"error": "Failed to list runs"})
                return
            }

            c.JSON(200, gin.H{
                "runs":      runs,
                "total":     total,
                "page":      query.Page,
                "page_size": query.PageSize,
            })
        })

        // Get Scout run by ID
        scoutAPI.GET("/runs/:id", func(c *gin.Context) {
            id, err := uuid.Parse(c.Param("id"))
            if err != nil {
                c.JSON(400, gin.H{"error": "Invalid run ID"})
                return
            }

            run, err := repos.Scout.GetRunByID(c.Request.Context(), id)
            if err != nil {
                c.JSON(404, gin.H{"error": "Run not found"})
                return
            }

            c.JSON(200, run)
        })

        // Reload schedules endpoint (for manual refresh)
        scoutAPI.POST("/schedules/reload", func(c *gin.Context) {
            if err := scoutScheduler.ReloadSchedules(); err != nil {
                logger.Error("Failed to reload schedules", zap.Error(err))
                c.JSON(500, gin.H{"error": "Failed to reload schedules"})
                return
            }

            c.JSON(200, gin.H{"message": "Schedules reloaded successfully"})
        })
    }

    return router
}
```

## Environment Variables

Add these to your `.env` file if needed:

```bash
# Scout Scheduler Configuration
SCOUT_SCHEDULE_POLL_INTERVAL=30s
```

## Database Migrations

Ensure you have the Scout tables created:

```sql
-- Create scout_schedules table
CREATE TABLE scout_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    cron_expression VARCHAR(255) NOT NULL,
    source VARCHAR(255) NOT NULL,
    max_strategies INT NOT NULL DEFAULT 10,
    enabled BOOLEAN NOT NULL DEFAULT true,
    last_run_id UUID REFERENCES scout_runs(id),
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create scout_runs table
CREATE TABLE scout_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_type VARCHAR(50) NOT NULL,
    triggered_by VARCHAR(255),
    source VARCHAR(255) NOT NULL,
    max_strategies INT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    metrics JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_scout_schedules_enabled ON scout_schedules(enabled);
CREATE INDEX idx_scout_schedules_next_run ON scout_schedules(next_run_at);
CREATE INDEX idx_scout_runs_status ON scout_runs(status);
CREATE INDEX idx_scout_runs_created_at ON scout_runs(created_at);
```

## Testing the Integration

### 1. Create a Schedule

```bash
curl -X POST http://localhost:8080/api/scout/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily StratNinja Scout",
    "cron_expression": "0 0 * * *",
    "source": "stratninja",
    "max_strategies": 20
  }'
```

### 2. List Schedules

```bash
curl http://localhost:8080/api/scout/schedules
```

### 3. Trigger Manual Run

```bash
curl -X POST http://localhost:8080/api/scout/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "source": "stratninja",
    "max_strategies": 10
  }'
```

### 4. List Runs

```bash
curl http://localhost:8080/api/scout/runs
```

### 5. Reload Schedules

```bash
curl -X POST http://localhost:8080/api/scout/schedules/reload
```

## Monitoring

### Log Messages to Watch For

```
INFO  Starting Scout scheduler  poll_interval=30s
INFO  Loaded Scout schedules    count=3
INFO  Scout scheduler started   active_schedules=3
INFO  Executing scheduled Scout run  schedule_id=... schedule_name="Daily Scout"
INFO  Scout run triggered       run_id=... source=stratninja max_strategies=20
```

### Error Messages

```
WARN  Failed to parse cron expression  schedule_id=... error="invalid format"
ERROR Failed to create Scout run  schedule_id=... error="database error"
ERROR Failed to publish scout trigger event  run_id=... error="connection closed"
```

## Python Agent Integration

The Python Scout agent should subscribe to `scout.trigger` events:

```python
# python-agents/src/freqsearch_agents/agents/scout/listener.py

import asyncio
from freqsearch_agents.grpc_client import FreqSearchClient
from freqsearch_agents.core.messaging import RabbitMQConsumer

async def handle_scout_trigger(message: dict):
    """Handle scout.trigger event from Go backend"""
    run_id = message['run_id']
    source = message['source']
    max_strategies = message['max_strategies']

    print(f"Scout run triggered: {run_id} (source={source}, max={max_strategies})")

    # Execute Scout agent
    scout = ScoutAgent(grpc_client=FreqSearchClient())

    try:
        # Update status to running
        await scout.grpc_client.update_scout_run_status(
            run_id, status='running'
        )

        # Discover strategies
        strategies = await scout.discover_strategies(source, max_strategies)

        # Complete run with metrics
        await scout.grpc_client.complete_scout_run(
            run_id,
            metrics={
                'total_fetched': len(strategies),
                'validated': len([s for s in strategies if s.is_valid]),
                'submitted': len([s for s in strategies if s.submitted]),
            }
        )
    except Exception as e:
        # Fail run
        await scout.grpc_client.fail_scout_run(run_id, str(e))
        raise

# Start consumer
consumer = RabbitMQConsumer(
    queue_name='scout_trigger_queue',
    routing_key='scout.trigger',
    callback=handle_scout_trigger
)

asyncio.run(consumer.start())
```
