package domain

import (
	"time"

	"github.com/google/uuid"
)

// Factor represents a quantitative alpha factor.
type Factor struct {
	ID          uuid.UUID `json:"id"`
	Name        string    `json:"name"`
	Source      string    `json:"source"`
	Version     int       `json:"version"`
	Expression  string    `json:"expression"`
	Description string    `json:"description,omitempty"`

	// Executable code
	CodeTemplate string   `json:"code_template,omitempty"`
	OperatorDeps []string `json:"operator_deps,omitempty"`
	DataDeps     []string `json:"data_deps,omitempty"`

	// 6-dimensional classification tags
	Category        string `json:"category"`
	SignalType      string `json:"signal_type,omitempty"`
	HoldingPeriod   string `json:"holding_period,omitempty"`
	DataRequirement string `json:"data_requirement,omitempty"`
	MarketRegime    string `json:"market_regime,omitempty"`
	Complexity      string `json:"complexity,omitempty"`

	// Performance metadata (optional)
	AvgReturn    *float64   `json:"avg_return,omitempty"`
	SharpeRatio  *float64   `json:"sharpe_ratio,omitempty"`
	MaxDrawdown  *float64   `json:"max_drawdown,omitempty"`
	WinRate      *float64   `json:"win_rate,omitempty"`
	TestedAt     *time.Time `json:"tested_at,omitempty"`

	// Metadata
	IsActive  bool      `json:"is_active"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// NewFactor creates a new Factor with generated UUID and timestamps.
func NewFactor(name, source, expression, category string) *Factor {
	now := time.Now()
	return &Factor{
		ID:           uuid.New(),
		Name:         name,
		Source:       source,
		Version:      1,
		Expression:   expression,
		Category:     category,
		IsActive:     true,
		OperatorDeps: make([]string, 0),
		DataDeps:     make([]string, 0),
		CreatedAt:    now,
		UpdatedAt:    now,
	}
}

// FactorOperator represents a factor computation operator.
type FactorOperator struct {
	ID          uuid.UUID `json:"id"`
	Name        string    `json:"name"`
	Category    string    `json:"category"`
	Signature   string    `json:"signature"`
	Description string    `json:"description,omitempty"`
	CodeImpl    string    `json:"code_impl"`
	CreatedAt   time.Time `json:"created_at"`
}

// NewFactorOperator creates a new FactorOperator.
func NewFactorOperator(name, category, signature, codeImpl string) *FactorOperator {
	return &FactorOperator{
		ID:        uuid.New(),
		Name:      name,
		Category:  category,
		Signature: signature,
		CodeImpl:  codeImpl,
		CreatedAt: time.Now(),
	}
}

// StrategyFactor represents the relationship between a strategy and a factor.
type StrategyFactor struct {
	ID         uuid.UUID              `json:"id"`
	StrategyID uuid.UUID              `json:"strategy_id"`
	FactorID   uuid.UUID              `json:"factor_id"`
	UsageType  string                 `json:"usage_type,omitempty"`
	Parameters map[string]interface{} `json:"parameters,omitempty"`
	CreatedAt  time.Time              `json:"created_at"`
}

// FactorSearchQuery represents query parameters for searching factors.
type FactorSearchQuery struct {
	Name            *string `json:"name,omitempty"`
	Source          *string `json:"source,omitempty"`
	Category        *string `json:"category,omitempty"`
	SignalType      *string `json:"signal_type,omitempty"`
	HoldingPeriod   *string `json:"holding_period,omitempty"`
	DataRequirement *string `json:"data_requirement,omitempty"`
	MarketRegime    *string `json:"market_regime,omitempty"`
	Complexity      *string `json:"complexity,omitempty"`
	Keyword         *string `json:"keyword,omitempty"` // Search in description
	IsActive        *bool   `json:"is_active,omitempty"`
	OrderBy         string  `json:"order_by,omitempty"` // "name", "category", "created_at"
	Ascending       bool    `json:"ascending,omitempty"`
	Page            int     `json:"page"`
	PageSize        int     `json:"page_size"`
}

// SetDefaults sets default values for the search query.
func (q *FactorSearchQuery) SetDefaults() {
	if q.OrderBy == "" {
		q.OrderBy = "name"
	}
	if q.Page <= 0 {
		q.Page = 1
	}
	if q.PageSize <= 0 {
		q.PageSize = 20
	}
	if q.PageSize > 100 {
		q.PageSize = 100
	}
}

// Offset returns the offset for pagination.
func (q *FactorSearchQuery) Offset() int {
	return (q.Page - 1) * q.PageSize
}

// CategoryStats represents statistics grouped by category.
type CategoryStats map[string]int
