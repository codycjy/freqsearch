package repository

import (
	"context"
	"fmt"
	"os"
	"testing"

	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/config"
	"github.com/saltfish/freqsearch/go-backend/internal/db"
)

// setupTestDB creates a test database connection pool for integration tests.
// It reads database configuration from environment variables.
// If the required variables are not set, the test will be skipped.
func setupTestDB(t *testing.T) *db.Pool {
	t.Helper()

	// Check for test database URL
	dbURL := os.Getenv("TEST_DATABASE_URL")
	if dbURL == "" {
		dbURL = os.Getenv("DATABASE_URL")
	}
	if dbURL == "" {
		t.Skip("TEST_DATABASE_URL or DATABASE_URL not set, skipping integration test")
	}

	// Create a test config from the database URL
	cfg := &config.DatabaseConfig{
		Host:               os.Getenv("DB_HOST"),
		Port:               5432,
		User:               os.Getenv("DB_USER"),
		Password:           os.Getenv("DB_PASSWORD"),
		Name:               os.Getenv("DB_NAME"),
		MaxConnections:     10,
		MaxIdleConnections: 5,
		ConnMaxLifetime:    "1h",
	}

	// If using DATABASE_URL, just set defaults
	if cfg.Host == "" {
		cfg.Host = "localhost"
		cfg.User = "postgres"
		cfg.Password = "postgres"
		cfg.Name = "freqsearch_test"
	}

	// Create a test logger (no-op logger for tests)
	logger := zap.NewNop()

	pool, err := db.NewPool(context.Background(), cfg, logger)
	if err != nil {
		t.Fatalf("failed to create test database pool: %v", err)
	}

	// Clean up function to close pool on test completion
	t.Cleanup(func() {
		pool.Close()
	})

	return pool
}

// truncateTables truncates all test tables to ensure a clean state.
func truncateTables(t *testing.T, pool *db.Pool, tables ...string) {
	t.Helper()

	ctx := context.Background()
	for _, table := range tables {
		query := fmt.Sprintf("TRUNCATE TABLE %s CASCADE", table)
		if _, err := pool.Exec(ctx, query); err != nil {
			t.Logf("warning: failed to truncate table %s: %v", table, err)
		}
	}
}
