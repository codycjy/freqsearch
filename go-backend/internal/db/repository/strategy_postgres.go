package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/saltfish/freqsearch/go-backend/internal/db"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// strategyRepo implements StrategyRepository using PostgreSQL.
type strategyRepo struct {
	pool *db.Pool
}

// NewStrategyRepository creates a new PostgreSQL strategy repository.
func NewStrategyRepository(pool *db.Pool) StrategyRepository {
	return &strategyRepo{pool: pool}
}

func (r *strategyRepo) Create(ctx context.Context, strategy *domain.Strategy) error {
	indicators, _ := json.Marshal(strategy.Indicators)
	minimalROI, _ := json.Marshal(strategy.MinimalROI)

	query := `
		INSERT INTO strategies (
			id, name, code, parent_id, description,
			timeframe, stoploss, trailing_stop, trailing_stop_positive,
			trailing_stop_positive_offset, startup_candle_count,
			indicators, minimal_roi, created_at, updated_at
		) VALUES (
			$1, $2, $3, $4, $5,
			$6, $7, $8, $9,
			$10, $11,
			$12, $13, $14, $15
		)
		RETURNING code_hash, generation
	`

	err := r.pool.QueryRow(ctx, query,
		strategy.ID, strategy.Name, strategy.Code, strategy.ParentID, strategy.Description,
		strategy.Timeframe, strategy.Stoploss, strategy.TrailingStop, strategy.TrailingStopPositive,
		strategy.TrailingStopPositiveOffset, strategy.StartupCandleCount,
		indicators, minimalROI, strategy.CreatedAt, strategy.UpdatedAt,
	).Scan(&strategy.CodeHash, &strategy.Generation)

	if err != nil {
		if isDuplicateKeyError(err) {
			return domain.NewDuplicateError("strategy", "code_hash", "")
		}
		return fmt.Errorf("failed to create strategy: %w", err)
	}

	return nil
}

func (r *strategyRepo) GetByID(ctx context.Context, id uuid.UUID) (*domain.Strategy, error) {
	query := `
		SELECT
			id, name, code, code_hash, parent_id, generation, description,
			timeframe, stoploss, trailing_stop, trailing_stop_positive,
			trailing_stop_positive_offset, startup_candle_count,
			indicators, minimal_roi, created_at, updated_at
		FROM strategies
		WHERE id = $1
	`

	strategy := &domain.Strategy{}
	var indicators, minimalROI []byte

	err := r.pool.QueryRow(ctx, query, id).Scan(
		&strategy.ID, &strategy.Name, &strategy.Code, &strategy.CodeHash,
		&strategy.ParentID, &strategy.Generation, &strategy.Description,
		&strategy.Timeframe, &strategy.Stoploss, &strategy.TrailingStop,
		&strategy.TrailingStopPositive, &strategy.TrailingStopPositiveOffset,
		&strategy.StartupCandleCount, &indicators, &minimalROI,
		&strategy.CreatedAt, &strategy.UpdatedAt,
	)

	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, domain.NewNotFoundError("strategy", id.String())
		}
		return nil, fmt.Errorf("failed to get strategy: %w", err)
	}

	_ = json.Unmarshal(indicators, &strategy.Indicators)
	_ = json.Unmarshal(minimalROI, &strategy.MinimalROI)

	return strategy, nil
}

func (r *strategyRepo) GetByCodeHash(ctx context.Context, hash string) (*domain.Strategy, error) {
	query := `
		SELECT
			id, name, code, code_hash, parent_id, generation, description,
			timeframe, stoploss, trailing_stop, trailing_stop_positive,
			trailing_stop_positive_offset, startup_candle_count,
			indicators, minimal_roi, created_at, updated_at
		FROM strategies
		WHERE code_hash = $1
	`

	strategy := &domain.Strategy{}
	var indicators, minimalROI []byte

	err := r.pool.QueryRow(ctx, query, hash).Scan(
		&strategy.ID, &strategy.Name, &strategy.Code, &strategy.CodeHash,
		&strategy.ParentID, &strategy.Generation, &strategy.Description,
		&strategy.Timeframe, &strategy.Stoploss, &strategy.TrailingStop,
		&strategy.TrailingStopPositive, &strategy.TrailingStopPositiveOffset,
		&strategy.StartupCandleCount, &indicators, &minimalROI,
		&strategy.CreatedAt, &strategy.UpdatedAt,
	)

	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, domain.NewNotFoundError("strategy", "code_hash:"+hash)
		}
		return nil, fmt.Errorf("failed to get strategy by code hash: %w", err)
	}

	_ = json.Unmarshal(indicators, &strategy.Indicators)
	_ = json.Unmarshal(minimalROI, &strategy.MinimalROI)

	return strategy, nil
}

func (r *strategyRepo) Update(ctx context.Context, strategy *domain.Strategy) error {
	indicators, _ := json.Marshal(strategy.Indicators)
	minimalROI, _ := json.Marshal(strategy.MinimalROI)

	query := `
		UPDATE strategies SET
			name = $2, description = $3,
			timeframe = $4, stoploss = $5, trailing_stop = $6,
			trailing_stop_positive = $7, trailing_stop_positive_offset = $8,
			startup_candle_count = $9, indicators = $10, minimal_roi = $11
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query,
		strategy.ID, strategy.Name, strategy.Description,
		strategy.Timeframe, strategy.Stoploss, strategy.TrailingStop,
		strategy.TrailingStopPositive, strategy.TrailingStopPositiveOffset,
		strategy.StartupCandleCount, indicators, minimalROI,
	)

	if err != nil {
		return fmt.Errorf("failed to update strategy: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("strategy", strategy.ID.String())
	}

	return nil
}

func (r *strategyRepo) Delete(ctx context.Context, id uuid.UUID) error {
	result, err := r.pool.Exec(ctx, "DELETE FROM strategies WHERE id = $1", id)
	if err != nil {
		// Check for foreign key violation (strategy in use)
		if isForeignKeyViolation(err) {
			return domain.ErrStrategyInUse
		}
		return fmt.Errorf("failed to delete strategy: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("strategy", id.String())
	}

	return nil
}

func (r *strategyRepo) Search(ctx context.Context, query domain.StrategySearchQuery) ([]domain.StrategyWithMetrics, int, error) {
	query.SetDefaults()

	// Build dynamic query
	var conditions []string
	var args []interface{}
	argIndex := 1

	baseQuery := `
		WITH strategy_metrics AS (
			SELECT
				s.id,
				s.name,
				s.code_hash,
				s.parent_id,
				s.generation,
				s.description,
				s.timeframe,
				s.stoploss,
				s.trailing_stop,
				s.created_at,
				s.updated_at,
				COUNT(br.id) as backtest_count,
				MAX(br.sharpe_ratio) as best_sharpe,
				MAX(br.profit_pct) as best_profit_pct,
				MIN(br.max_drawdown_pct) as best_drawdown,
				MAX(br.total_trades) as max_trades,
				AVG(br.win_rate) as avg_win_rate
			FROM strategies s
			LEFT JOIN backtest_results br ON br.strategy_id = s.id
			%s
			GROUP BY s.id
		)
	`

	// WHERE conditions
	if query.NamePattern != nil && *query.NamePattern != "" {
		conditions = append(conditions, fmt.Sprintf("s.name ILIKE $%d", argIndex))
		args = append(args, "%"+*query.NamePattern+"%")
		argIndex++
	}

	if query.MinGeneration != nil {
		conditions = append(conditions, fmt.Sprintf("s.generation >= $%d", argIndex))
		args = append(args, *query.MinGeneration)
		argIndex++
	}

	if query.MaxGeneration != nil {
		conditions = append(conditions, fmt.Sprintf("s.generation <= $%d", argIndex))
		args = append(args, *query.MaxGeneration)
		argIndex++
	}

	if query.ParentID != nil && *query.ParentID != "" {
		conditions = append(conditions, fmt.Sprintf("s.parent_id = $%d", argIndex))
		args = append(args, *query.ParentID)
		argIndex++
	}

	whereClause := ""
	if len(conditions) > 0 {
		whereClause = "WHERE " + strings.Join(conditions, " AND ")
	}

	// HAVING conditions for metrics
	var havingConditions []string

	if query.MinSharpe != nil {
		havingConditions = append(havingConditions, fmt.Sprintf("MAX(br.sharpe_ratio) >= $%d", argIndex))
		args = append(args, *query.MinSharpe)
		argIndex++
	}

	if query.MinProfitPct != nil {
		havingConditions = append(havingConditions, fmt.Sprintf("MAX(br.profit_pct) >= $%d", argIndex))
		args = append(args, *query.MinProfitPct)
		argIndex++
	}

	if query.MaxDrawdownPct != nil {
		havingConditions = append(havingConditions, fmt.Sprintf("MIN(br.max_drawdown_pct) <= $%d", argIndex))
		args = append(args, *query.MaxDrawdownPct)
		argIndex++
	}

	if query.MinTrades != nil {
		havingConditions = append(havingConditions, fmt.Sprintf("MAX(br.total_trades) >= $%d", argIndex))
		args = append(args, *query.MinTrades)
		argIndex++
	}

	havingClause := ""
	if len(havingConditions) > 0 {
		havingClause = "HAVING " + strings.Join(havingConditions, " AND ")
	}

	// Order by
	orderColumn := "created_at"
	switch query.OrderBy {
	case "sharpe":
		orderColumn = "best_sharpe"
	case "profit":
		orderColumn = "best_profit_pct"
	case "generation":
		orderColumn = "generation"
	case "name":
		orderColumn = "name"
	}

	orderDir := "DESC"
	if query.Ascending {
		orderDir = "ASC"
	}

	// Build final query with CTE
	fullQuery := fmt.Sprintf(baseQuery, whereClause+" "+havingClause)
	fullQuery += fmt.Sprintf(`
		SELECT
			id, name, code_hash, parent_id, generation, description,
			timeframe, stoploss, trailing_stop, created_at, updated_at,
			backtest_count, best_sharpe,
			COALESCE(best_profit_pct, 0) as best_profit_pct,
			COALESCE(best_drawdown, 0) as best_drawdown,
			COALESCE(max_trades, 0) as max_trades,
			COALESCE(avg_win_rate, 0) as avg_win_rate
		FROM strategy_metrics
		ORDER BY %s %s NULLS LAST
		LIMIT $%d OFFSET $%d
	`, orderColumn, orderDir, argIndex, argIndex+1)

	args = append(args, query.PageSize, query.Offset())

	// Execute query
	rows, err := r.pool.Query(ctx, fullQuery, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to search strategies: %w", err)
	}
	defer rows.Close()

	var results []domain.StrategyWithMetrics
	for rows.Next() {
		var s domain.Strategy
		var metrics domain.StrategyPerformanceMetrics

		err := rows.Scan(
			&s.ID, &s.Name, &s.CodeHash, &s.ParentID, &s.Generation, &s.Description,
			&s.Timeframe, &s.Stoploss, &s.TrailingStop, &s.CreatedAt, &s.UpdatedAt,
			&metrics.BacktestCount, &metrics.SharpeRatio, &metrics.ProfitPct,
			&metrics.MaxDrawdownPct, &metrics.TotalTrades, &metrics.WinRate,
		)
		if err != nil {
			return nil, 0, fmt.Errorf("failed to scan strategy: %w", err)
		}

		results = append(results, domain.StrategyWithMetrics{
			Strategy:   &s,
			BestResult: &metrics,
		})
	}

	// Get total count
	countQuery := fmt.Sprintf(`
		SELECT COUNT(*) FROM (
			SELECT s.id
			FROM strategies s
			LEFT JOIN backtest_results br ON br.strategy_id = s.id
			%s
			GROUP BY s.id
			%s
		) subquery
	`, whereClause, havingClause)

	// Remove pagination args for count query
	countArgs := args[:len(args)-2]
	var totalCount int
	err = r.pool.QueryRow(ctx, countQuery, countArgs...).Scan(&totalCount)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get count: %w", err)
	}

	return results, totalCount, nil
}

func (r *strategyRepo) GetLineage(ctx context.Context, strategyID uuid.UUID, depth int) (*domain.StrategyLineageNode, error) {
	if depth > 100 {
		depth = 100
	}

	query := `
		WITH RECURSIVE lineage AS (
			-- Base: starting strategy
			SELECT id, name, parent_id, generation, 0 as level
			FROM strategies
			WHERE id = $1

			UNION ALL

			-- Recursive: descendants
			SELECT s.id, s.name, s.parent_id, s.generation, l.level + 1
			FROM strategies s
			INNER JOIN lineage l ON s.parent_id = l.id
			WHERE l.level < $2
		)
		SELECT id, name, parent_id, generation, level
		FROM lineage
		ORDER BY level, generation
	`

	rows, err := r.pool.Query(ctx, query, strategyID, depth)
	if err != nil {
		return nil, fmt.Errorf("failed to get lineage: %w", err)
	}
	defer rows.Close()

	nodeMap := make(map[uuid.UUID]*domain.StrategyLineageNode)
	var root *domain.StrategyLineageNode

	for rows.Next() {
		node := &domain.StrategyLineageNode{}
		err := rows.Scan(&node.ID, &node.Name, &node.ParentID, &node.Generation, &node.Level)
		if err != nil {
			return nil, fmt.Errorf("failed to scan lineage node: %w", err)
		}

		node.Children = make([]*domain.StrategyLineageNode, 0)
		nodeMap[node.ID] = node

		if node.Level == 0 {
			root = node
		} else if node.ParentID != nil {
			if parent, ok := nodeMap[*node.ParentID]; ok {
				parent.Children = append(parent.Children, node)
			}
		}
	}

	if root == nil {
		return nil, domain.NewNotFoundError("strategy", strategyID.String())
	}

	return root, nil
}

func (r *strategyRepo) GetDescendants(ctx context.Context, strategyID uuid.UUID) ([]*domain.Strategy, error) {
	query := `
		WITH RECURSIVE descendants AS (
			SELECT id FROM strategies WHERE parent_id = $1
			UNION ALL
			SELECT s.id FROM strategies s
			INNER JOIN descendants d ON s.parent_id = d.id
		)
		SELECT
			s.id, s.name, s.code, s.code_hash, s.parent_id, s.generation, s.description,
			s.timeframe, s.stoploss, s.trailing_stop, s.trailing_stop_positive,
			s.trailing_stop_positive_offset, s.startup_candle_count,
			s.indicators, s.minimal_roi, s.created_at, s.updated_at
		FROM strategies s
		WHERE s.id IN (SELECT id FROM descendants)
		ORDER BY s.generation
	`

	return r.queryStrategies(ctx, query, strategyID)
}

func (r *strategyRepo) GetAncestors(ctx context.Context, strategyID uuid.UUID) ([]*domain.Strategy, error) {
	query := `
		WITH RECURSIVE ancestors AS (
			SELECT parent_id FROM strategies WHERE id = $1 AND parent_id IS NOT NULL
			UNION ALL
			SELECT s.parent_id FROM strategies s
			INNER JOIN ancestors a ON s.id = a.parent_id
			WHERE s.parent_id IS NOT NULL
		)
		SELECT
			s.id, s.name, s.code, s.code_hash, s.parent_id, s.generation, s.description,
			s.timeframe, s.stoploss, s.trailing_stop, s.trailing_stop_positive,
			s.trailing_stop_positive_offset, s.startup_candle_count,
			s.indicators, s.minimal_roi, s.created_at, s.updated_at
		FROM strategies s
		WHERE s.id IN (SELECT parent_id FROM ancestors)
		ORDER BY s.generation DESC
	`

	return r.queryStrategies(ctx, query, strategyID)
}

func (r *strategyRepo) queryStrategies(ctx context.Context, query string, args ...interface{}) ([]*domain.Strategy, error) {
	rows, err := r.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query strategies: %w", err)
	}
	defer rows.Close()

	var strategies []*domain.Strategy
	for rows.Next() {
		strategy := &domain.Strategy{}
		var indicators, minimalROI []byte

		err := rows.Scan(
			&strategy.ID, &strategy.Name, &strategy.Code, &strategy.CodeHash,
			&strategy.ParentID, &strategy.Generation, &strategy.Description,
			&strategy.Timeframe, &strategy.Stoploss, &strategy.TrailingStop,
			&strategy.TrailingStopPositive, &strategy.TrailingStopPositiveOffset,
			&strategy.StartupCandleCount, &indicators, &minimalROI,
			&strategy.CreatedAt, &strategy.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan strategy: %w", err)
		}

		_ = json.Unmarshal(indicators, &strategy.Indicators)
		_ = json.Unmarshal(minimalROI, &strategy.MinimalROI)

		strategies = append(strategies, strategy)
	}

	return strategies, nil
}

// Helper functions for error checking
func isDuplicateKeyError(err error) bool {
	return strings.Contains(err.Error(), "duplicate key") ||
		strings.Contains(err.Error(), "unique constraint")
}

func isForeignKeyViolation(err error) bool {
	return strings.Contains(err.Error(), "foreign key constraint")
}
