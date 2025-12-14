-- Rollback: Remove tags fields from strategies table

DROP INDEX IF EXISTS idx_strategies_tags;
ALTER TABLE strategies DROP COLUMN IF EXISTS tags;
ALTER TABLE strategies DROP COLUMN IF EXISTS description_generated_at;
