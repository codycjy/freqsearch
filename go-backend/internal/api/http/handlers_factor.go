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

	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// ========================================
// Factor Handlers
// ========================================

// CreateFactorRequest represents the request body for creating a factor.
type CreateFactorRequest struct {
	Name            string   `json:"name"`
	Source          string   `json:"source"`
	Version         int      `json:"version"`
	Expression      string   `json:"expression"`
	Description     string   `json:"description"`
	CodeTemplate    string   `json:"code_template"`
	OperatorDeps    []string `json:"operator_deps"`
	DataDeps        []string `json:"data_deps"`
	Category        string   `json:"category"`
	SignalType      string   `json:"signal_type"`
	HoldingPeriod   string   `json:"holding_period"`
	DataRequirement string   `json:"data_requirement"`
	MarketRegime    string   `json:"market_regime"`
	Complexity      string   `json:"complexity"`
}

// CreateFactorResponse represents the response for creating a factor.
type CreateFactorResponse struct {
	Factor *domain.Factor `json:"factor"`
}

// HandleCreateFactor creates a new factor.
func (h *Handler) HandleCreateFactor(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	var req CreateFactorRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid request body")
		return
	}

	// Validate required fields
	if req.Name == "" || req.Source == "" || req.Expression == "" || req.Category == "" {
		writeError(w, http.StatusBadRequest, errors.New("missing required fields"), "name, source, expression, and category are required")
		return
	}

	factor := &domain.Factor{
		ID:              uuid.New(),
		Name:            req.Name,
		Source:          req.Source,
		Version:         req.Version,
		Expression:      req.Expression,
		Description:     req.Description,
		CodeTemplate:    req.CodeTemplate,
		OperatorDeps:    req.OperatorDeps,
		DataDeps:        req.DataDeps,
		Category:        req.Category,
		SignalType:      req.SignalType,
		HoldingPeriod:   req.HoldingPeriod,
		DataRequirement: req.DataRequirement,
		MarketRegime:    req.MarketRegime,
		Complexity:      req.Complexity,
		IsActive:        true,
		CreatedAt:       time.Now(),
		UpdatedAt:       time.Now(),
	}

	if factor.Version == 0 {
		factor.Version = 1
	}

	if err := h.repos.Factor.Create(r.Context(), factor); err != nil {
		if errors.Is(err, domain.ErrDuplicate) {
			writeError(w, http.StatusConflict, err, "factor with same name already exists")
			return
		}
		h.logger.Error("Failed to create factor", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to create factor")
		return
	}

	writeJSON(w, http.StatusCreated, CreateFactorResponse{Factor: factor})
}

// GetFactorResponse represents the response for getting a factor.
type GetFactorResponse struct {
	Factor *domain.Factor `json:"factor"`
}

// HandleGetFactor retrieves a factor by ID.
func (h *Handler) HandleGetFactor(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/factors/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid factor id")
		return
	}

	factor, err := h.repos.Factor.GetByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "factor not found")
			return
		}
		h.logger.Error("Failed to get factor", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get factor")
		return
	}

	writeJSON(w, http.StatusOK, GetFactorResponse{Factor: factor})
}

// HandleGetFactorByName retrieves a factor by name.
func (h *Handler) HandleGetFactorByName(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	// Extract name from path like /api/v1/factors/name/:name
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/factors/name/")
	name := path

	if name == "" {
		writeError(w, http.StatusBadRequest, errors.New("name is required"), "")
		return
	}

	factor, err := h.repos.Factor.GetByName(r.Context(), name)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "factor not found")
			return
		}
		h.logger.Error("Failed to get factor by name", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get factor")
		return
	}

	writeJSON(w, http.StatusOK, GetFactorResponse{Factor: factor})
}

// UpdateFactorRequest represents the request body for updating a factor.
type UpdateFactorRequest struct {
	Name            string   `json:"name"`
	Source          string   `json:"source"`
	Version         int      `json:"version"`
	Expression      string   `json:"expression"`
	Description     string   `json:"description"`
	CodeTemplate    string   `json:"code_template"`
	OperatorDeps    []string `json:"operator_deps"`
	DataDeps        []string `json:"data_deps"`
	Category        string   `json:"category"`
	SignalType      string   `json:"signal_type"`
	HoldingPeriod   string   `json:"holding_period"`
	DataRequirement string   `json:"data_requirement"`
	MarketRegime    string   `json:"market_regime"`
	Complexity      string   `json:"complexity"`
	IsActive        bool     `json:"is_active"`
}

// HandleUpdateFactor updates an existing factor.
func (h *Handler) HandleUpdateFactor(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/factors/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid factor id")
		return
	}

	var req UpdateFactorRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid request body")
		return
	}

	// Get existing factor
	factor, err := h.repos.Factor.GetByID(r.Context(), id)
	if err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "factor not found")
			return
		}
		h.logger.Error("Failed to get factor", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get factor")
		return
	}

	// Update fields
	factor.Name = req.Name
	factor.Source = req.Source
	factor.Version = req.Version
	factor.Expression = req.Expression
	factor.Description = req.Description
	factor.CodeTemplate = req.CodeTemplate
	factor.OperatorDeps = req.OperatorDeps
	factor.DataDeps = req.DataDeps
	factor.Category = req.Category
	factor.SignalType = req.SignalType
	factor.HoldingPeriod = req.HoldingPeriod
	factor.DataRequirement = req.DataRequirement
	factor.MarketRegime = req.MarketRegime
	factor.Complexity = req.Complexity
	factor.IsActive = req.IsActive
	factor.UpdatedAt = time.Now()

	if err := h.repos.Factor.Update(r.Context(), factor); err != nil {
		h.logger.Error("Failed to update factor", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to update factor")
		return
	}

	writeJSON(w, http.StatusOK, GetFactorResponse{Factor: factor})
}

// HandleDeleteFactor deletes a factor by ID.
func (h *Handler) HandleDeleteFactor(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	idStr := extractID(r.URL.Path, "/api/v1/factors/")
	id, err := parseUUID(idStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, err, "invalid factor id")
		return
	}

	if err := h.repos.Factor.Delete(r.Context(), id); err != nil {
		if errors.Is(err, domain.ErrNotFound) {
			writeError(w, http.StatusNotFound, err, "factor not found")
			return
		}
		h.logger.Error("Failed to delete factor", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to delete factor")
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ListFactorsResponse represents the response for listing factors.
type ListFactorsResponse struct {
	Factors    []*domain.Factor          `json:"factors"`
	Pagination domain.PaginationResponse `json:"pagination"`
}

// HandleListFactors lists factors with filters.
func (h *Handler) HandleListFactors(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	query := domain.FactorSearchQuery{
		Page:     1,
		PageSize: 20,
	}

	// Parse query parameters
	queryParams := r.URL.Query()

	if name := queryParams.Get("name"); name != "" {
		query.Name = &name
	}
	if source := queryParams.Get("source"); source != "" {
		query.Source = &source
	}
	if category := queryParams.Get("category"); category != "" {
		query.Category = &category
	}
	if signalType := queryParams.Get("signal_type"); signalType != "" {
		query.SignalType = &signalType
	}
	if holdingPeriod := queryParams.Get("holding_period"); holdingPeriod != "" {
		query.HoldingPeriod = &holdingPeriod
	}
	if dataRequirement := queryParams.Get("data_requirement"); dataRequirement != "" {
		query.DataRequirement = &dataRequirement
	}
	if marketRegime := queryParams.Get("market_regime"); marketRegime != "" {
		query.MarketRegime = &marketRegime
	}
	if complexity := queryParams.Get("complexity"); complexity != "" {
		query.Complexity = &complexity
	}
	if isActive := queryParams.Get("is_active"); isActive != "" {
		active := isActive == "true"
		query.IsActive = &active
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

	factors, totalCount, err := h.repos.Factor.List(r.Context(), query)
	if err != nil {
		h.logger.Error("Failed to list factors", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to list factors")
		return
	}

	pagination := domain.NewPaginationResponse(totalCount, query.Page, query.PageSize)

	writeJSON(w, http.StatusOK, ListFactorsResponse{
		Factors:    factors,
		Pagination: pagination,
	})
}

// SearchFactorsResponse represents the response for searching factors.
type SearchFactorsResponse struct {
	Factors []*domain.Factor `json:"factors"`
}

// HandleSearchFactors searches factors by keyword.
func (h *Handler) HandleSearchFactors(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	keyword := r.URL.Query().Get("q")
	if keyword == "" {
		writeError(w, http.StatusBadRequest, errors.New("keyword is required"), "query parameter 'q' is required")
		return
	}

	limit := 20
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if val, err := strconv.Atoi(limitStr); err == nil && val > 0 {
			limit = val
		}
	}

	factors, err := h.repos.Factor.Search(r.Context(), keyword, limit)
	if err != nil {
		h.logger.Error("Failed to search factors", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to search factors")
		return
	}

	writeJSON(w, http.StatusOK, SearchFactorsResponse{Factors: factors})
}

// CategoryStatsResponse represents the response for category statistics.
type CategoryStatsResponse struct {
	Stats domain.CategoryStats `json:"stats"`
}

// HandleGetCategoryStats retrieves category statistics.
func (h *Handler) HandleGetCategoryStats(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeError(w, http.StatusMethodNotAllowed, errors.New("method not allowed"), "")
		return
	}

	stats, err := h.repos.Factor.GetCategoryStats(r.Context())
	if err != nil {
		h.logger.Error("Failed to get category stats", zap.Error(err))
		writeError(w, http.StatusInternalServerError, err, "failed to get category stats")
		return
	}

	writeJSON(w, http.StatusOK, CategoryStatsResponse{Stats: stats})
}
