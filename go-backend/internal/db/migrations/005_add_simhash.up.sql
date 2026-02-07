-- Add simhash column for similarity detection
-- SimHash is computed by Python agents and stored as 16-char hex string
-- Part of the dual-hash architecture: SHA256 for exact matching, SimHash for similarity

-- Add simhash column (nullable to support existing strategies)
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS simhash VARCHAR(16);

-- Create index for efficient similarity lookups
-- This index enables fast queries when checking for similar strategies
CREATE INDEX IF NOT EXISTS idx_strategies_simhash ON strategies(simhash) WHERE simhash IS NOT NULL;

-- Add comment explaining the dual-hash architecture
COMMENT ON COLUMN strategies.simhash IS 'SimHash for similarity detection (computed by Python). Used with code_hash (SHA256) for dual-hash deduplication: SHA256 for exact matches, SimHash for finding similar strategies.';
