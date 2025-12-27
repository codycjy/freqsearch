# WebSocket Integration Example

This document shows how to integrate the WebSocket hub into the FreqSearch application.

## Main Server Setup

Update your `cmd/server/main.go` to include WebSocket support:

```go
package main

import (
    "context"
    "os"
    "os/signal"
    "syscall"
    "time"

    "go.uber.org/zap"

    "github.com/saltfish/freqsearch/go-backend/internal/api/grpc"
    "github.com/saltfish/freqsearch/go-backend/internal/api/http"
    "github.com/saltfish/freqsearch/go-backend/internal/config"
    "github.com/saltfish/freqsearch/go-backend/internal/db"
    "github.com/saltfish/freqsearch/go-backend/internal/db/repository"
    "github.com/saltfish/freqsearch/go-backend/internal/docker"
    "github.com/saltfish/freqsearch/go-backend/internal/events"
    "github.com/saltfish/freqsearch/go-backend/internal/scheduler"
)

func main() {
    // Initialize logger
    logger, _ := zap.NewProduction()
    defer logger.Sync()

    // Load configuration
    cfg, err := config.Load()
    if err != nil {
        logger.Fatal("Failed to load config", zap.Error(err))
    }

    // Initialize database
    pool, err := db.NewPool(context.Background(), &cfg.Database, logger)
    if err != nil {
        logger.Fatal("Failed to create database pool", zap.Error(err))
    }
    defer pool.Close()

    // Initialize repositories
    repos := repository.NewRepositories(pool)

    // Initialize Docker manager
    dockerMgr, err := docker.NewDockerManager(&cfg.Docker, logger)
    if err != nil {
        logger.Fatal("Failed to create Docker manager", zap.Error(err))
    }
    defer dockerMgr.Close()

    // Initialize RabbitMQ publisher
    publisher, err := events.NewRabbitMQPublisher(&cfg.RabbitMQ, logger)
    if err != nil {
        logger.Warn("Failed to create RabbitMQ publisher, using no-op", zap.Error(err))
        publisher = events.NewNoOpPublisher()
    }
    defer publisher.Close()

    // Initialize scheduler
    sched := scheduler.NewScheduler(
        repos.BacktestJob,
        repos.BacktestResult,
        dockerMgr,
        publisher,
        cfg.Scheduler.WorkerCount,
        logger,
    )

    // Start scheduler
    go sched.Start()
    defer sched.Stop()

    // Initialize HTTP server with WebSocket support
    httpServer := http.NewServer(
        cfg.HTTP.Address,
        pool,
        repos,
        sched,
        logger,
    )

    // Initialize RabbitMQ subscriber for WebSocket events
    subscriber, err := events.NewRabbitMQSubscriber(
        &cfg.RabbitMQ,
        "websocket_events_queue", // Queue name for WebSocket events
        logger,
    )
    if err != nil {
        logger.Warn("Failed to create RabbitMQ subscriber, WebSocket events will be limited", zap.Error(err))
    } else {
        httpServer.SetSubscriber(subscriber)
    }

    // Start HTTP server (includes WebSocket hub and RabbitMQ subscriber)
    go func() {
        if err := httpServer.Start(); err != nil {
            logger.Fatal("HTTP server failed", zap.Error(err))
        }
    }()

    // Initialize gRPC server
    grpcServer := grpc.NewServer(
        repos.Strategy,
        repos.BacktestJob,
        repos.BacktestResult,
        repos.OptimizationRun,
        repos.OptimizationIteration,
        sched,
        logger,
    )

    // Start gRPC server
    go func() {
        if err := grpcServer.Start(cfg.GRPC.Address); err != nil {
            logger.Fatal("gRPC server failed", zap.Error(err))
        }
    }()

    // Wait for interrupt signal
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
    <-sigChan

    logger.Info("Shutting down servers...")

    // Graceful shutdown
    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()

    // Stop HTTP server (includes WebSocket hub and RabbitMQ subscriber)
    if err := httpServer.Stop(ctx); err != nil {
        logger.Error("HTTP server shutdown error", zap.Error(err))
    }

    // Stop gRPC server
    grpcServer.Stop()

    logger.Info("Servers stopped successfully")
}
```

## Broadcasting Custom Events

You can broadcast custom events from anywhere in your application:

### From a Service Layer

```go
package service

import (
    "github.com/saltfish/freqsearch/go-backend/internal/api/http"
)

type OptimizationService struct {
    wsHub *http.Hub
    // ... other dependencies
}

func (s *OptimizationService) RunOptimization(ctx context.Context, strategyID string) error {
    // Start optimization
    s.wsHub.BroadcastEvent("optimization.iteration.started", map[string]interface{}{
        "strategy_id": strategyID,
        "timestamp": time.Now(),
    })

    // Run optimization logic...
    result := runOptimization(strategyID)

    // Broadcast completion
    s.wsHub.BroadcastEvent("optimization.iteration.completed", map[string]interface{}{
        "strategy_id": strategyID,
        "result": result,
        "timestamp": time.Now(),
    })

    return nil
}
```

### From the Scheduler

```go
package scheduler

import (
    "github.com/saltfish/freqsearch/go-backend/internal/api/http"
)

type Scheduler struct {
    wsHub *http.Hub
    // ... other fields
}

func (s *Scheduler) executeJob(job *domain.BacktestJob) {
    // Notify job started
    s.wsHub.BroadcastEvent("backtest.submitted", map[string]interface{}{
        "job_id": job.ID,
        "strategy_id": job.StrategyID,
        "status": "running",
    })

    // Execute job...
    result, err := s.dockerMgr.RunBacktest(job)

    if err != nil {
        // Notify job failed
        s.wsHub.BroadcastEvent("backtest.failed", map[string]interface{}{
            "job_id": job.ID,
            "error": err.Error(),
        })
    } else {
        // Notify job completed
        s.wsHub.BroadcastEvent("backtest.completed", map[string]interface{}{
            "job_id": job.ID,
            "result_id": result.ID,
            "profit_pct": result.ProfitPct,
        })
    }
}
```

## Configuration Example

Add WebSocket-specific configuration to your `config.yaml`:

```yaml
http:
  address: ":8080"
  cors_allowed_origins:
    - "http://localhost:3000"
    - "https://your-frontend.com"

websocket:
  max_clients: 1000
  ping_period: "54s"
  pong_timeout: "60s"
  write_timeout: "10s"
  max_message_size: 512

rabbitmq:
  url: "amqp://guest:guest@localhost:5672/"
  exchange: "freqsearch_events"
  reconnect_delay: "5s"
  max_reconnect_wait: "30s"
```

## Monitoring WebSocket Connections

Use the metrics endpoint to monitor WebSocket connections:

```bash
# Get current metrics
curl http://localhost:8080/metrics | jq '.websocket'

# Output:
{
  "connected_clients": 5
}
```

## Testing the WebSocket Connection

### Using wscat (Command Line)

```bash
# Install wscat
npm install -g wscat

# Connect to WebSocket
wscat -c ws://localhost:8080/api/v1/ws/events

# Subscribe to events
> {"action":"subscribe","event_types":["backtest.completed"]}

# Wait for events...
< {"type":"backtest.completed","data":{...},"timestamp":"2025-12-15T10:30:00Z"}
```

### Using cURL (HTTP Upgrade)

```bash
curl --include \
     --no-buffer \
     --header "Connection: Upgrade" \
     --header "Upgrade: websocket" \
     --header "Host: localhost:8080" \
     --header "Origin: http://localhost:8080" \
     --header "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" \
     --header "Sec-WebSocket-Version: 13" \
     http://localhost:8080/api/v1/ws/events
```

## Production Deployment

### Nginx Configuration

```nginx
upstream backend {
    server localhost:8080;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket timeouts
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

### Docker Compose

```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8080:8080"
      - "50051:50051"
    environment:
      - HTTP_ADDRESS=:8080
      - GRPC_ADDRESS=:50051
      - RABBITMQ_URL=amqp://rabbitmq:5672/
    depends_on:
      - postgres
      - rabbitmq

  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=freqsearch
      - POSTGRES_USER=freqsearch
      - POSTGRES_PASSWORD=password
    ports:
      - "5432:5432"
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: freqsearch-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: freqsearch-backend
  template:
    metadata:
      labels:
        app: freqsearch-backend
    spec:
      containers:
      - name: backend
        image: freqsearch-backend:latest
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 50051
          name: grpc
        env:
        - name: HTTP_ADDRESS
          value: ":8080"
        - name: RABBITMQ_URL
          valueFrom:
            secretKeyRef:
              name: rabbitmq-credentials
              key: url
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: freqsearch-backend
spec:
  type: LoadBalancer
  selector:
    app: freqsearch-backend
  ports:
  - name: http
    port: 80
    targetPort: 8080
  - name: grpc
    port: 50051
    targetPort: 50051
```

## Performance Tuning

### Increase Connection Limits

```go
// In websocket.go, adjust constants:
const (
    sendBufferSize = 512  // Increase for high-frequency events
    maxMessageSize = 1024 // Increase if clients send larger messages
)
```

### Optimize RabbitMQ Consumer

```go
// In subscriber.go, adjust QoS:
err = s.channel.Qos(
    100,   // Increase prefetch count for higher throughput
    0,     // prefetch size
    false, // global
)
```

### Load Balancing

For horizontal scaling, use sticky sessions or consider using Redis as a pub/sub backend instead of in-memory hub.

## Troubleshooting

### Connection Refused

```bash
# Check if server is running
curl http://localhost:8080/health

# Check WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
     http://localhost:8080/api/v1/ws/events
```

### No Events Received

```bash
# Check RabbitMQ status
docker exec -it rabbitmq rabbitmqctl list_exchanges
docker exec -it rabbitmq rabbitmqctl list_queues
docker exec -it rabbitmq rabbitmqctl list_bindings

# Check server logs
docker logs freqsearch-backend | grep -i websocket
```

### High Memory Usage

Monitor client connections and implement connection limits:

```go
// Add to Hub struct
maxClients int

// Check in register handler
if len(h.clients) >= h.maxClients {
    logger.Warn("Max clients reached, rejecting connection")
    return
}
```
