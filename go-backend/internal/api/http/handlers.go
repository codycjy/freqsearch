package http

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/db/repository"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
	"github.com/saltfish/freqsearch/go-backend/internal/events"
)

// Handler provides REST API handlers.
type Handler struct {
	repos          *repository.Repositories
	agentStore     *AgentStore
	eventPublisher events.Publisher
	scoutScheduler ScoutSchedulerInterface
	logger         *zap.Logger
}

// ScoutSchedulerInterface defines the interface for Scout scheduler operations.
type ScoutSchedulerInterface interface {
	ReloadSchedules() error
}

// NewHandler creates a new Handler instance.
func NewHandler(repos *repository.Repositories, agentStore *AgentStore, logger *zap.Logger) *Handler {
	return &Handler{
		repos:      repos,
		agentStore: agentStore,
		logger:     logger,
	}
}

// SetEventPublisher sets the event publisher for the handler.
func (h *Handler) SetEventPublisher(publisher events.Publisher) {
	h.eventPublisher = publisher
}

// SetScoutScheduler sets the scout scheduler for the handler.
func (h *Handler) SetScoutScheduler(scheduler ScoutSchedulerInterface) {
	h.scoutScheduler = scheduler
}

// Error response structure
type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message,omitempty"`
}

// writeJSON writes a JSON response.
func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(data); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

// writeError writes an error response.
func writeError(w http.ResponseWriter, status int, err error, message string) {
	writeJSON(w, status, ErrorResponse{
		Error:   err.Error(),
		Message: message,
	})
}

// parseUUID parses UUID from string.
func parseUUID(s string) (uuid.UUID, error) {
	if s == "" {
		return uuid.Nil, errors.New("empty UUID")
	}
	return uuid.Parse(s)
}

// extractID extracts the ID from the URL path.
// Expected format: /api/v1/resource/:id or /api/v1/resource/:id/action
func extractID(path, prefix string) string {
	// Remove prefix and split by '/'
	path = strings.TrimPrefix(path, prefix)
	path = strings.Trim(path, "/")
	parts := strings.Split(path, "/")
	if len(parts) > 0 {
		return parts[0]
	}
	return ""
}

// ========================================
// Strategy Handlers
// ========================================

// CreateStrategyRequest represents the request body for creating a strategy.
type CreateStrategyRequest struct {
	Name        string  `json:"name"`
	Code        string  `json:"code"`
	Description string  `json:"description"`
	ParentID    *string `json:"parent_id,omitempty"`
}

// CreateStrategyResponse represents the response for creating a strategy.
type CreateStrategyResponse struct {
	Strategy *domain.Strategy `json:"strategy"`
}

// HandleCreateStrategy creates a new strategy.
func (h *Handler) HandleCreateStrategy(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	var req CreateStrategyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid request body")
		return
	}

	// Sanitize strategy name to ensure valid Python class name
	sanitizedName := domain.SanitizeStrategyName(req.Name)

	// Also fix class name in code if it doesn't match
	code := req.Code
	if sanitizedName != req.Name {
		code = strings.Replace(code, "class "+req.Name+"(", "class "+sanitizedName+"(", 1)
		h.logger.Info("Sanitized strategy name",
			zap.String("original", req.Name),
			zap.String("sanitized", sanitizedName),
		)
	}

	strategy := &domain.Strategy{
		ID:          uuid.New(),
		Name:        sanitizedName,
		Code:        code,
		Description: req.Description,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	if req.ParentID != nil && *req.ParentID != "" {
		parentID, err := parseUUID(*req.ParentID)
		if err != nil {
			writeError(w, http.StatusBadRequest, err, "invalid parent_id")
			return
		}
		strategy.ParentID = &parentID
	}

	if err := h.repos.Strategy.Create(r.Context(), strategy); err != nil {
		if errors.Is(err, domain.ErrDuplicate) {
			writeError(w, http.StatusConflict, err, "strategy with same code already exists")
			return
		}
		h.logger.Error("Failed to create strategy", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to create strategy")
		return
	}

	writeJSON(w, http.StatusCreated, CreateStrategyResponse{Strategy: strategy})
}

// GetStrategyResponse represents the response for getting a strategy.
type GetStrategyResponse struct {
	Strategy *domain.Strategy `json:"strategy"`
}

// HandleGetStrategy retrieves a strategy by ID.
func (h *Handler) HandleGetStrategy(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/strategies/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid strategy id")
		return
	}

	strategy, err := h.repos.Strategy.GetByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "strategy not found")
			return
		}
		h.logger.Error("Failed to get strategy", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get strategy")
		return
	}

	writeJSON(w, http.StatusOK, GetStrategyResponse{Strategy: strategy})
}

// UpdateStrategyRequest represents the request body for updating a strategy.
type UpdateStrategyRequest struct {
	Name        string  `json:"name"`
	Code        string  `json:"code"`
	Description string  `json:"description"`
	ParentID    *string `json:"parent_id,omitempty"`
}

// HandleUpdateStrategy updates an existing strategy.
func (h *Handler) HandleUpdateStrategy(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/strategies/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid strategy id")
		return
	}

	var req UpdateStrategyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid request body")
		return
	}

	// Get existing strategy
	strategy, err := h.repos.Strategy.GetByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "strategy not found")
			return
		}
		h.logger.Error("Failed to get strategy", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get strategy")
		return
	}

	// Sanitize strategy name
	sanitizedName := domain.SanitizeStrategyName(req.Name)

	// Update code class name if needed
	code := req.Code
	if sanitizedName != req.Name {
		code = strings.Replace(code, "class "+req.Name+"(", "class "+sanitizedName+"(", 1)
		h.logger.Info("Sanitized strategy name",
			zap.String("original", req.Name),
			zap.String("sanitized", sanitizedName),
		)
	}

	// Update strategy fields
	strategy.Name = sanitizedName
	strategy.Code = code
	strategy.Description = req.Description
	strategy.UpdatedAt = time.Now()

	if req.ParentID != nil && *req.ParentID != "" {
		parentID, err := parseUUID(*req.ParentID)
		if err != nil {
			writeError(w, http.StatusBadRequest, err, "invalid parent_id")
			return
		}
		strategy.ParentID = &parentID
	} else {
		strategy.ParentID = nil
	}

	if err := h.repos.Strategy.Update(r.Context(), strategy); err != nil {
		h.logger.Error("Failed to update strategy", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to update strategy")
		return
	}

	writeJSON(w, http.StatusOK, GetStrategyResponse{Strategy: strategy})
}

// HandleDeleteStrategy deletes a strategy by ID.
func (h *Handler) HandleDeleteStrategy(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/strategies/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid strategy id")
		return
	}

	if err := h.repos.Strategy.Delete(r.Context(), id); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "strategy not found")
			return
		}
		if errors.Is(err, domain.ErrStrategyInUse) {
			writeError(w, http.StatusConflict, err, "strategy is in use")
			return
		}
		h.logger.Error("Failed to delete strategy", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to delete strategy")
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// SearchStrategiesResponse represents the response for searching strategies.
type SearchStrategiesResponse struct {
	Strategies []domain.StrategyWithMetrics  `json:"strategies"`
	Pagination domain.PaginationResponse `json:"pagination"`
}

// HandleSearchStrategies searches for strategies with filters.
func (h *Handler) HandleSearchStrategies(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	query := domain.StrategySearchQuery{
		Page:     1,
		PageSize: 20,
	}

	// Parse query parameters
	queryParams := r.URL.Query()
	if namePattern := queryParams.Get("name_pattern"); namePattern != "" {
		query.NamePattern = &namePattern
	}
	if minSharpe := queryParams.Get("min_sharpe"); minSharpe != "" {
		if val, err := strconv.ParseFloat(minSharpe, 64); err == nil {
			query.MinSharpe = &val
		}
	}
	if minProfit := queryParams.Get("min_profit_pct"); minProfit != "" {
		if val, err := strconv.ParseFloat(minProfit, 64); err == nil {
			query.MinProfitPct = &val
		}
	}
	if maxDrawdown := queryParams.Get("max_drawdown_pct"); maxDrawdown != "" {
		if val, err := strconv.ParseFloat(maxDrawdown, 64); err == nil {
			query.MaxDrawdownPct = &val
		}
	}
	if minTrades := queryParams.Get("min_trades"); minTrades != "" {
		if val, err := strconv.Atoi(minTrades); err == nil {
			query.MinTrades = &val
		}
	}
	if orderBy := queryParams.Get("order_by"); orderBy != "" {
		query.OrderBy = orderBy
	}
	if ascending := queryParams.Get("ascending"); ascending == "true" {
		query.Ascending = true
	}
	if page := queryParams.Get("page"); page != "" {
		if val, err := strconv.Atoi(page); err == nil {
			query.Page = val
		}
	}
	if pageSize := queryParams.Get("page_size"); pageSize != "" {
		if val, err := strconv.Atoi(pageSize); err == nil {
			query.PageSize = val
		}
	}

	query.SetDefaults()

	strategies, totalCount, err := h.repos.Strategy.Search(r.Context(), query)
	if err != nil {
		h.logger.Error("Failed to search strategies", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to search strategies")
		return
	}

	pagination := domain.NewPaginationResponse(totalCount, query.Page, query.PageSize)

	writeJSON(w, http.StatusOK, SearchStrategiesResponse{
		Strategies: strategies,
		Pagination: pagination,
	})
}

// GetStrategyLineageResponse represents the response for getting strategy lineage.
type GetStrategyLineageResponse struct {
	Lineage *domain.StrategyLineageNode `json:"lineage"`
}

// HandleGetStrategyLineage retrieves the strategy lineage tree.
func (h *Handler) HandleGetStrategyLineage(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	// Extract ID from path like /api/v1/strategies/:id/lineage
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/strategies/")
	path = strings.TrimSuffix(path, "/lineage")
	idStr := path

	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid strategy id")
		return
	}

	// Parse depth parameter
	depth := 2 // default depth
	if depthStr := r.URL.Query().Get("depth"); depthStr != "" {
		if val, err := strconv.Atoi(depthStr); err == nil && val > 0 {
			depth = val
		}
	}

	lineage, err := h.repos.Strategy.GetLineage(r.Context(), id, depth)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "strategy not found")
			return
		}
		h.logger.Error("Failed to get strategy lineage", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get lineage")
		return
	}

	writeJSON(w, http.StatusOK, GetStrategyLineageResponse{Lineage: lineage})
}

// ========================================
// Backtest Handlers
// ========================================

// SubmitBacktestRequest represents the request body for submitting a backtest.
type SubmitBacktestRequest struct {
	StrategyID        string                `json:"strategy_id"`
	Config            domain.BacktestConfig `json:"config"`
	Priority          int                   `json:"priority"`
	OptimizationRunID *string               `json:"optimization_run_id,omitempty"`
}

// SubmitBacktestResponse represents the response for submitting a backtest.
type SubmitBacktestResponse struct {
	Job *domain.BacktestJob `json:"job"`
}

// HandleSubmitBacktest submits a backtest job.
func (h *Handler) HandleSubmitBacktest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	var req SubmitBacktestRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid request body")
		return
	}

	strategyID, err := parseUUID(req.StrategyID)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid strategy_id")
		return
	}

	var optRunID *uuid.UUID
	if req.OptimizationRunID != nil && *req.OptimizationRunID != "" {
		id, err := parseUUID(*req.OptimizationRunID)
		if err != nil {
			writeError(w, http.StatusBadRequest, err, "invalid optimization_run_id")
			return
		}
		optRunID = &id
	}

	job := domain.NewBacktestJob(strategyID, req.Config, req.Priority, optRunID)

	if err := h.repos.BacktestJob.Create(r.Context(), job); err != nil {
		h.logger.Error("Failed to create backtest job", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to create job")
		return
	}

	writeJSON(w, http.StatusCreated, SubmitBacktestResponse{Job: job})
}

// GetBacktestJobResponse represents the response for getting a backtest job.
type GetBacktestJobResponse struct {
	Job    *domain.BacktestJob    `json:"job"`
	Result *domain.BacktestResult `json:"result,omitempty"`
}

// HandleGetBacktestJob retrieves a backtest job by ID.
func (h *Handler) HandleGetBacktestJob(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/backtests/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid job id")
		return
	}

	job, err := h.repos.BacktestJob.GetByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "job not found")
			return
		}
		h.logger.Error("Failed to get backtest job", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get job")
		return
	}

	response := GetBacktestJobResponse{Job: job}

	// If job is completed, also fetch the result
	if job.Status == domain.JobStatusCompleted {
		result, err := h.repos.Result.GetByJobID(r.Context(), id)
		if err != nil && !errors.Is(err, domain.ErrNotFound) {
			h.logger.Warn("Failed to get backtest result for completed job", zap.Error(err), zap.String("job_id", id.String()))
		}
		if result != nil {
			response.Result = result
		}
	}

	writeJSON(w, http.StatusOK, response)
}

// HandleCancelBacktest cancels a backtest job.
func (h *Handler) HandleCancelBacktest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/backtests/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid job id")
		return
	}

	if err := h.repos.BacktestJob.Cancel(r.Context(), id); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "job not found")
			return
		}
		if errors.Is(err, domain.ErrJobNotCancellable) {
			writeError(w, http.StatusConflict, err, "job cannot be cancelled")
			return
		}
		h.logger.Error("Failed to cancel backtest job", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to cancel job")
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// QueryBacktestResultsResponse represents the response for querying backtest results.
type QueryBacktestResultsResponse struct {
	Results    []*domain.BacktestResult  `json:"results"`
	Pagination domain.PaginationResponse `json:"pagination"`
}

// HandleQueryBacktestResults queries backtest results with filters.
func (h *Handler) HandleQueryBacktestResults(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	query := domain.BacktestResultQuery{
		Page:     1,
		PageSize: 20,
	}

	// Parse query parameters
	queryParams := r.URL.Query()
	if strategyID := queryParams.Get("strategy_id"); strategyID != "" {
		if id, err := parseUUID(strategyID); err == nil {
			query.StrategyID = &id
		}
	}
	if optRunID := queryParams.Get("optimization_run_id"); optRunID != "" {
		if id, err := parseUUID(optRunID); err == nil {
			query.OptimizationRunID = &id
		}
	}
	if minSharpe := queryParams.Get("min_sharpe"); minSharpe != "" {
		if val, err := strconv.ParseFloat(minSharpe, 64); err == nil {
			query.MinSharpe = &val
		}
	}
	if minProfit := queryParams.Get("min_profit_pct"); minProfit != "" {
		if val, err := strconv.ParseFloat(minProfit, 64); err == nil {
			query.MinProfitPct = &val
		}
	}
	if maxDrawdown := queryParams.Get("max_drawdown_pct"); maxDrawdown != "" {
		if val, err := strconv.ParseFloat(maxDrawdown, 64); err == nil {
			query.MaxDrawdownPct = &val
		}
	}
	if minTrades := queryParams.Get("min_trades"); minTrades != "" {
		if val, err := strconv.Atoi(minTrades); err == nil {
			query.MinTrades = &val
		}
	}
	if orderBy := queryParams.Get("order_by"); orderBy != "" {
		query.OrderBy = orderBy
	}
	if ascending := queryParams.Get("ascending"); ascending == "true" {
		query.Ascending = true
	}
	if page := queryParams.Get("page"); page != "" {
		if val, err := strconv.Atoi(page); err == nil {
			query.Page = val
		}
	}
	if pageSize := queryParams.Get("page_size"); pageSize != "" {
		if val, err := strconv.Atoi(pageSize); err == nil {
			query.PageSize = val
		}
	}

	// Parse time range if provided
	if startStr := queryParams.Get("start_time"); startStr != "" {
		if start, err := time.Parse(time.RFC3339, startStr); err == nil {
			if query.TimeRange == nil {
				query.TimeRange = &domain.TimeRange{}
			}
			query.TimeRange.Start = start
		}
	}
	if endStr := queryParams.Get("end_time"); endStr != "" {
		if end, err := time.Parse(time.RFC3339, endStr); err == nil {
			if query.TimeRange == nil {
				query.TimeRange = &domain.TimeRange{}
			}
			query.TimeRange.End = end
		}
	}

	query.SetDefaults()

	results, totalCount, err := h.repos.Result.Query(r.Context(), query)
	if err != nil {
		h.logger.Error("Failed to query backtest results", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to query results")
		return
	}

	pagination := domain.NewPaginationResponse(totalCount, query.Page, query.PageSize)

	writeJSON(w, http.StatusOK, QueryBacktestResultsResponse{
		Results:    results,
		Pagination: pagination,
	})
}

// ListBacktestJobsResponse represents the response for listing backtest jobs.
type ListBacktestJobsResponse struct {
	Backtests  []*domain.BacktestJob     `json:"backtests"`
	Pagination domain.PaginationResponse `json:"pagination"`
}

// HandleListBacktestJobs lists backtest jobs with filters and pagination.
func (h *Handler) HandleListBacktestJobs(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	query := &domain.BacktestJobQuery{
		Page:     1,
		PageSize: 20,
	}

	// Parse query parameters
	queryParams := r.URL.Query()
	if strategyID := queryParams.Get("strategy_id"); strategyID != "" {
		if id, err := parseUUID(strategyID); err == nil {
			query.StrategyID = &id
		}
	}
	if optRunID := queryParams.Get("optimization_run_id"); optRunID != "" {
		if id, err := parseUUID(optRunID); err == nil {
			query.OptimizationRunID = &id
		}
	}
	if status := queryParams.Get("status"); status != "" {
		jobStatus := domain.JobStatusFromString(status)
		query.Status = &jobStatus
	}
	if orderBy := queryParams.Get("order_by"); orderBy != "" {
		query.OrderBy = orderBy
	}
	if ascending := queryParams.Get("ascending"); ascending == "true" {
		query.Ascending = true
	}
	if page := queryParams.Get("page"); page != "" {
		if val, err := strconv.Atoi(page); err == nil {
			query.Page = val
		}
	}
	if pageSize := queryParams.Get("page_size"); pageSize != "" {
		if val, err := strconv.Atoi(pageSize); err == nil {
			query.PageSize = val
		}
	}

	query.SetDefaults()

	jobs, pagination, err := h.repos.BacktestJob.Query(r.Context(), query)
	if err != nil {
		h.logger.Error("Failed to query backtest jobs", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to query backtest jobs")
		return
	}

	writeJSON(w, http.StatusOK, ListBacktestJobsResponse{
		Backtests:  jobs,
		Pagination: *pagination,
	})
}

// GetQueueStatsResponse represents the response for getting queue statistics.
type GetQueueStatsResponse struct {
	Stats *domain.QueueStats `json:"stats"`
}

// HandleGetQueueStats retrieves queue statistics.
func (h *Handler) HandleGetQueueStats(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	stats, err := h.repos.BacktestJob.GetQueueStats(r.Context())
	if err != nil {
		h.logger.Error("Failed to get queue stats", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get queue stats")
		return
	}

	writeJSON(w, http.StatusOK, GetQueueStatsResponse{Stats: stats})
}

// ========================================
// Optimization Handlers
// ========================================

// StartOptimizationRequest represents the request body for starting an optimization.
type StartOptimizationRequest struct {
	Name           string                    `json:"name"`
	BaseStrategyID string                    `json:"base_strategy_id"`
	Config         domain.OptimizationConfig `json:"config"`
}

// StartOptimizationResponse represents the response for starting an optimization.
type StartOptimizationResponse struct {
	Run *domain.OptimizationRun `json:"run"`
}

// HandleStartOptimization starts a new optimization run.
func (h *Handler) HandleStartOptimization(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	var req StartOptimizationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid request body")
		return
	}

	baseStrategyID, err := parseUUID(req.BaseStrategyID)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid base_strategy_id")
		return
	}

	run := domain.NewOptimizationRun(req.Name, baseStrategyID, req.Config)

	if err := h.repos.Optimization.Create(r.Context(), run); err != nil {
		h.logger.Error("Failed to create optimization run", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to create optimization run")
		return
	}

	// Publish optimization.started event to trigger Python orchestrator
	if err := h.eventPublisher.PublishOptimizationStarted(run); err != nil {
		h.logger.Error("Failed to publish optimization started event", zap.Error(err), zap.String("run_id", run.ID.String()))
		// Don't fail the request, just log the error - optimization was created
	}

	writeJSON(w, http.StatusCreated, StartOptimizationResponse{Run: run})
}

// GetOptimizationRunResponse represents the response for getting an optimization run.
type GetOptimizationRunResponse struct {
	Run        *domain.OptimizationRun        `json:"run"`
	Iterations []*domain.OptimizationIteration `json:"iterations"`
}

// HandleGetOptimizationRun retrieves an optimization run with its iterations.
func (h *Handler) HandleGetOptimizationRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/optimizations/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid optimization run id")
		return
	}

	run, err := h.repos.Optimization.GetByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "optimization run not found")
			return
		}
		h.logger.Error("Failed to get optimization run", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get optimization run")
		return
	}

	iterations, err := h.repos.Optimization.GetIterations(r.Context(), id)
	if err != nil {
		h.logger.Error("Failed to get optimization iterations", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get iterations")
		return
	}

	writeJSON(w, http.StatusOK, GetOptimizationRunResponse{
		Run:        run,
		Iterations: iterations,
	})
}

// ListOptimizationRunsResponse represents the response for listing optimization runs.
type ListOptimizationRunsResponse struct {
	Runs       []*domain.OptimizationRun `json:"runs"`
	Pagination domain.PaginationResponse `json:"pagination"`
}

// HandleListOptimizationRuns lists optimization runs with filters.
func (h *Handler) HandleListOptimizationRuns(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	query := domain.OptimizationListQuery{
		Page:     1,
		PageSize: 20,
	}

	// Parse query parameters
	queryParams := r.URL.Query()
	if status := queryParams.Get("status"); status != "" {
		optStatus := domain.OptimizationStatusFromString(status)
		query.Status = &optStatus
	}
	if orderBy := queryParams.Get("order_by"); orderBy != "" {
		query.OrderBy = orderBy
	}
	if ascending := queryParams.Get("ascending"); ascending == "true" {
		query.Ascending = true
	}
	if page := queryParams.Get("page"); page != "" {
		if val, err := strconv.Atoi(page); err == nil {
			query.Page = val
		}
	}
	if pageSize := queryParams.Get("page_size"); pageSize != "" {
		if val, err := strconv.Atoi(pageSize); err == nil {
			query.PageSize = val
		}
	}

	// Parse time range if provided
	if startStr := queryParams.Get("start_time"); startStr != "" {
		if start, err := time.Parse(time.RFC3339, startStr); err == nil {
			if query.TimeRange == nil {
				query.TimeRange = &domain.TimeRange{}
			}
			query.TimeRange.Start = start
		}
	}
	if endStr := queryParams.Get("end_time"); endStr != "" {
		if end, err := time.Parse(time.RFC3339, endStr); err == nil {
			if query.TimeRange == nil {
				query.TimeRange = &domain.TimeRange{}
			}
			query.TimeRange.End = end
		}
	}

	query.SetDefaults()

	runs, totalCount, err := h.repos.Optimization.List(r.Context(), query)
	if err != nil {
		h.logger.Error("Failed to list optimization runs", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to list optimization runs")
		return
	}

	pagination := domain.NewPaginationResponse(totalCount, query.Page, query.PageSize)

	writeJSON(w, http.StatusOK, ListOptimizationRunsResponse{
		Runs:       runs,
		Pagination: pagination,
	})
}

// ControlOptimizationRequest represents the request body for controlling an optimization.
type ControlOptimizationRequest struct {
	Action string `json:"action"` // "pause", "resume", "cancel"
}

// ControlOptimizationResponse represents the response for controlling an optimization.
type ControlOptimizationResponse struct {
	Success bool                    `json:"success"`
	Run     *domain.OptimizationRun `json:"run"`
}

// HandleControlOptimization controls an optimization run (pause/resume/cancel).
func (h *Handler) HandleControlOptimization(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	// Extract ID from path like /api/v1/optimizations/:id/control
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/optimizations/")
	path = strings.TrimSuffix(path, "/control")
	idStr := path

	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid optimization run id")
		return
	}

	var req ControlOptimizationRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid request body")
		return
	}

	var newStatus domain.OptimizationStatus
	switch strings.ToLower(req.Action) {
	case "pause":
		newStatus = domain.OptimizationStatusPaused
	case "resume":
		newStatus = domain.OptimizationStatusRunning
	case "cancel":
		newStatus = domain.OptimizationStatusCancelled
	case "complete":
		newStatus = domain.OptimizationStatusCompleted
	case "fail":
		newStatus = domain.OptimizationStatusFailed
	default:
		writeError(w, http.StatusBadRequest, errors.New("invalid action"), "action must be 'pause', 'resume', 'cancel', 'complete', or 'fail'")
		return
	}

	if err := h.repos.Optimization.UpdateStatus(r.Context(), id, newStatus); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "optimization run not found")
			return
		}
		h.logger.Error("Failed to control optimization run", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to control optimization")
		return
	}

	run, err := h.repos.Optimization.GetByID(r.Context(), id)
	if err != nil {
		h.logger.Error("Failed to get optimization run after control", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get optimization run")
		return
	}

	writeJSON(w, http.StatusOK, ControlOptimizationResponse{
		Success: true,
		Run:     run,
	})
}

// ============================================================================
// Agent Status Handlers
// ============================================================================

// AgentType represents the type of agent.
type AgentType string

const (
	AgentTypeOrchestrator AgentType = "orchestrator"
	AgentTypeEngineer     AgentType = "engineer"
	AgentTypeAnalyst      AgentType = "analyst"
	AgentTypeScout        AgentType = "scout"
)

// AgentStatusValue represents the status of an agent.
type AgentStatusValue string

const (
	AgentStatusActive  AgentStatusValue = "active"
	AgentStatusIdle    AgentStatusValue = "idle"
	AgentStatusOffline AgentStatusValue = "offline"
)

// AgentInfo represents an agent's status information.
type AgentInfo struct {
	Type        AgentType        `json:"type"`
	Status      AgentStatusValue `json:"status"`
	LastSeen    *time.Time       `json:"last_seen,omitempty"`
	CurrentTask *string          `json:"current_task,omitempty"`
}

// HandleGetAgentStatus retrieves the status of all agents.
// GET /api/v1/agents/status
func (h *Handler) HandleGetAgentStatus(w http.ResponseWriter, r *http.Request) {
	// Get real agent status from the AgentStore (populated by heartbeats)
	agents := h.agentStore.GetAll()

	// If no agents have sent heartbeats yet, return default offline statuses
	if len(agents) == 0 {
		agents = []AgentInfo{
			{
				Type:   AgentTypeOrchestrator,
				Status: AgentStatusOffline,
			},
			{
				Type:   AgentTypeEngineer,
				Status: AgentStatusOffline,
			},
			{
				Type:   AgentTypeAnalyst,
				Status: AgentStatusOffline,
			},
			{
				Type:   AgentTypeScout,
				Status: AgentStatusOffline,
			},
		}
	}

	writeJSON(w, http.StatusOK, agents)
}

// ============================================================================
// Performance Data Handlers
// ============================================================================

// PerformanceDataPoint represents a single data point for performance charts.
type PerformanceDataPoint struct {
	Timestamp        time.Time `json:"timestamp"`
	SharpeRatio      float64   `json:"sharpe_ratio"`
	OptimizationID   string    `json:"optimization_id"`
	OptimizationName string    `json:"optimization_name"`
}

// HandleGetOptimizationPerformance retrieves performance data for the chart.
// GET /api/v1/optimizations/performance?period=24h
func (h *Handler) HandleGetOptimizationPerformance(w http.ResponseWriter, r *http.Request) {
	period := r.URL.Query().Get("period")
	if period == "" {
		period = "24h"
	}

	// Parse period duration
	var duration time.Duration
	switch period {
	case "1h":
		duration = time.Hour
	case "6h":
		duration = 6 * time.Hour
	case "12h":
		duration = 12 * time.Hour
	case "24h":
		duration = 24 * time.Hour
	case "7d":
		duration = 7 * 24 * time.Hour
	default:
		duration = 24 * time.Hour
	}

	// Calculate time range
	endTime := time.Now()
	startTime := endTime.Add(-duration)

	// Query optimization iterations within the time range
	iterations, err := h.repos.Optimization.GetIterationsInTimeRange(r.Context(), startTime, endTime)
	if err != nil {
		// If the method fails, return empty data
		h.logger.Warn("Failed to get optimization iterations for performance", zap.Error(err))
		writeJSON(w, http.StatusOK, []PerformanceDataPoint{})
		return
	}

	// For now, return iterations as data points without detailed result info
	// In a future enhancement, we would join with backtest_results to get sharpe ratios
	dataPoints := make([]PerformanceDataPoint, 0, len(iterations))
	for _, iter := range iterations {
		dataPoints = append(dataPoints, PerformanceDataPoint{
			Timestamp:        iter.CreatedAt,
			SharpeRatio:      0, // Would need to query backtest_results by iter.ResultID
			OptimizationID:   iter.OptimizationRunID.String(),
			OptimizationName: iter.OptimizationRunID.String(),
		})
	}

	writeJSON(w, http.StatusOK, dataPoints)
}
