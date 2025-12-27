# Scout Scheduler

The Scout Scheduler manages cron-based automatic Scout runs for strategy discovery.

## Overview

The `ScoutScheduler` polls the database for active Scout schedules and executes them according to their cron expressions. When a schedule is due, it creates a new Scout run and publishes a `scout.trigger` event to RabbitMQ for the Python agents to consume.

## Architecture

```
┌─────────────────────┐
│  ScoutScheduler     │
│                     │
│  - Poll every 30s   │
│  - Check schedules  │
│  - Execute due runs │
└──────────┬──────────┘
           │
           ├──► PostgreSQL (scout_schedules, scout_runs)
           │
           └──► RabbitMQ (scout.trigger events)
```

## Key Features

- **Cron-based scheduling**: Supports standard 5-field cron expressions (minute, hour, day, month, weekday)
- **Automatic next-run calculation**: Automatically calculates and updates next run times
- **Event-driven**: Publishes `scout.trigger` events for Python agents to consume
- **Graceful shutdown**: Properly cancels context and waits for goroutines
- **Error resilient**: Continues running even if individual schedules fail
- **Thread-safe**: Uses mutex locks for concurrent access to schedule map

## Usage

### Basic Setup

```go
import (
    "github.com/saltfish/freqsearch/go-backend/internal/scheduler"
    "github.com/saltfish/freqsearch/go-backend/internal/db/repository"
    "github.com/saltfish/freqsearch/go-backend/internal/events"
    "go.uber.org/zap"
)

// Create scheduler
scoutScheduler := scheduler.NewScoutScheduler(
    repos,          // *repository.Repositories
    eventPublisher, // events.Publisher
    logger,         // *zap.Logger
)

// Start scheduler
if err := scoutScheduler.Start(); err != nil {
    log.Fatal("Failed to start Scout scheduler:", err)
}

// Stop scheduler on shutdown
defer scoutScheduler.Stop()
```

### Reload Schedules

To reload schedules from the database without restarting:

```go
if err := scoutScheduler.ReloadSchedules(); err != nil {
    logger.Error("Failed to reload schedules", zap.Error(err))
}
```

This is useful when:
- A new schedule is created via the API
- An existing schedule is updated
- A schedule is enabled/disabled

## Cron Expression Format

The scheduler uses standard 5-field cron expressions:

```
 ┌───────────── minute (0 - 59)
 │ ┌───────────── hour (0 - 23)
 │ │ ┌───────────── day of month (1 - 31)
 │ │ │ ┌───────────── month (1 - 12)
 │ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
 │ │ │ │ │
 * * * * *
```

### Examples

| Expression | Description |
|------------|-------------|
| `*/5 * * * *` | Every 5 minutes |
| `0 * * * *` | Every hour at minute 0 |
| `0 0 * * *` | Daily at midnight |
| `0 0 * * 0` | Weekly on Sunday at midnight |
| `0 0 1 * *` | Monthly on the 1st at midnight |
| `0 9,17 * * 1-5` | Weekdays at 9 AM and 5 PM |

## Database Schema

### scout_schedules

Stores schedule configurations:

```sql
CREATE TABLE scout_schedules (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    cron_expression VARCHAR(255) NOT NULL,
    source VARCHAR(255) NOT NULL,  -- 'stratninja', 'github', etc.
    max_strategies INT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    last_run_id UUID REFERENCES scout_runs(id),
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### scout_runs

Stores Scout run execution records:

```sql
CREATE TABLE scout_runs (
    id UUID PRIMARY KEY,
    trigger_type VARCHAR(50) NOT NULL,  -- 'scheduled', 'manual', 'event'
    triggered_by VARCHAR(255),
    source VARCHAR(255) NOT NULL,
    max_strategies INT NOT NULL,
    status VARCHAR(50) NOT NULL,  -- 'pending', 'running', 'completed', 'failed'
    error_message TEXT,
    metrics JSONB,
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

## Event Flow

When a schedule is due:

1. **Create Scout Run**
   ```go
   run := domain.NewScoutRun(
       domain.ScoutTriggerTypeScheduled,
       schedule.Name,
       schedule.Source,
       schedule.MaxStrategies,
   )
   ```

2. **Save to Database**
   ```go
   repos.Scout.CreateRun(ctx, run)
   ```

3. **Update Schedule**
   ```go
   repos.Scout.UpdateScheduleLastRun(ctx, schedule.ID, run.ID)
   repos.Scout.UpdateScheduleNextRun(ctx, schedule.ID, nextRunAt)
   ```

4. **Publish Event**
   ```go
   event := events.NewScoutTriggerEvent(run)
   publisher.PublishScoutTrigger(event)
   ```

The Python Scout agent listens for `scout.trigger` events and executes the strategy discovery process.

## Event Payload

The `scout.trigger` event contains:

```json
{
    "event_id": "uuid",
    "event_type": "scout.trigger",
    "timestamp": "2025-12-15T12:00:00Z",
    "source": "go-backend",
    "run_id": "uuid",
    "source": "stratninja",
    "max_strategies": 10,
    "trigger_type": "scheduled",
    "triggered_by": "Daily Scout Run"
}
```

## Implementation Details

### Poll Interval

The scheduler checks for due schedules every 30 seconds:

```go
pollInterval: 30 * time.Second
```

This can be adjusted in the constructor if needed.

### Concurrency

- Schedule checks are protected by `RWMutex`
- Individual schedule executions run in separate goroutines
- Uses WaitGroup for graceful shutdown

### Error Handling

- Invalid cron expressions are logged and skipped
- Database errors are logged but don't stop the scheduler
- Event publishing failures are logged but don't prevent run creation

## Example: Creating a Schedule

Via repository:

```go
schedule := domain.NewScoutSchedule(
    "Daily StratNinja Scout",  // name
    "0 0 * * *",               // cron: daily at midnight
    "stratninja",              // source
    20,                        // max strategies
)

if err := repos.Scout.CreateSchedule(ctx, schedule); err != nil {
    return err
}

// Reload scheduler to pick up new schedule
scoutScheduler.ReloadSchedules()
```

## Testing

The implementation includes comprehensive tests:

```bash
go test -v ./internal/scheduler -run TestScoutScheduler
```

Tests cover:
- Schedule loading and parsing
- Cron expression validation
- Schedule execution
- Next run calculation
- Start/stop lifecycle
- Concurrent safety

## Integration Points

### With Python Agents

The Python Scout agent subscribes to `scout.trigger` events:

```python
async def handle_scout_trigger(event: ScoutTriggerEvent):
    run_id = event['run_id']
    source = event['source']
    max_strategies = event['max_strategies']

    # Execute strategy discovery
    strategies = await scout.discover(source, max_strategies)

    # Update run status
    await update_scout_run(run_id, metrics={
        'total_fetched': len(strategies),
        'validated': validated_count,
        ...
    })
```

### With HTTP API

The HTTP API can trigger manual runs and manage schedules:

```go
// POST /api/scout/trigger
func TriggerScoutRun(c *gin.Context) {
    var req struct {
        Source        string `json:"source"`
        MaxStrategies int    `json:"max_strategies"`
    }

    run := domain.NewScoutRun(
        domain.ScoutTriggerTypeManual,
        "Manual trigger",
        req.Source,
        req.MaxStrategies,
    )

    repos.Scout.CreateRun(ctx, run)
    publisher.PublishScoutTrigger(events.NewScoutTriggerEvent(run))

    c.JSON(200, run)
}

// POST /api/scout/schedules/:id/reload
func ReloadSchedule(c *gin.Context) {
    if err := scoutScheduler.ReloadSchedules(); err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }
    c.JSON(200, gin.H{"message": "Schedules reloaded"})
}
```

## Best Practices

1. **Reload after changes**: Always call `ReloadSchedules()` after creating/updating schedules
2. **Monitor logs**: Watch for cron parsing errors and execution failures
3. **Set reasonable intervals**: Avoid schedules that run too frequently
4. **Handle duplicates**: Scout agent should handle duplicate strategies gracefully
5. **Graceful shutdown**: Always call `Stop()` during application shutdown

## Troubleshooting

### Schedule not executing

1. Check if schedule is enabled: `enabled = true`
2. Verify cron expression is valid
3. Check `next_run_at` timestamp in database
4. Review scheduler logs for parsing errors

### Missing events

1. Verify RabbitMQ connection is healthy
2. Check event publisher is not nil
3. Review RabbitMQ logs for routing issues

### Database errors

1. Ensure database migrations are applied
2. Verify foreign key constraints
3. Check connection pool health
