-- Rollback: Remove simhash column and index

-- Drop the index first
DROP INDEX IF EXISTS idx_strategies_simhash;

-- Remove the simhash column
ALTER TABLE strategies DROP COLUMN IF EXISTS simhash;
