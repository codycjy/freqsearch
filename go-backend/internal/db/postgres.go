// Package db provides database connectivity and pool management.
package db

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"go.uber.org/zap"

	"github.com/saltfish/freqsearch/go-backend/internal/config"
)

// Pool wraps pgxpool.Pool with additional functionality.
type Pool struct {
	*pgxpool.Pool
	logger *zap.Logger
}

// NewPool creates a new database connection pool.
func NewPool(ctx context.Context, cfg *config.DatabaseConfig, logger *zap.Logger) (*Pool, error) {
	connString := cfg.ConnectionString()

	poolConfig, err := pgxpool.ParseConfig(connString)
	if err != nil {
		return nil, fmt.Errorf("failed to parse connection string: %w", err)
	}

	// Configure pool settings
	poolConfig.MaxConns = int32(cfg.MaxConnections)
	poolConfig.MinConns = int32(cfg.MaxIdleConnections)

	// Parse and set connection max lifetime
	if cfg.ConnMaxLifetime != "" {
		lifetime, err := time.ParseDuration(cfg.ConnMaxLifetime)
		if err != nil {
			return nil, fmt.Errorf("invalid conn_max_lifetime: %w", err)
		}
		poolConfig.MaxConnLifetime = lifetime
	}

	// Configure connection options
	poolConfig.ConnConfig.ConnectTimeout = 10 * time.Second

	// Create pool
	pool, err := pgxpool.NewWithConfig(ctx, poolConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create pool: %w", err)
	}

	// Verify connection
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	logger.Info("Database connection pool created",
		zap.String("host", cfg.Host),
		zap.Int("port", cfg.Port),
		zap.String("database", cfg.Name),
		zap.Int("max_connections", cfg.MaxConnections),
	)

	return &Pool{
		Pool:   pool,
		logger: logger,
	}, nil
}

// Ping checks if the database connection is alive.
func (p *Pool) Ping(ctx context.Context) error {
	return p.Pool.Ping(ctx)
}

// Close closes all connections in the pool.
func (p *Pool) Close() {
	p.Pool.Close()
	p.logger.Info("Database connection pool closed")
}

// Stats returns pool statistics.
func (p *Pool) Stats() *pgxpool.Stat {
	return p.Pool.Stat()
}

// HealthCheck performs a health check on the database.
func (p *Pool) HealthCheck(ctx context.Context) error {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	var result int
	err := p.Pool.QueryRow(ctx, "SELECT 1").Scan(&result)
	if err != nil {
		return fmt.Errorf("database health check failed: %w", err)
	}
	return nil
}

// Tx represents a database transaction wrapper.
type Tx struct {
	pgx.Tx
}

// BeginTx starts a new transaction.
func (p *Pool) BeginTx(ctx context.Context) (*Tx, error) {
	tx, err := p.Pool.Begin(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	return &Tx{Tx: tx}, nil
}

// Commit commits the transaction.
func (t *Tx) Commit(ctx context.Context) error {
	return t.Tx.Commit(ctx)
}

// Rollback rolls back the transaction.
func (t *Tx) Rollback(ctx context.Context) error {
	return t.Tx.Rollback(ctx)
}

// WithTx executes a function within a transaction.
// If the function returns an error, the transaction is rolled back.
// Otherwise, the transaction is committed.
func (p *Pool) WithTx(ctx context.Context, fn func(tx *Tx) error) error {
	tx, err := p.BeginTx(ctx)
	if err != nil {
		return err
	}

	defer func() {
		if r := recover(); r != nil {
			_ = tx.Rollback(ctx)
			panic(r)
		}
	}()

	if err := fn(tx); err != nil {
		if rbErr := tx.Rollback(ctx); rbErr != nil {
			p.logger.Error("Failed to rollback transaction",
				zap.Error(rbErr),
				zap.Error(err),
			)
		}
		return err
	}

	return tx.Commit(ctx)
}
