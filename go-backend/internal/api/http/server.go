// Package http provides HTTP server for health checks and metrics.
package http

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/db"
	"github.com/saltfish/freqsearch/go-backend/internal/scheduler"
)

// Server provides HTTP endpoints for health checks and metrics.
type Server struct {
	server    *http.Server
	pool      *db.Pool
	scheduler *scheduler.Scheduler
	logger    *zap.Logger
}

// NewServer creates a new HTTP server.
func NewServer(
	address string,
	pool *db.Pool,
	sched *scheduler.Scheduler,
	logger *zap.Logger,
) *Server {
	s := &Server{
		pool:      pool,
		scheduler: sched,
		logger:    logger,
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/health/live", s.handleLiveness)
	mux.HandleFunc("/health/ready", s.handleReadiness)
	mux.HandleFunc("/metrics", s.handleMetrics)

	s.server = &http.Server{
		Addr:         address,
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	return s
}

// Start starts the HTTP server.
func (s *Server) Start() error {
	s.logger.Info("HTTP server starting", zap.String("address", s.server.Addr))
	return s.server.ListenAndServe()
}

// Stop gracefully stops the HTTP server.
func (s *Server) Stop(ctx context.Context) error {
	s.logger.Info("HTTP server stopping")
	return s.server.Shutdown(ctx)
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
