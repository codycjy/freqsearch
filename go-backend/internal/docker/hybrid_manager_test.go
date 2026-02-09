package docker

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.uber.org/zap/zaptest"

	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// mockManager is a mock implementation of the Manager interface for testing.
type mockManager struct {
	mock.Mock
}

func (m *mockManager) RunBacktest(ctx context.Context, params *RunBacktestParams) (string, error) {
	args := m.Called(ctx, params)
	return args.String(0), args.Error(1)
}

func (m *mockManager) ValidateStrategy(ctx context.Context, params *ValidateStrategyParams) (*ValidationResult, error) {
	args := m.Called(ctx, params)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*ValidationResult), args.Error(1)
}

func (m *mockManager) WaitContainer(ctx context.Context, containerID string) (int64, string, error) {
	args := m.Called(ctx, containerID)
	return args.Get(0).(int64), args.String(1), args.Error(2)
}

func (m *mockManager) StopContainer(ctx context.Context, containerID string) error {
	args := m.Called(ctx, containerID)
	return args.Error(0)
}

func (m *mockManager) RemoveContainer(ctx context.Context, containerID string) error {
	args := m.Called(ctx, containerID)
	return args.Error(0)
}

func (m *mockManager) GetContainerLogs(ctx context.Context, containerID string) (string, error) {
	args := m.Called(ctx, containerID)
	return args.String(0), args.Error(1)
}

func (m *mockManager) CleanupStaleContainers(ctx context.Context, maxAge time.Duration) (int, error) {
	args := m.Called(ctx, maxAge)
	return args.Int(0), args.Error(1)
}

func (m *mockManager) IsContainerRunning(ctx context.Context, containerID string) (bool, error) {
	args := m.Called(ctx, containerID)
	return args.Bool(0), args.Error(1)
}

func TestHybridManager_RunBacktest_UsesLocalWhenAvailable(t *testing.T) {
	localMgr := new(mockManager)
	remoteMgr := new(mockManager)
	logger := zaptest.NewLogger(t)

	hybrid := NewHybridManager(localMgr, remoteMgr, 2, logger).(*hybridManager)

	params := &RunBacktestParams{
		JobID:        uuid.New(),
		StrategyCode: "test code",
		StrategyName: "TestStrategy",
		Config:       domain.BacktestConfig{},
	}

	localMgr.On("RunBacktest", mock.Anything, params).Return("container123", nil)

	containerID, err := hybrid.RunBacktest(context.Background(), params)

	assert.NoError(t, err)
	assert.Equal(t, "local:container123", containerID)
	assert.Equal(t, int32(1), hybrid.activeLocal.Load())
	localMgr.AssertExpectations(t)
	remoteMgr.AssertExpectations(t)
}

func TestHybridManager_RunBacktest_UsesRemoteWhenLocalFull(t *testing.T) {
	localMgr := new(mockManager)
	remoteMgr := new(mockManager)
	logger := zaptest.NewLogger(t)

	hybrid := NewHybridManager(localMgr, remoteMgr, 1, logger).(*hybridManager)

	// First job uses local
	params1 := &RunBacktestParams{
		JobID:        uuid.New(),
		StrategyCode: "test code 1",
		StrategyName: "TestStrategy1",
		Config:       domain.BacktestConfig{},
	}
	localMgr.On("RunBacktest", mock.Anything, params1).Return("local123", nil)

	containerID1, err := hybrid.RunBacktest(context.Background(), params1)
	assert.NoError(t, err)
	assert.Equal(t, "local:local123", containerID1)
	assert.Equal(t, int32(1), hybrid.activeLocal.Load())

	// Second job should use remote
	params2 := &RunBacktestParams{
		JobID:        uuid.New(),
		StrategyCode: "test code 2",
		StrategyName: "TestStrategy2",
		Config:       domain.BacktestConfig{},
	}
	remoteMgr.On("RunBacktest", mock.Anything, params2).Return("aci456", nil)

	containerID2, err := hybrid.RunBacktest(context.Background(), params2)
	assert.NoError(t, err)
	assert.Equal(t, "aci:aci456", containerID2)
	assert.Equal(t, int32(1), hybrid.activeLocal.Load()) // Still 1 from first job

	localMgr.AssertExpectations(t)
	remoteMgr.AssertExpectations(t)
}

func TestHybridManager_WaitContainer_DecrementsLocalCounter(t *testing.T) {
	localMgr := new(mockManager)
	remoteMgr := new(mockManager)
	logger := zaptest.NewLogger(t)

	hybrid := NewHybridManager(localMgr, remoteMgr, 2, logger).(*hybridManager)

	// Simulate a running local container
	hybrid.activeLocal.Add(1)
	assert.Equal(t, int32(1), hybrid.activeLocal.Load())

	localMgr.On("WaitContainer", mock.Anything, "container123").Return(int64(0), "logs", nil)

	exitCode, logs, err := hybrid.WaitContainer(context.Background(), "local:container123")

	assert.NoError(t, err)
	assert.Equal(t, int64(0), exitCode)
	assert.Equal(t, "logs", logs)
	assert.Equal(t, int32(0), hybrid.activeLocal.Load()) // Decremented
	localMgr.AssertExpectations(t)
}

func TestHybridManager_WaitContainer_DoesNotDecrementRemoteCounter(t *testing.T) {
	localMgr := new(mockManager)
	remoteMgr := new(mockManager)
	logger := zaptest.NewLogger(t)

	hybrid := NewHybridManager(localMgr, remoteMgr, 2, logger).(*hybridManager)

	// Simulate some local jobs
	hybrid.activeLocal.Add(1)
	assert.Equal(t, int32(1), hybrid.activeLocal.Load())

	remoteMgr.On("WaitContainer", mock.Anything, "aci456").Return(int64(0), "remote logs", nil)

	exitCode, logs, err := hybrid.WaitContainer(context.Background(), "aci:aci456")

	assert.NoError(t, err)
	assert.Equal(t, int64(0), exitCode)
	assert.Equal(t, "remote logs", logs)
	assert.Equal(t, int32(1), hybrid.activeLocal.Load()) // Unchanged
	remoteMgr.AssertExpectations(t)
}

func TestParseContainerID(t *testing.T) {
	tests := []struct {
		name           string
		input          string
		expectBackend  string
		expectRealID   string
	}{
		{
			name:          "local prefix",
			input:         "local:abc123",
			expectBackend: "local",
			expectRealID:  "abc123",
		},
		{
			name:          "aci prefix",
			input:         "aci:xyz789",
			expectBackend: "aci",
			expectRealID:  "xyz789",
		},
		{
			name:          "legacy no prefix",
			input:         "container123",
			expectBackend: "local",
			expectRealID:  "container123",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			backend, realID := parseContainerID(tt.input)
			assert.Equal(t, tt.expectBackend, backend)
			assert.Equal(t, tt.expectRealID, realID)
		})
	}
}

func TestHybridManager_RemoveContainer_DecrementsIfRunning(t *testing.T) {
	localMgr := new(mockManager)
	remoteMgr := new(mockManager)
	logger := zaptest.NewLogger(t)

	hybrid := NewHybridManager(localMgr, remoteMgr, 2, logger).(*hybridManager)

	// Simulate a running local container
	hybrid.activeLocal.Add(1)
	assert.Equal(t, int32(1), hybrid.activeLocal.Load())

	localMgr.On("IsContainerRunning", mock.Anything, "container123").Return(true, nil)
	localMgr.On("RemoveContainer", mock.Anything, "container123").Return(nil)

	err := hybrid.RemoveContainer(context.Background(), "local:container123")

	assert.NoError(t, err)
	assert.Equal(t, int32(0), hybrid.activeLocal.Load()) // Decremented
	localMgr.AssertExpectations(t)
}

func TestHybridManager_CleanupStaleContainers_CallsBothBackends(t *testing.T) {
	localMgr := new(mockManager)
	remoteMgr := new(mockManager)
	logger := zaptest.NewLogger(t)

	hybrid := NewHybridManager(localMgr, remoteMgr, 2, logger)

	maxAge := 24 * time.Hour

	localMgr.On("CleanupStaleContainers", mock.Anything, maxAge).Return(3, nil)
	remoteMgr.On("CleanupStaleContainers", mock.Anything, maxAge).Return(2, nil)

	total, err := hybrid.CleanupStaleContainers(context.Background(), maxAge)

	assert.NoError(t, err)
	assert.Equal(t, 5, total)
	localMgr.AssertExpectations(t)
	remoteMgr.AssertExpectations(t)
}

func TestHybridManager_ValidateStrategy_UsesLocal(t *testing.T) {
	localMgr := new(mockManager)
	remoteMgr := new(mockManager)
	logger := zaptest.NewLogger(t)

	hybrid := NewHybridManager(localMgr, remoteMgr, 2, logger)

	params := &ValidateStrategyParams{
		StrategyCode: "test code",
		StrategyName: "TestStrategy",
	}

	expectedResult := &ValidationResult{
		Valid:     true,
		Errors:    []string{},
		Warnings:  []string{},
		ClassName: "TestStrategy",
	}

	localMgr.On("ValidateStrategy", mock.Anything, params).Return(expectedResult, nil)

	result, err := hybrid.ValidateStrategy(context.Background(), params)

	assert.NoError(t, err)
	assert.Equal(t, expectedResult, result)
	localMgr.AssertExpectations(t)
	remoteMgr.AssertNotCalled(t, "ValidateStrategy")
}
