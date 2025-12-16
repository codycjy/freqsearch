package domain

import (
	"time"

	"github.com/google/uuid"
)

// =====================================================
// ENUMS
// =====================================================

// ScoutRunStatus represents the status of a Scout agent run.
type ScoutRunStatus string

const (
	ScoutRunStatusPending   ScoutRunStatus = "pending"
	ScoutRunStatusRunning   ScoutRunStatus = "running"
	ScoutRunStatusCompleted ScoutRunStatus = "completed"
	ScoutRunStatusFailed    ScoutRunStatus = "failed"
	ScoutRunStatusCancelled ScoutRunStatus = "cancelled"
)

// IsValid returns true if the status is a valid ScoutRunStatus.
func (s ScoutRunStatus) IsValid() bool {
	switch s {
	case ScoutRunStatusPending, ScoutRunStatusRunning, ScoutRunStatusCompleted,
		ScoutRunStatusFailed, ScoutRunStatusCancelled:
		return true
	default:
		return false
	}
}

// IsTerminal returns true if the status is terminal (no further transitions).
func (s ScoutRunStatus) IsTerminal() bool {
	return s == ScoutRunStatusCompleted || s == ScoutRunStatusFailed || s == ScoutRunStatusCancelled
}

// String returns the string representation of the status.
func (s ScoutRunStatus) String() string {
	return string(s)
}

// ScoutRunStatusFromString converts a string to ScoutRunStatus.
func ScoutRunStatusFromString(s string) ScoutRunStatus {
	status := ScoutRunStatus(s)
	if status.IsValid() {
		return status
	}
	return ScoutRunStatusPending
}

// ScoutTriggerType represents how a Scout run was triggered.
type ScoutTriggerType string

const (
	ScoutTriggerTypeManual    ScoutTriggerType = "manual"
	ScoutTriggerTypeScheduled ScoutTriggerType = "scheduled"
	ScoutTriggerTypeEvent     ScoutTriggerType = "event"
)

// IsValid returns true if the trigger type is valid.
func (t ScoutTriggerType) IsValid() bool {
	switch t {
	case ScoutTriggerTypeManual, ScoutTriggerTypeScheduled, ScoutTriggerTypeEvent:
		return true
	default:
		return false
	}
}

// String returns the string representation of the trigger type.
func (t ScoutTriggerType) String() string {
	return string(t)
}

// ScoutTriggerTypeFromString converts a string to ScoutTriggerType.
func ScoutTriggerTypeFromString(s string) ScoutTriggerType {
	triggerType := ScoutTriggerType(s)
	if triggerType.IsValid() {
		return triggerType
	}
	return ScoutTriggerTypeManual
}

// =====================================================
// DOMAIN MODELS
// =====================================================

// ScoutRun represents a single Scout agent execution run.
type ScoutRun struct {
	ID            uuid.UUID        `json:"id"`
	TriggerType   ScoutTriggerType `json:"trigger_type"`
	TriggeredBy   string           `json:"triggered_by,omitempty"`
	Source        string           `json:"source"`
	MaxStrategies int              `json:"max_strategies"`
	Status        ScoutRunStatus   `json:"status"`
	ErrorMessage  *string          `json:"error_message,omitempty"`
	Metrics       *ScoutMetrics    `json:"metrics,omitempty"`
	CreatedAt     time.Time        `json:"created_at"`
	StartedAt     *time.Time       `json:"started_at,omitempty"`
	CompletedAt   *time.Time       `json:"completed_at,omitempty"`
}

// NewScoutRun creates a new Scout run with generated UUID.
func NewScoutRun(triggerType ScoutTriggerType, triggeredBy, source string, maxStrategies int) *ScoutRun {
	return &ScoutRun{
		ID:            uuid.New(),
		TriggerType:   triggerType,
		TriggeredBy:   triggeredBy,
		Source:        source,
		MaxStrategies: maxStrategies,
		Status:        ScoutRunStatusPending,
		Metrics:       &ScoutMetrics{},
		CreatedAt:     time.Now(),
	}
}

// Duration returns the duration of the Scout run.
func (r *ScoutRun) Duration() time.Duration {
	if r.StartedAt == nil {
		return 0
	}
	end := time.Now()
	if r.CompletedAt != nil {
		end = *r.CompletedAt
	}
	return end.Sub(*r.StartedAt)
}

// IsComplete returns true if the Scout run is in a terminal state.
func (r *ScoutRun) IsComplete() bool {
	return r.Status.IsTerminal()
}

// ScoutMetrics represents metrics collected during a Scout run.
type ScoutMetrics struct {
	TotalFetched       int `json:"total_fetched"`
	Validated          int `json:"validated"`
	ValidationFailed   int `json:"validation_failed"`
	DuplicatesRemoved  int `json:"duplicates_removed"`
	Submitted          int `json:"submitted"`
}

// ValidationRate returns the percentage of strategies that passed validation.
func (m *ScoutMetrics) ValidationRate() float64 {
	if m.TotalFetched == 0 {
		return 0.0
	}
	return float64(m.Validated) / float64(m.TotalFetched) * 100.0
}

// SubmissionRate returns the percentage of validated strategies that were submitted.
func (m *ScoutMetrics) SubmissionRate() float64 {
	if m.Validated == 0 {
		return 0.0
	}
	return float64(m.Submitted) / float64(m.Validated) * 100.0
}

// ScoutSchedule represents a cron-based schedule for automatic Scout runs.
type ScoutSchedule struct {
	ID             uuid.UUID  `json:"id"`
	Name           string     `json:"name"`
	CronExpression string     `json:"cron_expression"`
	Source         string     `json:"source"`
	MaxStrategies  int        `json:"max_strategies"`
	Enabled        bool       `json:"enabled"`
	LastRunID      *uuid.UUID `json:"last_run_id,omitempty"`
	LastRunAt      *time.Time `json:"last_run_at,omitempty"`
	NextRunAt      *time.Time `json:"next_run_at,omitempty"`
	CreatedAt      time.Time  `json:"created_at"`
	UpdatedAt      time.Time  `json:"updated_at"`
}

// NewScoutSchedule creates a new Scout schedule with generated UUID.
func NewScoutSchedule(name, cronExpression, source string, maxStrategies int) *ScoutSchedule {
	now := time.Now()
	return &ScoutSchedule{
		ID:             uuid.New(),
		Name:           name,
		CronExpression: cronExpression,
		Source:         source,
		MaxStrategies:  maxStrategies,
		Enabled:        true,
		CreatedAt:      now,
		UpdatedAt:      now,
	}
}

// IsDue returns true if the schedule is due to run.
func (s *ScoutSchedule) IsDue() bool {
	if !s.Enabled || s.NextRunAt == nil {
		return false
	}
	return s.NextRunAt.Before(time.Now()) || s.NextRunAt.Equal(time.Now())
}

// =====================================================
// QUERY MODELS
// =====================================================

// ScoutRunQuery represents query parameters for listing Scout runs.
type ScoutRunQuery struct {
	Status    *ScoutRunStatus `json:"status,omitempty"`
	Source    *string         `json:"source,omitempty"`
	TimeRange *TimeRange      `json:"time_range,omitempty"`
	OrderBy   string          `json:"order_by,omitempty"`
	Ascending bool            `json:"ascending,omitempty"`
	Page      int             `json:"page"`
	PageSize  int             `json:"page_size"`
}

// SetDefaults sets default values for the query.
func (q *ScoutRunQuery) SetDefaults() {
	if q.OrderBy == "" {
		q.OrderBy = "created_at"
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
func (q *ScoutRunQuery) Offset() int {
	return (q.Page - 1) * q.PageSize
}

// ScoutScheduleQuery represents query parameters for listing Scout schedules.
type ScoutScheduleQuery struct {
	Enabled   *bool      `json:"enabled,omitempty"`
	Source    *string    `json:"source,omitempty"`
	TimeRange *TimeRange `json:"time_range,omitempty"`
	OrderBy   string     `json:"order_by,omitempty"`
	Ascending bool       `json:"ascending,omitempty"`
	Page      int        `json:"page"`
	PageSize  int        `json:"page_size"`
}

// SetDefaults sets default values for the query.
func (q *ScoutScheduleQuery) SetDefaults() {
	if q.OrderBy == "" {
		q.OrderBy = "created_at"
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
func (q *ScoutScheduleQuery) Offset() int {
	return (q.Page - 1) * q.PageSize
}
