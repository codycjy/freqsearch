// Package domain contains the core domain models for FreqSearch.
package domain

// JobStatus represents the status of a backtest job.
type JobStatus string

const (
	JobStatusPending   JobStatus = "pending"
	JobStatusRunning   JobStatus = "running"
	JobStatusCompleted JobStatus = "completed"
	JobStatusFailed    JobStatus = "failed"
	JobStatusCancelled JobStatus = "cancelled"
)

// IsTerminal returns true if the status is terminal (no further transitions).
func (s JobStatus) IsTerminal() bool {
	return s == JobStatusCompleted || s == JobStatusFailed || s == JobStatusCancelled
}

// IsValid returns true if the status is a valid JobStatus.
func (s JobStatus) IsValid() bool {
	switch s {
	case JobStatusPending, JobStatusRunning, JobStatusCompleted, JobStatusFailed, JobStatusCancelled:
		return true
	default:
		return false
	}
}

// String returns the string representation of the status.
func (s JobStatus) String() string {
	return string(s)
}

// JobStatusFromString converts a string to JobStatus.
func JobStatusFromString(s string) JobStatus {
	status := JobStatus(s)
	if status.IsValid() {
		return status
	}
	return JobStatusPending
}

// OptimizationStatus represents the status of an optimization run.
type OptimizationStatus string

const (
	OptimizationStatusPending   OptimizationStatus = "pending"
	OptimizationStatusRunning   OptimizationStatus = "running"
	OptimizationStatusPaused    OptimizationStatus = "paused"
	OptimizationStatusCompleted OptimizationStatus = "completed"
	OptimizationStatusFailed    OptimizationStatus = "failed"
	OptimizationStatusCancelled OptimizationStatus = "cancelled"
)

// IsTerminal returns true if the status is terminal.
func (s OptimizationStatus) IsTerminal() bool {
	return s == OptimizationStatusCompleted || s == OptimizationStatusFailed || s == OptimizationStatusCancelled
}

// IsValid returns true if the status is a valid OptimizationStatus.
func (s OptimizationStatus) IsValid() bool {
	switch s {
	case OptimizationStatusPending, OptimizationStatusRunning, OptimizationStatusPaused,
		OptimizationStatusCompleted, OptimizationStatusFailed, OptimizationStatusCancelled:
		return true
	default:
		return false
	}
}

// String returns the string representation of the status.
func (s OptimizationStatus) String() string {
	return string(s)
}

// OptimizationStatusFromString converts a string to OptimizationStatus.
func OptimizationStatusFromString(s string) OptimizationStatus {
	status := OptimizationStatus(s)
	if status.IsValid() {
		return status
	}
	return OptimizationStatusPending
}

// OptimizationMode represents the optimization goal.
type OptimizationMode string

const (
	OptimizationModeMaximizeSharpe   OptimizationMode = "maximize_sharpe"
	OptimizationModeMaximizeProfit   OptimizationMode = "maximize_profit"
	OptimizationModeMinimizeDrawdown OptimizationMode = "minimize_drawdown"
	OptimizationModeBalanced         OptimizationMode = "balanced"
)

// IsValid returns true if the mode is a valid OptimizationMode.
func (m OptimizationMode) IsValid() bool {
	switch m {
	case OptimizationModeMaximizeSharpe, OptimizationModeMaximizeProfit,
		OptimizationModeMinimizeDrawdown, OptimizationModeBalanced:
		return true
	default:
		return false
	}
}

// String returns the string representation of the mode.
func (m OptimizationMode) String() string {
	return string(m)
}

// OptimizationModeFromString converts a string to OptimizationMode.
func OptimizationModeFromString(s string) OptimizationMode {
	mode := OptimizationMode(s)
	if mode.IsValid() {
		return mode
	}
	return OptimizationModeBalanced
}

// ApprovalStatus represents the approval status of an optimization iteration.
type ApprovalStatus string

const (
	ApprovalStatusPending        ApprovalStatus = "pending"
	ApprovalStatusApproved       ApprovalStatus = "approved"
	ApprovalStatusRejected       ApprovalStatus = "rejected"
	ApprovalStatusNeedsIteration ApprovalStatus = "needs_iteration"
)

// IsValid returns true if the status is a valid ApprovalStatus.
func (s ApprovalStatus) IsValid() bool {
	switch s {
	case ApprovalStatusPending, ApprovalStatusApproved, ApprovalStatusRejected, ApprovalStatusNeedsIteration:
		return true
	default:
		return false
	}
}

// String returns the string representation of the status.
func (s ApprovalStatus) String() string {
	return string(s)
}

// ApprovalStatusFromString converts a string to ApprovalStatus.
func ApprovalStatusFromString(s string) ApprovalStatus {
	status := ApprovalStatus(s)
	if status.IsValid() {
		return status
	}
	return ApprovalStatusPending
}
