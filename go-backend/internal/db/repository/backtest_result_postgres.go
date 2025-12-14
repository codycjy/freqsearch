package repository

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/saltfish/freqsearch/go-backend/internal/db"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// backtestResultRepo implements BacktestResultRepository using PostgreSQL.
type backtestResultRepo struct {
	pool *db.Pool
}

// NewBacktestResultRepository creates a new PostgreSQL backtest result repository.
func NewBacktestResultRepository(pool *db.Pool) BacktestResultRepository {
	return &backtestResultRepo{pool: pool}
}

// Create creates a new backtest result.
func (r *backtestResultRepo) Create(ctx context.Context, result *domain.BacktestResult) error {
	pairResultsJSON, err := json.Marshal(result.PairResults)
	if err != nil {
		return fmt.Errorf("failed to marshal pair_results: %w", err)
	}

	query := `
		INSERT INTO backtest_results (
			id, job_id, strategy_id,
			total_trades, winning_trades, losing_trades, win_rate,
			profit_total, profit_pct, profit_factor,
			max_drawdown, max_drawdown_pct, sharpe_ratio, sortino_ratio, calmar_ratio,
			avg_trade_duration_minutes, avg_profit_per_trade, best_trade_pct, worst_trade_pct,
			pair_results, raw_log, created_at
		) VALUES (
			$1, $2, $3,
			$4, $5, $6, $7,
			$8, $9, $10,
			$11, $12, $13, $14, $15,
			$16, $17, $18, $19,
			$20, $21, $22
		)
	`

	_, err = r.pool.Exec(ctx, query,
		result.ID,
		result.JobID,
		result.StrategyID,
		result.TotalTrades,
		result.WinningTrades,
		result.LosingTrades,
		result.WinRate,
		result.ProfitTotal,
		result.ProfitPct,
		result.ProfitFactor,
		result.MaxDrawdown,
		result.MaxDrawdownPct,
		result.SharpeRatio,
		result.SortinoRatio,
		result.CalmarRatio,
		result.AvgTradeDurationMinutes,
		result.AvgProfitPerTrade,
		result.BestTradePct,
		result.WorstTradePct,
		pairResultsJSON,
		result.RawLog,
		result.CreatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to create backtest result: %w", err)
	}

	return nil
}

// GetByID retrieves a result by ID.
func (r *backtestResultRepo) GetByID(ctx context.Context, id uuid.UUID) (*domain.BacktestResult, error) {
	query := `
		SELECT
			id, job_id, strategy_id,
			total_trades, winning_trades, losing_trades, win_rate,
			profit_total, profit_pct, profit_factor,
			max_drawdown, max_drawdown_pct, sharpe_ratio, sortino_ratio, calmar_ratio,
			avg_trade_duration_minutes, avg_profit_per_trade, best_trade_pct, worst_trade_pct,
			pair_results, raw_log, created_at
		FROM backtest_results
		WHERE id = $1
	`

	return r.scanResult(r.pool.QueryRow(ctx, query, id))
}

// GetByJobID retrieves a result by job ID.
func (r *backtestResultRepo) GetByJobID(ctx context.Context, jobID uuid.UUID) (*domain.BacktestResult, error) {
	query := `
		SELECT
			id, job_id, strategy_id,
			total_trades, winning_trades, losing_trades, win_rate,
			profit_total, profit_pct, profit_factor,
			max_drawdown, max_drawdown_pct, sharpe_ratio, sortino_ratio, calmar_ratio,
			avg_trade_duration_minutes, avg_profit_per_trade, best_trade_pct, worst_trade_pct,
			pair_results, raw_log, created_at
		FROM backtest_results
		WHERE job_id = $1
	`

	return r.scanResult(r.pool.QueryRow(ctx, query, jobID))
}

// GetByStrategyID retrieves all results for a strategy.
func (r *backtestResultRepo) GetByStrategyID(ctx context.Context, strategyID uuid.UUID) ([]*domain.BacktestResult, error) {
	query := `
		SELECT
			id, job_id, strategy_id,
			total_trades, winning_trades, losing_trades, win_rate,
			profit_total, profit_pct, profit_factor,
			max_drawdown, max_drawdown_pct, sharpe_ratio, sortino_ratio, calmar_ratio,
			avg_trade_duration_minutes, avg_profit_per_trade, best_trade_pct, worst_trade_pct,
			pair_results, raw_log, created_at
		FROM backtest_results
		WHERE strategy_id = $1
		ORDER BY created_at DESC
	`

	rows, err := r.pool.Query(ctx, query, strategyID)
	if err != nil {
		return nil, fmt.Errorf("failed to query results by strategy: %w", err)
	}
	defer rows.Close()

	return r.scanResults(rows)
}

// Query queries results with filters and pagination.
func (r *backtestResultRepo) Query(
	ctx context.Context,
	query domain.BacktestResultQuery,
) ([]*domain.BacktestResult, int, error) {
	query.SetDefaults()

	var conditions []string
	var args []interface{}
	argNum := 1

	// Build WHERE conditions
	if query.StrategyID != nil {
		conditions = append(conditions, fmt.Sprintf("br.strategy_id = $%d", argNum))
		args = append(args, *query.StrategyID)
		argNum++
	}

	if query.OptimizationRunID != nil {
		conditions = append(conditions, fmt.Sprintf("bj.optimization_run_id = $%d", argNum))
		args = append(args, *query.OptimizationRunID)
		argNum++
	}

	if query.MinSharpe != nil {
		conditions = append(conditions, fmt.Sprintf("br.sharpe_ratio >= $%d", argNum))
		args = append(args, *query.MinSharpe)
		argNum++
	}

	if query.MinProfitPct != nil {
		conditions = append(conditions, fmt.Sprintf("br.profit_pct >= $%d", argNum))
		args = append(args, *query.MinProfitPct)
		argNum++
	}

	if query.MaxDrawdownPct != nil {
		conditions = append(conditions, fmt.Sprintf("br.max_drawdown_pct <= $%d", argNum))
		args = append(args, *query.MaxDrawdownPct)
		argNum++
	}

	if query.MinTrades != nil {
		conditions = append(conditions, fmt.Sprintf("br.total_trades >= $%d", argNum))
		args = append(args, *query.MinTrades)
		argNum++
	}

	if query.TimeRange != nil {
		conditions = append(conditions, fmt.Sprintf("br.created_at >= $%d", argNum))
		args = append(args, query.TimeRange.Start)
		argNum++
		conditions = append(conditions, fmt.Sprintf("br.created_at <= $%d", argNum))
		args = append(args, query.TimeRange.End)
		argNum++
	}

	whereClause := ""
	if len(conditions) > 0 {
		whereClause = "WHERE " + strings.Join(conditions, " AND ")
	}

	// Determine ORDER BY clause
	orderColumn := "br.created_at"
	switch query.OrderBy {
	case "sharpe":
		orderColumn = "br.sharpe_ratio"
	case "profit":
		orderColumn = "br.profit_pct"
	case "created_at":
		orderColumn = "br.created_at"
	}

	orderDir := "DESC"
	if query.Ascending {
		orderDir = "ASC"
	}

	// Handle NULL values for sharpe_ratio ordering
	nullsOrder := ""
	if orderColumn == "br.sharpe_ratio" {
		if query.Ascending {
			nullsOrder = " NULLS FIRST"
		} else {
			nullsOrder = " NULLS LAST"
		}
	}

	// Count total
	countQuery := fmt.Sprintf(`
		SELECT COUNT(*)
		FROM backtest_results br
		LEFT JOIN backtest_jobs bj ON br.job_id = bj.id
		%s
	`, whereClause)

	var totalCount int
	err := r.pool.QueryRow(ctx, countQuery, args...).Scan(&totalCount)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to count results: %w", err)
	}

	// Query results
	selectQuery := fmt.Sprintf(`
		SELECT
			br.id, br.job_id, br.strategy_id,
			br.total_trades, br.winning_trades, br.losing_trades, br.win_rate,
			br.profit_total, br.profit_pct, br.profit_factor,
			br.max_drawdown, br.max_drawdown_pct, br.sharpe_ratio, br.sortino_ratio, br.calmar_ratio,
			br.avg_trade_duration_minutes, br.avg_profit_per_trade, br.best_trade_pct, br.worst_trade_pct,
			br.pair_results, br.raw_log, br.created_at
		FROM backtest_results br
		LEFT JOIN backtest_jobs bj ON br.job_id = bj.id
		%s
		ORDER BY %s %s%s
		LIMIT $%d OFFSET $%d
	`, whereClause, orderColumn, orderDir, nullsOrder, argNum, argNum+1)

	args = append(args, query.PageSize, query.Offset())

	rows, err := r.pool.Query(ctx, selectQuery, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to query results: %w", err)
	}
	defer rows.Close()

	results, err := r.scanResults(rows)
	if err != nil {
		return nil, 0, err
	}

	return results, totalCount, nil
}

// GetBestByStrategyID retrieves the best result for a strategy based on sharpe ratio.
func (r *backtestResultRepo) GetBestByStrategyID(ctx context.Context, strategyID uuid.UUID) (*domain.BacktestResult, error) {
	query := `
		SELECT
			id, job_id, strategy_id,
			total_trades, winning_trades, losing_trades, win_rate,
			profit_total, profit_pct, profit_factor,
			max_drawdown, max_drawdown_pct, sharpe_ratio, sortino_ratio, calmar_ratio,
			avg_trade_duration_minutes, avg_profit_per_trade, best_trade_pct, worst_trade_pct,
			pair_results, raw_log, created_at
		FROM backtest_results
		WHERE strategy_id = $1 AND sharpe_ratio IS NOT NULL
		ORDER BY sharpe_ratio DESC
		LIMIT 1
	`

	return r.scanResult(r.pool.QueryRow(ctx, query, strategyID))
}

// scanResult scans a single row into a BacktestResult.
func (r *backtestResultRepo) scanResult(row pgx.Row) (*domain.BacktestResult, error) {
	result := &domain.BacktestResult{}
	var pairResultsJSON []byte

	err := row.Scan(
		&result.ID,
		&result.JobID,
		&result.StrategyID,
		&result.TotalTrades,
		&result.WinningTrades,
		&result.LosingTrades,
		&result.WinRate,
		&result.ProfitTotal,
		&result.ProfitPct,
		&result.ProfitFactor,
		&result.MaxDrawdown,
		&result.MaxDrawdownPct,
		&result.SharpeRatio,
		&result.SortinoRatio,
		&result.CalmarRatio,
		&result.AvgTradeDurationMinutes,
		&result.AvgProfitPerTrade,
		&result.BestTradePct,
		&result.WorstTradePct,
		&pairResultsJSON,
		&result.RawLog,
		&result.CreatedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, domain.ErrNotFound
		}
		return nil, fmt.Errorf("failed to scan result row: %w", err)
	}

	if pairResultsJSON != nil {
		if err := json.Unmarshal(pairResultsJSON, &result.PairResults); err != nil {
			return nil, fmt.Errorf("failed to unmarshal pair_results: %w", err)
		}
	}

	return result, nil
}

// scanResults scans multiple rows into a slice of BacktestResult.
func (r *backtestResultRepo) scanResults(rows pgx.Rows) ([]*domain.BacktestResult, error) {
	var results []*domain.BacktestResult

	for rows.Next() {
		result := &domain.BacktestResult{}
		var pairResultsJSON []byte

		err := rows.Scan(
			&result.ID,
			&result.JobID,
			&result.StrategyID,
			&result.TotalTrades,
			&result.WinningTrades,
			&result.LosingTrades,
			&result.WinRate,
			&result.ProfitTotal,
			&result.ProfitPct,
			&result.ProfitFactor,
			&result.MaxDrawdown,
			&result.MaxDrawdownPct,
			&result.SharpeRatio,
			&result.SortinoRatio,
			&result.CalmarRatio,
			&result.AvgTradeDurationMinutes,
			&result.AvgProfitPerTrade,
			&result.BestTradePct,
			&result.WorstTradePct,
			&pairResultsJSON,
			&result.RawLog,
			&result.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan result row: %w", err)
		}

		if pairResultsJSON != nil {
			if err := json.Unmarshal(pairResultsJSON, &result.PairResults); err != nil {
				return nil, fmt.Errorf("failed to unmarshal pair_results: %w", err)
			}
		}

		results = append(results, result)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating result rows: %w", err)
	}

	return results, nil
}
