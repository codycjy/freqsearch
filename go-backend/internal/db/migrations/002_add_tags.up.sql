-- Migration: Add tags JSONB field for strategy metadata
-- This supports searchable strategy classification tags

-- Add tags JSONB field
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '{}'::jsonb;

-- Create GIN index for efficient tag searching
CREATE INDEX IF NOT EXISTS idx_strategies_tags ON strategies USING gin(tags);

-- Add timestamp for when description/tags were generated
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS description_generated_at TIMESTAMPTZ;

-- Add comment
COMMENT ON COLUMN strategies.tags IS 'Strategy classification tags: strategy_type, risk_level, trading_style, indicators, market_regime';
