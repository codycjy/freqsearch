-- FreqSearch Database Schema
-- Version: 001
-- Description: Initial schema with strategies, backtest jobs, results, and optimization tracking

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- =====================================================
-- STRATEGIES TABLE
-- Stores trading strategy source code and metadata
-- =====================================================
CREATE TABLE strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code TEXT NOT NULL,
    code_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA256 hash for deduplication
    parent_id UUID REFERENCES strategies(id) ON DELETE SET NULL,
    generation INTEGER NOT NULL DEFAULT 0,   -- Optimization generation number
    description TEXT,

    -- Denormalized metadata (extracted from code for query performance)
    timeframe VARCHAR(10),
    stoploss DECIMAL(10, 6),
    trailing_stop BOOLEAN DEFAULT FALSE,
    trailing_stop_positive DECIMAL(10, 6),
    trailing_stop_positive_offset DECIMAL(10, 6),
    startup_candle_count INTEGER,
    indicators JSONB DEFAULT '[]'::jsonb,    -- e.g., ["RSI", "MACD", "EMA"]
    minimal_roi JSONB,                        -- e.g., {"0": 0.1, "60": 0.05}

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for strategies
CREATE INDEX idx_strategies_name ON strategies(name);
CREATE INDEX idx_strategies_parent_id ON strategies(parent_id);
CREATE INDEX idx_strategies_generation ON strategies(generation);
CREATE INDEX idx_strategies_created_at ON strategies(created_at DESC);
CREATE INDEX idx_strategies_name_trgm ON strategies USING gin(name gin_trgm_ops);

COMMENT ON TABLE strategies IS 'Trading strategies with source code and metadata';
COMMENT ON COLUMN strategies.code_hash IS 'SHA256 hash of code for deduplication';
COMMENT ON COLUMN strategies.generation IS 'Generation number in optimization lineage (0 = original)';

-- =====================================================
-- BACKTEST JOBS TABLE
-- Task queue for backtest execution
-- =====================================================
CREATE TYPE job_status AS ENUM (
    'pending',
    'running',
    'completed',
    'failed',
    'cancelled'
);

CREATE TABLE backtest_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    optimization_run_id UUID,  -- Will be FK after optimization_runs table is created
    config JSONB NOT NULL,      -- BacktestConfig as JSON
    priority INTEGER NOT NULL DEFAULT 0,  -- Higher = processed first
    status job_status NOT NULL DEFAULT 'pending',
    container_id VARCHAR(64),   -- Docker container ID when running
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,  -- Number of retry attempts
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    CONSTRAINT valid_config CHECK (
        config ? 'exchange' AND config ? 'pairs' AND config ? 'timeframe'
    )
);

-- Indexes for backtest_jobs
CREATE INDEX idx_backtest_jobs_strategy_id ON backtest_jobs(strategy_id);
CREATE INDEX idx_backtest_jobs_optimization_run ON backtest_jobs(optimization_run_id);
CREATE INDEX idx_backtest_jobs_status ON backtest_jobs(status);
CREATE INDEX idx_backtest_jobs_created_at ON backtest_jobs(created_at DESC);
-- Partial index for efficient pending job retrieval
CREATE INDEX idx_backtest_jobs_pending ON backtest_jobs(priority DESC, created_at ASC)
    WHERE status = 'pending';

COMMENT ON TABLE backtest_jobs IS 'Queue of backtest execution tasks';
COMMENT ON COLUMN backtest_jobs.priority IS 'Higher priority jobs are processed first';

-- =====================================================
-- BACKTEST RESULTS TABLE
-- Stores execution results and performance metrics
-- =====================================================
CREATE TABLE backtest_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL UNIQUE REFERENCES backtest_jobs(id) ON DELETE CASCADE,
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,

    -- Trade statistics
    total_trades INTEGER NOT NULL,
    winning_trades INTEGER NOT NULL,
    losing_trades INTEGER NOT NULL,
    win_rate DECIMAL(5, 4) NOT NULL,  -- 0.0000 to 1.0000

    -- Profit metrics
    profit_total DECIMAL(20, 8) NOT NULL,    -- Absolute profit
    profit_pct DECIMAL(10, 4) NOT NULL,      -- Percentage profit
    profit_factor DECIMAL(10, 4),             -- Gross profit / Gross loss

    -- Risk metrics
    max_drawdown DECIMAL(20, 8) NOT NULL,
    max_drawdown_pct DECIMAL(10, 4) NOT NULL,
    sharpe_ratio DECIMAL(10, 4),
    sortino_ratio DECIMAL(10, 4),
    calmar_ratio DECIMAL(10, 4),

    -- Trade duration metrics
    avg_trade_duration_minutes DECIMAL(10, 2),
    avg_profit_per_trade DECIMAL(20, 8),
    best_trade_pct DECIMAL(10, 4),
    worst_trade_pct DECIMAL(10, 4),

    -- Detailed data
    pair_results JSONB,     -- Per-pair breakdown
    raw_log TEXT,           -- Full Freqtrade output
    trades_json JSONB,      -- Individual trade details

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for backtest_results
CREATE INDEX idx_backtest_results_strategy_id ON backtest_results(strategy_id);
CREATE INDEX idx_backtest_results_created_at ON backtest_results(created_at DESC);
CREATE INDEX idx_backtest_results_sharpe ON backtest_results(sharpe_ratio DESC NULLS LAST);
CREATE INDEX idx_backtest_results_profit ON backtest_results(profit_pct DESC);
-- Composite index for performance queries
CREATE INDEX idx_backtest_results_performance ON backtest_results(
    sharpe_ratio DESC NULLS LAST,
    profit_pct DESC,
    max_drawdown_pct ASC
) WHERE sharpe_ratio IS NOT NULL;

COMMENT ON TABLE backtest_results IS 'Backtest execution results with performance metrics';

-- =====================================================
-- OPTIMIZATION RUNS TABLE
-- Tracks AI-driven optimization sessions
-- =====================================================
CREATE TYPE optimization_status AS ENUM (
    'pending',
    'running',
    'paused',
    'completed',
    'failed',
    'cancelled'
);

CREATE TYPE optimization_mode AS ENUM (
    'maximize_sharpe',
    'maximize_profit',
    'minimize_drawdown',
    'balanced'
);

CREATE TABLE optimization_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    base_strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    config JSONB NOT NULL,  -- OptimizationConfig as JSON
    mode optimization_mode NOT NULL DEFAULT 'balanced',

    -- Success criteria
    criteria_min_sharpe DECIMAL(10, 4),
    criteria_min_profit_pct DECIMAL(10, 4),
    criteria_max_drawdown_pct DECIMAL(10, 4),
    criteria_min_trades INTEGER,
    criteria_min_win_rate DECIMAL(5, 4),

    -- Progress tracking
    status optimization_status NOT NULL DEFAULT 'pending',
    current_iteration INTEGER NOT NULL DEFAULT 0,
    max_iterations INTEGER NOT NULL DEFAULT 10,

    -- Best results
    best_strategy_id UUID REFERENCES strategies(id),
    best_result_id UUID REFERENCES backtest_results(id),
    termination_reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Add FK constraint to backtest_jobs now that optimization_runs exists
ALTER TABLE backtest_jobs
    ADD CONSTRAINT fk_optimization_run
    FOREIGN KEY (optimization_run_id)
    REFERENCES optimization_runs(id) ON DELETE SET NULL;

-- Indexes for optimization_runs
CREATE INDEX idx_optimization_runs_status ON optimization_runs(status);
CREATE INDEX idx_optimization_runs_base_strategy ON optimization_runs(base_strategy_id);
CREATE INDEX idx_optimization_runs_created_at ON optimization_runs(created_at DESC);

COMMENT ON TABLE optimization_runs IS 'AI-driven strategy optimization sessions';

-- =====================================================
-- OPTIMIZATION ITERATIONS TABLE
-- Records each iteration in an optimization run
-- =====================================================
CREATE TYPE approval_status AS ENUM (
    'pending',
    'approved',
    'rejected',
    'needs_iteration'
);

CREATE TABLE optimization_iterations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    optimization_run_id UUID NOT NULL REFERENCES optimization_runs(id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    strategy_id UUID NOT NULL REFERENCES strategies(id),
    backtest_job_id UUID NOT NULL REFERENCES backtest_jobs(id),
    result_id UUID REFERENCES backtest_results(id),

    -- Agent feedback
    engineer_changes TEXT,    -- What the Strategy Engineer changed
    analyst_feedback TEXT,    -- Quant Analyst's diagnosis

    approval approval_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(optimization_run_id, iteration_number)
);

-- Indexes for optimization_iterations
CREATE INDEX idx_optimization_iterations_run ON optimization_iterations(optimization_run_id);
CREATE INDEX idx_optimization_iterations_strategy ON optimization_iterations(strategy_id);

COMMENT ON TABLE optimization_iterations IS 'Individual iterations within an optimization run';

-- =====================================================
-- VIEWS
-- =====================================================

-- Strategy performance summary view
CREATE VIEW v_strategy_performance AS
SELECT
    s.id AS strategy_id,
    s.name AS strategy_name,
    s.generation,
    s.parent_id,
    COUNT(br.id) AS backtest_count,
    MAX(br.sharpe_ratio) AS best_sharpe,
    AVG(br.sharpe_ratio) AS avg_sharpe,
    MAX(br.profit_pct) AS best_profit_pct,
    AVG(br.profit_pct) AS avg_profit_pct,
    MIN(br.max_drawdown_pct) AS best_drawdown,
    AVG(br.win_rate) AS avg_win_rate,
    s.created_at
FROM strategies s
LEFT JOIN backtest_results br ON br.strategy_id = s.id
GROUP BY s.id;

COMMENT ON VIEW v_strategy_performance IS 'Aggregated performance metrics per strategy';

-- Active jobs view
CREATE VIEW v_active_jobs AS
SELECT
    bj.id AS job_id,
    bj.status,
    bj.priority,
    s.name AS strategy_name,
    bj.container_id,
    bj.created_at,
    bj.started_at,
    EXTRACT(EPOCH FROM (NOW() - bj.started_at)) / 60 AS running_minutes
FROM backtest_jobs bj
JOIN strategies s ON s.id = bj.strategy_id
WHERE bj.status IN ('pending', 'running')
ORDER BY bj.priority DESC, bj.created_at ASC;

COMMENT ON VIEW v_active_jobs IS 'Currently pending and running backtest jobs';

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_strategies_updated_at
    BEFORE UPDATE ON strategies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_optimization_runs_updated_at
    BEFORE UPDATE ON optimization_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-calculate code hash
CREATE OR REPLACE FUNCTION calculate_code_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.code_hash = encode(sha256(NEW.code::bytea), 'hex');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_strategies_code_hash
    BEFORE INSERT OR UPDATE OF code ON strategies
    FOR EACH ROW EXECUTE FUNCTION calculate_code_hash();

-- Auto-set strategy generation based on parent
CREATE OR REPLACE FUNCTION set_strategy_generation()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.parent_id IS NOT NULL THEN
        SELECT generation + 1 INTO NEW.generation
        FROM strategies WHERE id = NEW.parent_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_strategies_generation
    BEFORE INSERT ON strategies
    FOR EACH ROW EXECUTE FUNCTION set_strategy_generation();

-- Update optimization run status when iteration completes
CREATE OR REPLACE FUNCTION update_optimization_on_iteration()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE optimization_runs
    SET
        current_iteration = NEW.iteration_number,
        updated_at = NOW()
    WHERE id = NEW.optimization_run_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_optimization_iteration_update
    AFTER INSERT ON optimization_iterations
    FOR EACH ROW EXECUTE FUNCTION update_optimization_on_iteration();
