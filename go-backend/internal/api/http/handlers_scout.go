package http

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/domain"
	"github.com/saltfish/freqsearch/go-backend/internal/events"
)

// ============================================================================
// Scout Run Handlers
// ============================================================================

// TriggerScoutRequest represents the request body for triggering a scout run.
type TriggerScoutRequest struct {
	Source        string `json:"source"`         // "stratninja", "github", etc.
	MaxStrategies int    `json:"max_strategies"` // Maximum strategies to fetch
	TriggerType   string `json:"trigger_type"`   // "manual", "scheduled", "event"
	TriggeredBy   string `json:"triggered_by"`   // User ID or "system"
}

// TriggerScoutResponse represents the response for triggering a scout run.
type TriggerScoutResponse struct {
	Run *domain.ScoutRun `json:"run"`
}

// HandleTriggerScout triggers a new Scout run.
// POST /api/v1/agents/scout/trigger
func (h *Handler) HandleTriggerScout(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	var req TriggerScoutRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid request body")
		return
	}

	// Validate request
	if req.Source == "" {
		writeError(w, http.StatusBadRequest, errors.New("source is required"), "")
		return
	}
	if req.MaxStrategies <= 0 {
		req.MaxStrategies = 100 // Default
	}
	if req.TriggerType == "" {
		req.TriggerType = "manual"
	}
	if req.TriggeredBy == "" {
		req.TriggeredBy = "unknown"
	}

	// Check if there's already an active Scout run
	activeRun, err := h.repos.Scout.GetActiveRun(r.Context())
	if err != nil && !errors.Is(err, domain.ErrNotFound) {
		h.logger.Error("Failed to check for active Scout run", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to check for active runs")
		return
	}
	if activeRun != nil {
		writeError(w, http.StatusConflict, errors.New("scout run already in progress"),
			"Scout run already in progress with ID: "+activeRun.ID.String())
		return
	}

	// Parse and validate trigger type
	triggerType := domain.ScoutTriggerTypeFromString(req.TriggerType)

	// Create scout run
	run := domain.NewScoutRun(
		triggerType,
		req.TriggeredBy,
		req.Source,
		req.MaxStrategies,
	)

	if err := h.repos.Scout.CreateRun(r.Context(), run); err != nil {
		h.logger.Error("Failed to create scout run", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to create scout run")
		return
	}

	// Publish scout trigger event
	if h.eventPublisher != nil {
		event := events.NewScoutTriggerEvent(run)
		if err := h.eventPublisher.PublishScoutTrigger(event); err != nil {
			h.logger.Error("Failed to publish scout trigger event", zap.Error(err))
			// Don't fail the request, just log the error
		}
	}

	h.logger.Info("Scout run triggered",
		zap.String("run_id", run.ID.String()),
		zap.String("source", run.Source),
		zap.String("trigger_type", run.TriggerType.String()),
	)

	writeJSON(w, http.StatusCreated, TriggerScoutResponse{Run: run})
}

// ListScoutRunsResponse represents the response for listing scout runs.
type ListScoutRunsResponse struct {
	Runs       []*domain.ScoutRun        `json:"runs"`
	Pagination domain.PaginationResponse `json:"pagination"`
}

// HandleListScoutRuns lists Scout runs with filters.
// GET /api/v1/agents/scout/runs
func (h *Handler) HandleListScoutRuns(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	query := domain.ScoutRunQuery{
		Page:     1,
		PageSize: 20,
	}

	// Parse query parameters
	queryParams := r.URL.Query()
	if status := queryParams.Get("status"); status != "" {
		scoutStatus := domain.ScoutRunStatusFromString(status)
		query.Status = &scoutStatus
	}
	if source := queryParams.Get("source"); source != "" {
		query.Source = &source
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

	runs, totalCount, err := h.repos.Scout.ListRuns(r.Context(), query)
	if err != nil {
		h.logger.Error("Failed to list scout runs", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to list scout runs")
		return
	}

	pagination := domain.NewPaginationResponse(totalCount, query.Page, query.PageSize)

	writeJSON(w, http.StatusOK, ListScoutRunsResponse{
		Runs:       runs,
		Pagination: pagination,
	})
}

// GetScoutRunResponse represents the response for getting a scout run.
type GetScoutRunResponse struct {
	Run *domain.ScoutRun `json:"run"`
}

// HandleGetScoutRun retrieves a Scout run by ID.
// GET /api/v1/agents/scout/runs/:id
func (h *Handler) HandleGetScoutRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/agents/scout/runs/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid run id")
		return
	}

	run, err := h.repos.Scout.GetRunByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "scout run not found")
			return
		}
		h.logger.Error("Failed to get scout run", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get scout run")
		return
	}

	writeJSON(w, http.StatusOK, GetScoutRunResponse{Run: run})
}

// HandleCancelScoutRun cancels a Scout run.
// DELETE /api/v1/agents/scout/runs/:id
func (h *Handler) HandleCancelScoutRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/agents/scout/runs/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid run id")
		return
	}

	// Get run to check status
	run, err := h.repos.Scout.GetRunByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "scout run not found")
			return
		}
		h.logger.Error("Failed to get scout run", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get scout run")
		return
	}

	// Check if the run can be cancelled
	if run.Status.IsTerminal() {
		writeError(w, http.StatusConflict, errors.New("cannot cancel completed run"),
			"Scout run is already in terminal state: "+run.Status.String())
		return
	}

	// Update run status to cancelled
	if err := h.repos.Scout.UpdateRunStatus(r.Context(), id, domain.ScoutRunStatusCancelled, nil); err != nil {
		h.logger.Error("Failed to cancel Scout run", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to cancel Scout run")
		return
	}

	// Publish Scout cancelled event
	if h.eventPublisher != nil {
		if err := h.eventPublisher.PublishScoutCancelled(id); err != nil {
			h.logger.Error("Failed to publish Scout cancelled event", zap.Error(err))
			// Don't fail the request, just log the error
		}
	}

	h.logger.Info("Scout run cancelled", zap.String("run_id", id.String()))

	w.WriteHeader(http.StatusNoContent)
}

// ============================================================================
// Scout Schedule Handlers
// ============================================================================

// ListScoutSchedulesResponse represents the response for listing scout schedules.
type ListScoutSchedulesResponse struct {
	Schedules  []*domain.ScoutSchedule   `json:"schedules"`
	Pagination domain.PaginationResponse `json:"pagination"`
}

// HandleListScoutSchedules lists Scout schedules with filters.
// GET /api/v1/agents/scout/schedules
func (h *Handler) HandleListScoutSchedules(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	query := domain.ScoutScheduleQuery{
		Page:     1,
		PageSize: 20,
	}

	// Parse query parameters
	queryParams := r.URL.Query()
	if enabled := queryParams.Get("enabled"); enabled != "" {
		if val, err := strconv.ParseBool(enabled); err == nil {
			query.Enabled = &val
		}
	}
	if source := queryParams.Get("source"); source != "" {
		query.Source = &source
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

	schedules, totalCount, err := h.repos.Scout.ListSchedules(r.Context(), query)
	if err != nil {
		h.logger.Error("Failed to list scout schedules", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to list scout schedules")
		return
	}

	pagination := domain.NewPaginationResponse(totalCount, query.Page, query.PageSize)

	writeJSON(w, http.StatusOK, ListScoutSchedulesResponse{
		Schedules:  schedules,
		Pagination: pagination,
	})
}

// CreateScoutScheduleRequest represents the request body for creating a scout schedule.
type CreateScoutScheduleRequest struct {
	Name           string `json:"name"`
	CronExpression string `json:"cron_expression"`
	Source         string `json:"source"`
	MaxStrategies  int    `json:"max_strategies"`
}

// CreateScoutScheduleResponse represents the response for creating a scout schedule.
type CreateScoutScheduleResponse struct {
	Schedule *domain.ScoutSchedule `json:"schedule"`
}

// HandleCreateScoutSchedule creates a new Scout schedule.
// POST /api/v1/agents/scout/schedules
func (h *Handler) HandleCreateScoutSchedule(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	var req CreateScoutScheduleRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid request body")
		return
	}

	// Validate request
	if req.Name == "" {
		writeError(w, http.StatusBadRequest, errors.New("name is required"), "")
		return
	}
	if req.CronExpression == "" {
		writeError(w, http.StatusBadRequest, errors.New("cron_expression is required"), "")
		return
	}
	if req.Source == "" {
		writeError(w, http.StatusBadRequest, errors.New("source is required"), "")
		return
	}
	if req.MaxStrategies <= 0 {
		req.MaxStrategies = 100 // Default
	}

	// Check if schedule with same name already exists
	existingSchedule, err := h.repos.Scout.GetScheduleByName(r.Context(), req.Name)
	if err != nil && !errors.Is(err, domain.ErrNotFound) {
		h.logger.Error("Failed to check for existing schedule", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to check for existing schedule")
		return
	}
	if existingSchedule != nil {
		writeError(w, http.StatusConflict, domain.ErrDuplicate, "schedule with this name already exists")
		return
	}

	// Create schedule
	schedule := domain.NewScoutSchedule(req.Name, req.CronExpression, req.Source, req.MaxStrategies)

	if err := h.repos.Scout.CreateSchedule(r.Context(), schedule); err != nil {
		h.logger.Error("Failed to create Scout schedule", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to create Scout schedule")
		return
	}

	// Reload schedules in the scheduler
	if h.scoutScheduler != nil {
		_ = h.scoutScheduler.ReloadSchedules()
	}

	h.logger.Info("Scout schedule created",
		zap.String("schedule_id", schedule.ID.String()),
		zap.String("name", schedule.Name),
		zap.String("cron", schedule.CronExpression),
	)

	writeJSON(w, http.StatusCreated, CreateScoutScheduleResponse{Schedule: schedule})
}

// GetScoutScheduleResponse represents the response for getting a scout schedule.
type GetScoutScheduleResponse struct {
	Schedule *domain.ScoutSchedule `json:"schedule"`
}

// HandleGetScoutSchedule retrieves a Scout schedule by ID.
// GET /api/v1/agents/scout/schedules/:id
func (h *Handler) HandleGetScoutSchedule(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/agents/scout/schedules/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid schedule id")
		return
	}

	schedule, err := h.repos.Scout.GetScheduleByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "scout schedule not found")
			return
		}
		h.logger.Error("Failed to get scout schedule", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get scout schedule")
		return
	}

	writeJSON(w, http.StatusOK, GetScoutScheduleResponse{Schedule: schedule})
}

// UpdateScoutScheduleRequest represents the request body for updating a scout schedule.
type UpdateScoutScheduleRequest struct {
	Name           *string `json:"name,omitempty"`
	CronExpression *string `json:"cron_expression,omitempty"`
	Source         *string `json:"source,omitempty"`
	MaxStrategies  *int    `json:"max_strategies,omitempty"`
	Enabled        *bool   `json:"enabled,omitempty"`
}

// UpdateScoutScheduleResponse represents the response for updating a scout schedule.
type UpdateScoutScheduleResponse struct {
	Schedule *domain.ScoutSchedule `json:"schedule"`
}

// HandleUpdateScoutSchedule updates a Scout schedule.
// PUT /api/v1/agents/scout/schedules/:id
func (h *Handler) HandleUpdateScoutSchedule(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/agents/scout/schedules/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid schedule id")
		return
	}

	var req UpdateScoutScheduleRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid request body")
		return
	}

	// Get existing schedule
	schedule, err := h.repos.Scout.GetScheduleByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "scout schedule not found")
			return
		}
		h.logger.Error("Failed to get scout schedule", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get scout schedule")
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
	schedule.UpdatedAt = time.Now()

	if err := h.repos.Scout.UpdateSchedule(r.Context(), schedule); err != nil {
		h.logger.Error("Failed to update Scout schedule", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to update Scout schedule")
		return
	}

	// Reload schedules in the scheduler
	if h.scoutScheduler != nil {
		_ = h.scoutScheduler.ReloadSchedules()
	}

	h.logger.Info("Scout schedule updated",
		zap.String("schedule_id", schedule.ID.String()),
		zap.String("name", schedule.Name),
	)

	writeJSON(w, http.StatusOK, UpdateScoutScheduleResponse{Schedule: schedule})
}

// HandleDeleteScoutSchedule deletes a Scout schedule.
// DELETE /api/v1/agents/scout/schedules/:id
func (h *Handler) HandleDeleteScoutSchedule(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/agents/scout/schedules/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid schedule id")
		return
	}

	if err := h.repos.Scout.DeleteSchedule(r.Context(), id); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "Scout schedule not found")
			return
		}
		h.logger.Error("Failed to delete Scout schedule", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to delete Scout schedule")
		return
	}

	// Reload schedules in the scheduler
	if h.scoutScheduler != nil {
		_ = h.scoutScheduler.ReloadSchedules()
	}

	h.logger.Info("Scout schedule deleted", zap.String("schedule_id", id.String()))

	w.WriteHeader(http.StatusNoContent)
}

// ToggleScoutScheduleResponse represents the response for toggling a scout schedule.
type ToggleScoutScheduleResponse struct {
	Schedule *domain.ScoutSchedule `json:"schedule"`
}

// HandleToggleScoutSchedule toggles the enabled status of a Scout schedule.
// POST /api/v1/agents/scout/schedules/:id/toggle
func (h *Handler) HandleToggleScoutSchedule(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	// Extract ID from path like /api/v1/agents/scout/schedules/:id/toggle
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/agents/scout/schedules/")
	path = strings.TrimSuffix(path, "/toggle")
	idStr := path

	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid schedule id")
		return
	}

	// Get existing schedule
	schedule, err := h.repos.Scout.GetScheduleByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "scout schedule not found")
			return
		}
		h.logger.Error("Failed to get scout schedule", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get scout schedule")
		return
	}

	// Toggle enabled status
	schedule.Enabled = !schedule.Enabled
	schedule.UpdatedAt = time.Now()

	if err := h.repos.Scout.UpdateSchedule(r.Context(), schedule); err != nil {
		h.logger.Error("Failed to toggle Scout schedule", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to toggle Scout schedule")
		return
	}

	// Reload schedules in the scheduler
	if h.scoutScheduler != nil {
		_ = h.scoutScheduler.ReloadSchedules()
	}

	h.logger.Info("Scout schedule toggled",
		zap.String("schedule_id", schedule.ID.String()),
		zap.Bool("enabled", schedule.Enabled),
	)

	writeJSON(w, http.StatusOK, ToggleScoutScheduleResponse{Schedule: schedule})
}
