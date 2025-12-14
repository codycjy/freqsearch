-- FreqSearch Database Schema - Rollback
-- Version: 001
-- Description: Drop all tables, types, and extensions

-- Drop triggers first
DROP TRIGGER IF EXISTS trg_optimization_iteration_update ON optimization_iterations;
DROP TRIGGER IF EXISTS trg_strategies_generation ON strategies;
DROP TRIGGER IF EXISTS trg_strategies_code_hash ON strategies;
DROP TRIGGER IF EXISTS trg_optimization_runs_updated_at ON optimization_runs;
DROP TRIGGER IF EXISTS trg_strategies_updated_at ON strategies;

-- Drop functions
DROP FUNCTION IF EXISTS update_optimization_on_iteration();
DROP FUNCTION IF EXISTS set_strategy_generation();
DROP FUNCTION IF EXISTS calculate_code_hash();
DROP FUNCTION IF EXISTS update_updated_at();

-- Drop views
DROP VIEW IF EXISTS v_active_jobs;
DROP VIEW IF EXISTS v_strategy_performance;

-- Drop tables (in correct order due to foreign keys)
DROP TABLE IF EXISTS optimization_iterations;
DROP TABLE IF EXISTS optimization_runs;
DROP TABLE IF EXISTS backtest_results;
DROP TABLE IF EXISTS backtest_jobs;
DROP TABLE IF EXISTS strategies;

-- Drop types
DROP TYPE IF EXISTS approval_status;
DROP TYPE IF EXISTS optimization_mode;
DROP TYPE IF EXISTS optimization_status;
DROP TYPE IF EXISTS job_status;

-- Note: We don't drop extensions as they might be used by other schemas
-- DROP EXTENSION IF EXISTS "pg_trgm";
-- DROP EXTENSION IF EXISTS "uuid-ossp";
