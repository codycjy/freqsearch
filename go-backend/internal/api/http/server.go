// Package http provides HTTP server for health checks, metrics, REST API, and WebSocket.
package http

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/db"
	"github.com/saltfish/freqsearch/go-backend/internal/db/repository"
	"github.com/saltfish/freqsearch/go-backend/internal/events"
	"github.com/saltfish/freqsearch/go-backend/internal/scheduler"
)

// Server provides HTTP endpoints for health checks, metrics, REST API, and WebSocket.
type Server struct {
	server     *http.Server
	pool       *db.Pool
	scheduler  *scheduler.Scheduler
	logger     *zap.Logger
	handler    *Handler
	wsHub      *Hub
	subscriber events.Subscriber
	agentStore *AgentStore
}

// NewServer creates a new HTTP server.
func NewServer(
	address string,
	pool *db.Pool,
	repos *repository.Repositories,
	sched *scheduler.Scheduler,
	logger *zap.Logger,
) *Server {
	agentStore := NewAgentStore(60 * time.Second) // 60 second timeout for offline detection

	s := &Server{
		pool:       pool,
		scheduler:  sched,
		logger:     logger,
		handler:    NewHandler(repos, agentStore, logger),
		wsHub:      NewHub(logger),
		agentStore: agentStore,
	}

	mux := http.NewServeMux()

	// Health and metrics endpoints
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/health/live", s.handleLiveness)
	mux.HandleFunc("/health/ready", s.handleReadiness)
	mux.HandleFunc("/metrics", s.handleMetrics)

	// REST API endpoints
	s.setupAPIRoutes(mux)

	// WebSocket endpoint
	mux.HandleFunc("/api/v1/ws/events", func(w http.ResponseWriter, r *http.Request) {
		s.wsHub.ServeWS(w, r, logger)
	})

	// Wrap with CORS middleware
	handler := corsMiddleware(mux)

	s.server = &http.Server{
		Addr:         address,
		Handler:      handler,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	return s
}

// SetSubscriber sets the RabbitMQ subscriber for the server.
func (s *Server) SetSubscriber(subscriber events.Subscriber) {
	s.subscriber = subscriber
}

// setupAPIRoutes configures REST API routes.
func (s *Server) setupAPIRoutes(mux *http.ServeMux) {
	// Strategy endpoints
	mux.HandleFunc("/api/v1/strategies", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			s.handler.HandleSearchStrategies(w, r)
		case http.MethodPost:
			s.handler.HandleCreateStrategy(w, r)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})

	// Strategy by ID endpoints - need custom routing
	mux.HandleFunc("/api/v1/strategies/", func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path

		// Check for /lineage suffix
		if strings.HasSuffix(path, "/lineage") {
			s.handler.HandleGetStrategyLineage(w, r)
			return
		}

		// Check if it's a specific ID (has more than just "/api/v1/strategies/")
		if strings.TrimPrefix(path, "/api/v1/strategies/") != "" {
			switch r.Method {
			case http.MethodGet:
				s.handler.HandleGetStrategy(w, r)
			case http.MethodDelete:
				s.handler.HandleDeleteStrategy(w, r)
			default:
				http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			}
			return
		}

		// If we get here, it's the collection endpoint
		switch r.Method {
		case http.MethodGet:
			s.handler.HandleSearchStrategies(w, r)
		case http.MethodPost:
			s.handler.HandleCreateStrategy(w, r)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})

	// Backtest endpoints
	mux.HandleFunc("/api/v1/backtests", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			s.handler.HandleQueryBacktestResults(w, r)
		case http.MethodPost:
			s.handler.HandleSubmitBacktest(w, r)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})

	mux.HandleFunc("/api/v1/backtests/", func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path

		// Check for /queue/stats endpoint
		if strings.HasSuffix(path, "/queue/stats") {
			s.handler.HandleGetQueueStats(w, r)
			return
		}

		// Check if it's a specific ID
		if strings.TrimPrefix(path, "/api/v1/backtests/") != "" {
			switch r.Method {
			case http.MethodGet:
				s.handler.HandleGetBacktestJob(w, r)
			case http.MethodDelete:
				s.handler.HandleCancelBacktest(w, r)
			default:
				http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			}
			return
		}

		// Collection endpoint
		switch r.Method {
		case http.MethodGet:
			s.handler.HandleQueryBacktestResults(w, r)
		case http.MethodPost:
			s.handler.HandleSubmitBacktest(w, r)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})

	mux.HandleFunc("/api/v1/backtests/queue/stats", func(w http.ResponseWriter, r *http.Request) {
		s.handler.HandleGetQueueStats(w, r)
	})

	// Optimization endpoints
	mux.HandleFunc("/api/v1/optimizations", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			s.handler.HandleListOptimizationRuns(w, r)
		case http.MethodPost:
			s.handler.HandleStartOptimization(w, r)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})

	// Optimization performance endpoint - must be before the generic /optimizations/ handler
	mux.HandleFunc("/api/v1/optimizations/performance", func(w http.ResponseWriter, r *http.Request) {
		s.handler.HandleGetOptimizationPerformance(w, r)
	})

	mux.HandleFunc("/api/v1/optimizations/", func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path

		// Check for /control suffix
		if strings.HasSuffix(path, "/control") {
			s.handler.HandleControlOptimization(w, r)
			return
		}

		// Check if it's a specific ID
		if strings.TrimPrefix(path, "/api/v1/optimizations/") != "" {
			switch r.Method {
			case http.MethodGet:
				s.handler.HandleGetOptimizationRun(w, r)
			default:
				http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			}
			return
		}

		// Collection endpoint
		switch r.Method {
		case http.MethodGet:
			s.handler.HandleListOptimizationRuns(w, r)
		case http.MethodPost:
			s.handler.HandleStartOptimization(w, r)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})

	// Agent status endpoint
	mux.HandleFunc("/api/v1/agents/status", func(w http.ResponseWriter, r *http.Request) {
		s.handler.HandleGetAgentStatus(w, r)
	})

	// Scout endpoints
	mux.HandleFunc("/api/v1/agents/scout/trigger", func(w http.ResponseWriter, r *http.Request) {
		s.handler.HandleTriggerScout(w, r)
	})

	mux.HandleFunc("/api/v1/agents/scout/runs", func(w http.ResponseWriter, r *http.Request) {
		s.handler.HandleListScoutRuns(w, r)
	})

	mux.HandleFunc("/api/v1/agents/scout/runs/", func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path

		// Check if it's a specific ID
		if strings.TrimPrefix(path, "/api/v1/agents/scout/runs/") != "" {
			switch r.Method {
			case http.MethodGet:
				s.handler.HandleGetScoutRun(w, r)
			case http.MethodDelete:
				s.handler.HandleCancelScoutRun(w, r)
			default:
				http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			}
			return
		}

		// Collection endpoint
		s.handler.HandleListScoutRuns(w, r)
	})

	mux.HandleFunc("/api/v1/agents/scout/schedules", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			s.handler.HandleListScoutSchedules(w, r)
		case http.MethodPost:
			s.handler.HandleCreateScoutSchedule(w, r)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})

	mux.HandleFunc("/api/v1/agents/scout/schedules/", func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path

		// Check for /toggle suffix
		if strings.HasSuffix(path, "/toggle") {
			s.handler.HandleToggleScoutSchedule(w, r)
			return
		}

		// Check if it's a specific ID
		if strings.TrimPrefix(path, "/api/v1/agents/scout/schedules/") != "" {
			switch r.Method {
			case http.MethodGet:
				s.handler.HandleGetScoutSchedule(w, r)
			case http.MethodPut:
				s.handler.HandleUpdateScoutSchedule(w, r)
			case http.MethodDelete:
				s.handler.HandleDeleteScoutSchedule(w, r)
			default:
				http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			}
			return
		}

		// Collection endpoint
		switch r.Method {
		case http.MethodGet:
			s.handler.HandleListScoutSchedules(w, r)
		case http.MethodPost:
			s.handler.HandleCreateScoutSchedule(w, r)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// corsMiddleware adds CORS headers for frontend access.
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Allow requests from any origin (configure more restrictively in production)
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		w.Header().Set("Access-Control-Max-Age", "3600")

		// Handle preflight OPTIONS request
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// Start starts the HTTP server and WebSocket hub.
func (s *Server) Start() error {
	// Start WebSocket hub
	go s.wsHub.Run()

	// Start RabbitMQ subscriber if configured
	if s.subscriber != nil {
		s.startEventSubscription()
	}

	s.logger.Info("HTTP server starting", zap.String("address", s.server.Addr))
	return s.server.ListenAndServe()
}

// Stop gracefully stops the HTTP server, WebSocket hub, and subscriber.
func (s *Server) Stop(ctx context.Context) error {
	s.logger.Info("HTTP server stopping")

	// Stop subscriber
	if s.subscriber != nil {
		if err := s.subscriber.Close(); err != nil {
			s.logger.Error("Failed to close subscriber", zap.Error(err))
		}
	}

	// Stop WebSocket hub
	s.wsHub.Shutdown()

	return s.server.Shutdown(ctx)
}

// startEventSubscription starts subscribing to RabbitMQ events.
func (s *Server) startEventSubscription() {
	// Define routing keys to subscribe to
	routingKeys := []string{
		events.RoutingKeyTaskRunning,
		events.RoutingKeyTaskCompleted,
		events.RoutingKeyTaskFailed,
		events.RoutingKeyTaskCancelled,
		events.RoutingKeyOptIteration,
		events.RoutingKeyBacktestCompleted,
		events.RoutingKeyBacktestFailed,
		events.RoutingKeyStrategyDiscovered,
		events.RoutingKeyStrategyNeedsProcessing,
		events.RoutingKeyStrategyReadyForBacktest,
		events.RoutingKeyStrategyApproved,
		events.RoutingKeyStrategyEvolve,
		events.RoutingKeyStrategyArchived,
		events.RoutingKeyAgentHeartbeat,
		events.RoutingKeyScoutTrigger,
		events.RoutingKeyScoutStarted,
		events.RoutingKeyScoutProgress,
		events.RoutingKeyScoutCompleted,
		events.RoutingKeyScoutFailed,
		events.RoutingKeyScoutCancelled,
	}

	// Start subscription
	go func() {
		err := s.subscriber.Subscribe(context.Background(), routingKeys, s.handleRabbitMQEvent)
		if err != nil {
			s.logger.Error("Failed to start event subscription", zap.Error(err))
		}
	}()

	s.logger.Info("Started event subscription", zap.Strings("routing_keys", routingKeys))
}

// handleRabbitMQEvent handles events received from RabbitMQ and broadcasts to WebSocket clients.
func (s *Server) handleRabbitMQEvent(routingKey string, body []byte) error {
	s.logger.Debug("Received RabbitMQ event",
		zap.String("routing_key", routingKey),
		zap.Int("body_size", len(body)),
	)

	// Handle agent heartbeat events specially
	if routingKey == events.RoutingKeyAgentHeartbeat {
		return s.handleAgentHeartbeat(body)
	}

	// Map RabbitMQ routing key to WebSocket event type
	eventType := mapRoutingKeyToEventType(routingKey)

	// Parse the event body
	var eventData interface{}
	if err := json.Unmarshal(body, &eventData); err != nil {
		return err
	}

	// Broadcast to WebSocket clients
	s.wsHub.BroadcastEvent(eventType, eventData)

	return nil
}

// handleAgentHeartbeat processes agent heartbeat events.
func (s *Server) handleAgentHeartbeat(body []byte) error {
	var payload AgentHeartbeatPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		return err
	}

	// Update the agent store
	s.agentStore.UpdateHeartbeat(payload.AgentType, payload.Status, payload.CurrentTask)

	s.logger.Debug("Updated agent heartbeat",
		zap.String("agent_type", payload.AgentType),
		zap.String("status", payload.Status),
	)

	// Broadcast agent status update to WebSocket clients
	s.wsHub.BroadcastEvent(EventTypeAgentStatusUpdate, s.agentStore.GetAll())

	return nil
}

// mapRoutingKeyToEventType maps RabbitMQ routing keys to WebSocket event types.
func mapRoutingKeyToEventType(routingKey string) string {
	switch routingKey {
	case events.RoutingKeyTaskRunning:
		return EventTypeBacktestSubmitted
	case events.RoutingKeyTaskCompleted:
		return EventTypeBacktestCompleted
	case events.RoutingKeyTaskFailed:
		return EventTypeBacktestFailed
	case events.RoutingKeyOptIteration:
		return EventTypeOptIterationCompleted
	case events.RoutingKeyBacktestCompleted:
		return EventTypeBacktestCompleted
	case events.RoutingKeyBacktestFailed:
		return EventTypeBacktestFailed
	default:
		// For other events, use the routing key as is
		return routingKey
	}
}

// GetHub returns the WebSocket hub (useful for broadcasting events from other parts of the app).
func (s *Server) GetHub() *Hub {
	return s.wsHub
}

// HealthResponse represents the health check response.
type HealthResponse struct {
	Status   string            `json:"status"`
	Version  string            `json:"version"`
	Services map[string]string `json:"services"`
}

// handleHealth handles the /health endpoint.
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	response := HealthResponse{
		Status:   "healthy",
		Version:  "1.0.0",
		Services: make(map[string]string),
	}

	// Check PostgreSQL
	if err := s.pool.Ping(ctx); err != nil {
		response.Services["postgres"] = "unhealthy: " + err.Error()
		response.Status = "unhealthy"
	} else {
		response.Services["postgres"] = "healthy"
	}

	// Scheduler is always "healthy" if it exists
	if s.scheduler != nil {
		response.Services["scheduler"] = "healthy"
	} else {
		response.Services["scheduler"] = "not configured"
	}

	w.Header().Set("Content-Type", "application/json")
	if response.Status == "unhealthy" {
		w.WriteHeader(http.StatusServiceUnavailable)
	}
	json.NewEncoder(w).Encode(response)
}

// handleLiveness handles the /health/live endpoint (Kubernetes liveness probe).
func (s *Server) handleLiveness(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "alive"})
}

// handleReadiness handles the /health/ready endpoint (Kubernetes readiness probe).
func (s *Server) handleReadiness(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	// Check if we can connect to the database
	if err := s.pool.Ping(ctx); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(map[string]string{
			"status": "not ready",
			"reason": "database unavailable: " + err.Error(),
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ready"})
}

// MetricsResponse represents the metrics response.
type MetricsResponse struct {
	Scheduler SchedulerMetrics `json:"scheduler"`
	Database  DatabaseMetrics  `json:"database"`
	WebSocket WebSocketMetrics `json:"websocket"`
}

// SchedulerMetrics represents scheduler-related metrics.
type SchedulerMetrics struct {
	ActiveJobs     int   `json:"active_jobs"`
	QueueLength    int   `json:"queue_length"`
	WorkerCount    int   `json:"worker_count"`
	PendingJobs    int   `json:"pending_jobs"`
	RunningJobs    int   `json:"running_jobs"`
	CompletedToday int   `json:"completed_today"`
	FailedToday    int   `json:"failed_today"`
	AvgWaitTimeMs  int64 `json:"avg_wait_time_ms"`
	AvgRunTimeMs   int64 `json:"avg_run_time_ms"`
}

// DatabaseMetrics represents database-related metrics.
type DatabaseMetrics struct {
	TotalConnections  int32 `json:"total_connections"`
	AcquiredConns     int32 `json:"acquired_connections"`
	IdleConns         int32 `json:"idle_connections"`
	MaxConns          int32 `json:"max_connections"`
	ConstructingConns int32 `json:"constructing_connections"`
}

// WebSocketMetrics represents WebSocket-related metrics.
type WebSocketMetrics struct {
	ConnectedClients int `json:"connected_clients"`
}

// handleMetrics handles the /metrics endpoint.
func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	response := MetricsResponse{}

	// Get scheduler stats
	if s.scheduler != nil {
		stats := s.scheduler.GetStats()

		response.Scheduler = SchedulerMetrics{
			ActiveJobs:  getInt(stats, "active_jobs"),
			QueueLength: getInt(stats, "queue_length"),
			WorkerCount: getInt(stats, "worker_count"),
		}

		if pending, ok := stats["pending_jobs"]; ok {
			response.Scheduler.PendingJobs = getInt(stats, "pending_jobs")
			_ = pending // silence unused warning
		}
		if running, ok := stats["running_jobs"]; ok {
			response.Scheduler.RunningJobs = getInt(stats, "running_jobs")
			_ = running
		}
		if completed, ok := stats["completed_today"]; ok {
			response.Scheduler.CompletedToday = getInt(stats, "completed_today")
			_ = completed
		}
		if failed, ok := stats["failed_today"]; ok {
			response.Scheduler.FailedToday = getInt(stats, "failed_today")
			_ = failed
		}
		if avgWait, ok := stats["avg_wait_time_ms"]; ok {
			if v, ok := avgWait.(int64); ok {
				response.Scheduler.AvgWaitTimeMs = v
			}
		}
		if avgRun, ok := stats["avg_run_time_ms"]; ok {
			if v, ok := avgRun.(int64); ok {
				response.Scheduler.AvgRunTimeMs = v
			}
		}
	}

	// Get database pool stats
	poolStats := s.pool.Stat()
	response.Database = DatabaseMetrics{
		TotalConnections:  poolStats.TotalConns(),
		AcquiredConns:     poolStats.AcquiredConns(),
		IdleConns:         poolStats.IdleConns(),
		MaxConns:          poolStats.MaxConns(),
		ConstructingConns: poolStats.ConstructingConns(),
	}

	// Get WebSocket stats
	response.WebSocket = WebSocketMetrics{
		ConnectedClients: s.wsHub.GetClientCount(),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// getInt safely extracts an int from a map.
func getInt(m map[string]interface{}, key string) int {
	if v, ok := m[key]; ok {
		switch val := v.(type) {
		case int:
			return val
		case int32:
			return int(val)
		case int64:
			return int(val)
		}
	}
	return 0
}
