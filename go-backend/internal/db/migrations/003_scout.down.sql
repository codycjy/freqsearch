-- Rollback Migration: Scout Agent Automatic Trigger System
-- Version: 003

-- Drop views
DROP VIEW IF EXISTS v_scout_runs_summary;
DROP VIEW IF EXISTS v_scout_schedules_active;

-- Drop triggers
DROP TRIGGER IF EXISTS trg_scout_runs_update_schedule ON scout_runs;
DROP TRIGGER IF EXISTS trg_scout_schedules_updated_at ON scout_schedules;

-- Drop trigger function
DROP FUNCTION IF EXISTS update_schedule_last_run();

-- Drop tables
DROP TABLE IF EXISTS scout_schedules;
DROP TABLE IF EXISTS scout_runs;

-- Drop types
DROP TYPE IF EXISTS scout_trigger_type;
DROP TYPE IF EXISTS scout_run_status;
