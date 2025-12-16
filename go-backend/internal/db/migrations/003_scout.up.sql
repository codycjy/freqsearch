-- Migration: Scout Agent Automatic Trigger System
-- Version: 003
-- Description: Tables for Scout agent runs, schedules, and automatic triggers

-- =====================================================
-- SCOUT ENUMS
-- =====================================================

-- Scout run status
CREATE TYPE scout_run_status AS ENUM (
    'pending',
    'running',
    'completed',
    'failed',
    'cancelled'
);

-- Scout trigger type
CREATE TYPE scout_trigger_type AS ENUM (
    'manual',
    'scheduled',
    'event'
);

-- =====================================================
-- SCOUT RUNS TABLE
-- Tracks individual Scout agent executions
-- =====================================================
CREATE TABLE scout_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trigger_type scout_trigger_type NOT NULL,
    triggered_by VARCHAR(255),
    source VARCHAR(50) NOT NULL DEFAULT 'stratninja',
    max_strategies INTEGER NOT NULL DEFAULT 50,
    status scout_run_status NOT NULL DEFAULT 'pending',
    error_message TEXT,
    metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT chk_max_strategies_positive CHECK (max_strategies > 0),
    CONSTRAINT chk_metrics_valid CHECK (
        jsonb_typeof(metrics) = 'object'
    )
);

-- Indexes for scout_runs
CREATE INDEX idx_scout_runs_status ON scout_runs(status);
CREATE INDEX idx_scout_runs_source ON scout_runs(source);
CREATE INDEX idx_scout_runs_trigger_type ON scout_runs(trigger_type);
CREATE INDEX idx_scout_runs_created_at ON scout_runs(created_at DESC);
CREATE INDEX idx_scout_runs_triggered_by ON scout_runs(triggered_by);

-- Partial index for active runs
CREATE INDEX idx_scout_runs_active ON scout_runs(created_at DESC)
    WHERE status IN ('pending', 'running');

-- Composite index for filtering
CREATE INDEX idx_scout_runs_status_source ON scout_runs(status, source, created_at DESC);

-- JSONB index for metrics queries
CREATE INDEX idx_scout_runs_metrics ON scout_runs USING gin(metrics);

COMMENT ON TABLE scout_runs IS 'Scout agent execution runs with metrics tracking';
COMMENT ON COLUMN scout_runs.trigger_type IS 'How the Scout run was triggered (manual, scheduled, event)';
COMMENT ON COLUMN scout_runs.triggered_by IS 'User ID or system identifier that triggered the run';
COMMENT ON COLUMN scout_runs.source IS 'Strategy source to scout (stratninja, freqai_gym, etc.)';
COMMENT ON COLUMN scout_runs.max_strategies IS 'Maximum number of strategies to fetch';
COMMENT ON COLUMN scout_runs.metrics IS 'JSON metrics: total_fetched, validated, validation_failed, duplicates_removed, submitted';

-- =====================================================
-- SCOUT SCHEDULES TABLE
-- Manages cron-based automatic Scout triggers
-- =====================================================
CREATE TABLE scout_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    cron_expression VARCHAR(100) NOT NULL,
    source VARCHAR(50) NOT NULL DEFAULT 'stratninja',
    max_strategies INTEGER NOT NULL DEFAULT 50,
    enabled BOOLEAN NOT NULL DEFAULT true,
    last_run_id UUID REFERENCES scout_runs(id) ON DELETE SET NULL,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_schedule_max_strategies_positive CHECK (max_strategies > 0),
    CONSTRAINT chk_cron_not_empty CHECK (cron_expression <> '')
);

-- Indexes for scout_schedules
CREATE INDEX idx_scout_schedules_enabled ON scout_schedules(enabled);
CREATE INDEX idx_scout_schedules_next_run ON scout_schedules(next_run_at)
    WHERE enabled = true;
CREATE INDEX idx_scout_schedules_source ON scout_schedules(source);
CREATE INDEX idx_scout_schedules_created_at ON scout_schedules(created_at DESC);

-- Partial index for active schedules due to run
CREATE INDEX idx_scout_schedules_due ON scout_schedules(next_run_at)
    WHERE enabled = true AND next_run_at <= NOW();

COMMENT ON TABLE scout_schedules IS 'Cron schedules for automatic Scout agent execution';
COMMENT ON COLUMN scout_schedules.name IS 'Unique schedule name';
COMMENT ON COLUMN scout_schedules.cron_expression IS 'Cron expression (e.g., "0 2 * * *" for 2am daily)';
COMMENT ON COLUMN scout_schedules.enabled IS 'Whether the schedule is active';
COMMENT ON COLUMN scout_schedules.last_run_id IS 'Reference to the most recent Scout run';
COMMENT ON COLUMN scout_schedules.next_run_at IS 'Calculated next execution time';

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Auto-update updated_at timestamp on scout_schedules
CREATE TRIGGER trg_scout_schedules_updated_at
    BEFORE UPDATE ON scout_schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Update schedule last_run tracking when a run completes
CREATE OR REPLACE FUNCTION update_schedule_last_run()
RETURNS TRIGGER AS $$
BEGIN
    -- Only update if this run was triggered by a schedule
    IF NEW.trigger_type = 'scheduled' AND NEW.triggered_by IS NOT NULL THEN
        UPDATE scout_schedules
        SET
            last_run_id = NEW.id,
            last_run_at = NEW.created_at,
            updated_at = NOW()
        WHERE name = NEW.triggered_by;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_scout_runs_update_schedule
    AFTER INSERT ON scout_runs
    FOR EACH ROW EXECUTE FUNCTION update_schedule_last_run();

-- =====================================================
-- VIEWS
-- =====================================================

-- Active Scout schedules view
CREATE VIEW v_scout_schedules_active AS
SELECT
    s.id,
    s.name,
    s.cron_expression,
    s.source,
    s.max_strategies,
    s.last_run_at,
    s.next_run_at,
    sr.status AS last_run_status,
    EXTRACT(EPOCH FROM (s.next_run_at - NOW())) / 60 AS minutes_until_next_run
FROM scout_schedules s
LEFT JOIN scout_runs sr ON sr.id = s.last_run_id
WHERE s.enabled = true
ORDER BY s.next_run_at ASC NULLS LAST;

COMMENT ON VIEW v_scout_schedules_active IS 'Active Scout schedules with next run timing';

-- Scout run metrics summary view
CREATE VIEW v_scout_runs_summary AS
SELECT
    sr.id,
    sr.trigger_type,
    sr.triggered_by,
    sr.source,
    sr.max_strategies,
    sr.status,
    sr.created_at,
    sr.started_at,
    sr.completed_at,
    EXTRACT(EPOCH FROM (COALESCE(sr.completed_at, NOW()) - COALESCE(sr.started_at, sr.created_at))) / 60 AS duration_minutes,
    (sr.metrics->>'total_fetched')::INTEGER AS total_fetched,
    (sr.metrics->>'validated')::INTEGER AS validated,
    (sr.metrics->>'validation_failed')::INTEGER AS validation_failed,
    (sr.metrics->>'duplicates_removed')::INTEGER AS duplicates_removed,
    (sr.metrics->>'submitted')::INTEGER AS submitted
FROM scout_runs sr
ORDER BY sr.created_at DESC;

COMMENT ON VIEW v_scout_runs_summary IS 'Scout runs with extracted metrics and duration';
