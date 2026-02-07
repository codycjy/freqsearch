package repository

import (
	"context"
	"fmt"
	"strings"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/saltfish/freqsearch/go-backend/internal/db"
	"github.com/saltfish/freqsearch/go-backend/internal/domain"
)

// factorRepo implements FactorRepository using PostgreSQL.
type factorRepo struct {
	pool *db.Pool
}

// NewFactorRepository creates a new PostgreSQL factor repository.
func NewFactorRepository(pool *db.Pool) FactorRepository {
	return &factorRepo{pool: pool}
}

// stringSliceToPostgresArray converts a Go string slice to PostgreSQL array format
func stringSliceToPostgresArray(s []string) string {
	if len(s) == 0 {
		return "{}"
	}
	escaped := make([]string, len(s))
	for i, v := range s {
		escaped[i] = strings.ReplaceAll(v, "\"", "\\\"")
	}
	return "{\"" + strings.Join(escaped, "\",\"") + "\"}"
}

func (r *factorRepo) Create(ctx context.Context, factor *domain.Factor) error {
	operatorDeps := stringSliceToPostgresArray(factor.OperatorDeps)
	dataDeps := stringSliceToPostgresArray(factor.DataDeps)

	query := `
		INSERT INTO factors (
			id, name, source, version, expression, description,
			code_template, operator_deps, data_deps,
			category, signal_type, holding_period, data_requirement,
			market_regime, complexity,
			avg_return, sharpe_ratio, max_drawdown, win_rate, tested_at,
			is_active, created_at, updated_at
		) VALUES (
			$1, $2, $3, $4, $5, $6,
			$7, $8, $9,
			$10, $11, $12, $13,
			$14, $15,
			$16, $17, $18, $19, $20,
			$21, $22, $23
		)
	`

	_, err := r.pool.Exec(ctx, query,
		factor.ID, factor.Name, factor.Source, factor.Version, factor.Expression, factor.Description,
		factor.CodeTemplate, operatorDeps, dataDeps,
		factor.Category, factor.SignalType, factor.HoldingPeriod, factor.DataRequirement,
		factor.MarketRegime, factor.Complexity,
		factor.AvgReturn, factor.SharpeRatio, factor.MaxDrawdown, factor.WinRate, factor.TestedAt,
		factor.IsActive, factor.CreatedAt, factor.UpdatedAt,
	)

	if err != nil {
		if isDuplicateKeyError(err) {
			return domain.NewDuplicateError("factor", "name", factor.Name)
		}
		return fmt.Errorf("failed to create factor: %w", err)
	}

	return nil
}

func (r *factorRepo) GetByID(ctx context.Context, id uuid.UUID) (*domain.Factor, error) {
	query := `
		SELECT
			id, name, source, version, expression, description,
			code_template, operator_deps, data_deps,
			category, signal_type, holding_period, data_requirement,
			market_regime, complexity,
			avg_return, sharpe_ratio, max_drawdown, win_rate, tested_at,
			is_active, created_at, updated_at
		FROM factors
		WHERE id = $1
	`

	factor := &domain.Factor{}

	err := r.pool.QueryRow(ctx, query, id).Scan(
		&factor.ID, &factor.Name, &factor.Source, &factor.Version, &factor.Expression, &factor.Description,
		&factor.CodeTemplate, &factor.OperatorDeps, &factor.DataDeps,
		&factor.Category, &factor.SignalType, &factor.HoldingPeriod, &factor.DataRequirement,
		&factor.MarketRegime, &factor.Complexity,
		&factor.AvgReturn, &factor.SharpeRatio, &factor.MaxDrawdown, &factor.WinRate, &factor.TestedAt,
		&factor.IsActive, &factor.CreatedAt, &factor.UpdatedAt,
	)

	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, domain.NewNotFoundError("factor", id.String())
		}
		return nil, fmt.Errorf("failed to get factor: %w", err)
	}

	return factor, nil
}

func (r *factorRepo) GetByName(ctx context.Context, name string) (*domain.Factor, error) {
	query := `
		SELECT
			id, name, source, version, expression, description,
			code_template, operator_deps, data_deps,
			category, signal_type, holding_period, data_requirement,
			market_regime, complexity,
			avg_return, sharpe_ratio, max_drawdown, win_rate, tested_at,
			is_active, created_at, updated_at
		FROM factors
		WHERE name = $1
	`

	factor := &domain.Factor{}

	err := r.pool.QueryRow(ctx, query, name).Scan(
		&factor.ID, &factor.Name, &factor.Source, &factor.Version, &factor.Expression, &factor.Description,
		&factor.CodeTemplate, &factor.OperatorDeps, &factor.DataDeps,
		&factor.Category, &factor.SignalType, &factor.HoldingPeriod, &factor.DataRequirement,
		&factor.MarketRegime, &factor.Complexity,
		&factor.AvgReturn, &factor.SharpeRatio, &factor.MaxDrawdown, &factor.WinRate, &factor.TestedAt,
		&factor.IsActive, &factor.CreatedAt, &factor.UpdatedAt,
	)

	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, domain.NewNotFoundError("factor", "name:"+name)
		}
		return nil, fmt.Errorf("failed to get factor by name: %w", err)
	}

	return factor, nil
}

func (r *factorRepo) Update(ctx context.Context, factor *domain.Factor) error {
	operatorDeps := stringSliceToPostgresArray(factor.OperatorDeps)
	dataDeps := stringSliceToPostgresArray(factor.DataDeps)

	query := `
		UPDATE factors SET
			name = $2, source = $3, version = $4, expression = $5, description = $6,
			code_template = $7, operator_deps = $8, data_deps = $9,
			category = $10, signal_type = $11, holding_period = $12, data_requirement = $13,
			market_regime = $14, complexity = $15,
			avg_return = $16, sharpe_ratio = $17, max_drawdown = $18, win_rate = $19, tested_at = $20,
			is_active = $21, updated_at = $22
		WHERE id = $1
	`

	result, err := r.pool.Exec(ctx, query,
		factor.ID, factor.Name, factor.Source, factor.Version, factor.Expression, factor.Description,
		factor.CodeTemplate, operatorDeps, dataDeps,
		factor.Category, factor.SignalType, factor.HoldingPeriod, factor.DataRequirement,
		factor.MarketRegime, factor.Complexity,
		factor.AvgReturn, factor.SharpeRatio, factor.MaxDrawdown, factor.WinRate, factor.TestedAt,
		factor.IsActive, factor.UpdatedAt,
	)

	if err != nil {
		if isDuplicateKeyError(err) {
			return domain.NewDuplicateError("factor", "name", factor.Name)
		}
		return fmt.Errorf("failed to update factor: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("factor", factor.ID.String())
	}

	return nil
}

func (r *factorRepo) Delete(ctx context.Context, id uuid.UUID) error {
	result, err := r.pool.Exec(ctx, "DELETE FROM factors WHERE id = $1", id)
	if err != nil {
		if isForeignKeyViolation(err) {
			return fmt.Errorf("factor is in use by strategies")
		}
		return fmt.Errorf("failed to delete factor: %w", err)
	}

	if result.RowsAffected() == 0 {
		return domain.NewNotFoundError("factor", id.String())
	}

	return nil
}

func (r *factorRepo) List(ctx context.Context, query domain.FactorSearchQuery) ([]*domain.Factor, int, error) {
	query.SetDefaults()

	// Build dynamic query
	var conditions []string
	var args []interface{}
	argIndex := 1

	if query.Name != nil && *query.Name != "" {
		conditions = append(conditions, fmt.Sprintf("name ILIKE $%d", argIndex))
		args = append(args, "%"+*query.Name+"%")
		argIndex++
	}

	if query.Source != nil && *query.Source != "" {
		conditions = append(conditions, fmt.Sprintf("source = $%d", argIndex))
		args = append(args, *query.Source)
		argIndex++
	}

	if query.Category != nil && *query.Category != "" {
		conditions = append(conditions, fmt.Sprintf("category = $%d", argIndex))
		args = append(args, *query.Category)
		argIndex++
	}

	if query.SignalType != nil && *query.SignalType != "" {
		conditions = append(conditions, fmt.Sprintf("signal_type = $%d", argIndex))
		args = append(args, *query.SignalType)
		argIndex++
	}

	if query.HoldingPeriod != nil && *query.HoldingPeriod != "" {
		conditions = append(conditions, fmt.Sprintf("holding_period = $%d", argIndex))
		args = append(args, *query.HoldingPeriod)
		argIndex++
	}

	if query.DataRequirement != nil && *query.DataRequirement != "" {
		conditions = append(conditions, fmt.Sprintf("data_requirement = $%d", argIndex))
		args = append(args, *query.DataRequirement)
		argIndex++
	}

	if query.MarketRegime != nil && *query.MarketRegime != "" {
		conditions = append(conditions, fmt.Sprintf("market_regime = $%d", argIndex))
		args = append(args, *query.MarketRegime)
		argIndex++
	}

	if query.Complexity != nil && *query.Complexity != "" {
		conditions = append(conditions, fmt.Sprintf("complexity = $%d", argIndex))
		args = append(args, *query.Complexity)
		argIndex++
	}

	if query.IsActive != nil {
		conditions = append(conditions, fmt.Sprintf("is_active = $%d", argIndex))
		args = append(args, *query.IsActive)
		argIndex++
	}

	whereClause := ""
	if len(conditions) > 0 {
		whereClause = "WHERE " + strings.Join(conditions, " AND ")
	}

	// Order by
	orderColumn := "name"
	switch query.OrderBy {
	case "category":
		orderColumn = "category"
	case "created_at":
		orderColumn = "created_at"
	case "name":
		orderColumn = "name"
	}

	orderDir := "ASC"
	if !query.Ascending {
		orderDir = "DESC"
	}

	// Build final query
	fullQuery := fmt.Sprintf(`
		SELECT
			id, name, source, version, expression, description,
			code_template, operator_deps, data_deps,
			category, signal_type, holding_period, data_requirement,
			market_regime, complexity,
			avg_return, sharpe_ratio, max_drawdown, win_rate, tested_at,
			is_active, created_at, updated_at
		FROM factors
		%s
		ORDER BY %s %s
		LIMIT $%d OFFSET $%d
	`, whereClause, orderColumn, orderDir, argIndex, argIndex+1)

	args = append(args, query.PageSize, query.Offset())

	// Execute query
	rows, err := r.pool.Query(ctx, fullQuery, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list factors: %w", err)
	}
	defer rows.Close()

	var factors []*domain.Factor
	for rows.Next() {
		factor := &domain.Factor{}

		err := rows.Scan(
			&factor.ID, &factor.Name, &factor.Source, &factor.Version, &factor.Expression, &factor.Description,
			&factor.CodeTemplate, &factor.OperatorDeps, &factor.DataDeps,
			&factor.Category, &factor.SignalType, &factor.HoldingPeriod, &factor.DataRequirement,
			&factor.MarketRegime, &factor.Complexity,
			&factor.AvgReturn, &factor.SharpeRatio, &factor.MaxDrawdown, &factor.WinRate, &factor.TestedAt,
			&factor.IsActive, &factor.CreatedAt, &factor.UpdatedAt,
		)
		if err != nil {
			return nil, 0, fmt.Errorf("failed to scan factor: %w", err)
		}

		factors = append(factors, factor)
	}

	// Get total count
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM factors %s", whereClause)
	countArgs := args[:len(args)-2] // Remove pagination args

	var totalCount int
	err = r.pool.QueryRow(ctx, countQuery, countArgs...).Scan(&totalCount)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get count: %w", err)
	}

	return factors, totalCount, nil
}

func (r *factorRepo) Search(ctx context.Context, keyword string, limit int) ([]*domain.Factor, error) {
	query := `
		SELECT
			id, name, source, version, expression, description,
			code_template, operator_deps, data_deps,
			category, signal_type, holding_period, data_requirement,
			market_regime, complexity,
			avg_return, sharpe_ratio, max_drawdown, win_rate, tested_at,
			is_active, created_at, updated_at
		FROM factors
		WHERE to_tsvector('english', description) @@ plainto_tsquery('english', $1)
			OR name ILIKE $2
		ORDER BY ts_rank(to_tsvector('english', description), plainto_tsquery('english', $1)) DESC
		LIMIT $3
	`

	rows, err := r.pool.Query(ctx, query, keyword, "%"+keyword+"%", limit)
	if err != nil {
		return nil, fmt.Errorf("failed to search factors: %w", err)
	}
	defer rows.Close()

	var factors []*domain.Factor
	for rows.Next() {
		factor := &domain.Factor{}

		err := rows.Scan(
			&factor.ID, &factor.Name, &factor.Source, &factor.Version, &factor.Expression, &factor.Description,
			&factor.CodeTemplate, &factor.OperatorDeps, &factor.DataDeps,
			&factor.Category, &factor.SignalType, &factor.HoldingPeriod, &factor.DataRequirement,
			&factor.MarketRegime, &factor.Complexity,
			&factor.AvgReturn, &factor.SharpeRatio, &factor.MaxDrawdown, &factor.WinRate, &factor.TestedAt,
			&factor.IsActive, &factor.CreatedAt, &factor.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan factor: %w", err)
		}

		factors = append(factors, factor)
	}

	return factors, nil
}

func (r *factorRepo) GetCategoryStats(ctx context.Context) (domain.CategoryStats, error) {
	query := `
		SELECT category, COUNT(*) as count
		FROM factors
		WHERE is_active = TRUE
		GROUP BY category
		ORDER BY count DESC
	`

	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to get category stats: %w", err)
	}
	defer rows.Close()

	stats := make(domain.CategoryStats)
	for rows.Next() {
		var category string
		var count int
		if err := rows.Scan(&category, &count); err != nil {
			return nil, fmt.Errorf("failed to scan category stats: %w", err)
		}
		stats[category] = count
	}

	return stats, nil
}
