package domain

import "errors"

// Common domain errors.
var (
	// ErrNotFound is returned when a resource is not found.
	ErrNotFound = errors.New("resource not found")

	// ErrDuplicate is returned when a duplicate resource is detected.
	ErrDuplicate = errors.New("duplicate resource")

	// ErrInvalidInput is returned when input validation fails.
	ErrInvalidInput = errors.New("invalid input")

	// ErrConflict is returned when there is a conflict (e.g., state transition error).
	ErrConflict = errors.New("conflict")

	// ErrJobAlreadyRunning is returned when trying to start a job that's already running.
	ErrJobAlreadyRunning = errors.New("job is already running")

	// ErrJobNotCancellable is returned when trying to cancel a job that cannot be cancelled.
	ErrJobNotCancellable = errors.New("job cannot be cancelled")

	// ErrOptimizationNotRunning is returned when trying to pause/resume a non-running optimization.
	ErrOptimizationNotRunning = errors.New("optimization is not running")

	// ErrStrategyInUse is returned when trying to delete a strategy that is in use.
	ErrStrategyInUse = errors.New("strategy is in use")
)

// NotFoundError wraps ErrNotFound with additional context.
type NotFoundError struct {
	Resource string
	ID       string
}

func (e NotFoundError) Error() string {
	return e.Resource + " not found: " + e.ID
}

func (e NotFoundError) Unwrap() error {
	return ErrNotFound
}

// NewNotFoundError creates a new NotFoundError.
func NewNotFoundError(resource, id string) NotFoundError {
	return NotFoundError{Resource: resource, ID: id}
}

// DuplicateError wraps ErrDuplicate with additional context.
type DuplicateError struct {
	Resource string
	Field    string
	Value    string
}

func (e DuplicateError) Error() string {
	return e.Resource + " with " + e.Field + " '" + e.Value + "' already exists"
}

func (e DuplicateError) Unwrap() error {
	return ErrDuplicate
}

// NewDuplicateError creates a new DuplicateError.
func NewDuplicateError(resource, field, value string) DuplicateError {
	return DuplicateError{Resource: resource, Field: field, Value: value}
}
