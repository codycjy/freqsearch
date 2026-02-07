-- Factor system migration
-- Implements structured quantitative factor library for FreqSearch

-- Factor operators (18 core operators for factor computation)
CREATE TABLE factor_operators (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(32) NOT NULL UNIQUE,  -- "rank", "correlation", "delay"
    category        VARCHAR(32) NOT NULL,         -- "cross_sectional", "time_series", "arithmetic"
    signature       TEXT NOT NULL,                -- "rank(x) -> Series"
    description     TEXT,
    code_impl       TEXT NOT NULL,                -- Python implementation
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_factor_operators_category ON factor_operators(category);

-- Factors (quantitative alpha factors)
CREATE TABLE factors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(64) NOT NULL UNIQUE,  -- "alpha_001"
    source          VARCHAR(32) NOT NULL,         -- "worldquant_101", "ta_lib", "custom"
    version         INTEGER DEFAULT 1,

    -- DSL expression (human-readable)
    expression      TEXT NOT NULL,
    description     TEXT,

    -- Executable code (Python)
    code_template   TEXT,
    operator_deps   TEXT[],                       -- ["correlation", "rank", "delta", "log"]
    data_deps       TEXT[],                       -- ["close", "open", "volume", "vwap"]

    -- 6-dimensional classification tags
    category        VARCHAR(32) NOT NULL,         -- momentum, mean_reversion, volatility, volume, price_pattern
    signal_type     VARCHAR(32),                  -- entry, exit, filter, sizing, alpha
    holding_period  VARCHAR(32),                  -- intraday, short(1-3d), medium(3-10d), long(10d+)
    data_requirement VARCHAR(32),                 -- price_only, volume, vwap, industry, fundamental
    market_regime   VARCHAR(32),                  -- trending, ranging, volatile, any
    complexity      VARCHAR(32),                  -- simple, medium, complex

    -- Performance metadata (optional, populated after backtest validation)
    avg_return      DECIMAL(10,6),
    sharpe_ratio    DECIMAL(10,4),
    max_drawdown    DECIMAL(10,4),
    win_rate        DECIMAL(5,4),
    tested_at       TIMESTAMPTZ,

    -- Metadata
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for multi-dimensional queries
CREATE INDEX idx_factors_source ON factors(source);
CREATE INDEX idx_factors_category ON factors(category);
CREATE INDEX idx_factors_signal_type ON factors(signal_type);
CREATE INDEX idx_factors_holding_period ON factors(holding_period);
CREATE INDEX idx_factors_multi ON factors(category, signal_type, holding_period, data_requirement);
CREATE INDEX idx_factors_active ON factors(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_factors_description ON factors USING GIN (to_tsvector('english', description));

-- Strategy-factor relationship tracking
CREATE TABLE strategy_factors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    factor_id       UUID NOT NULL REFERENCES factors(id) ON DELETE CASCADE,
    usage_type      VARCHAR(32),                  -- "entry_signal", "exit_signal", "filter"
    parameters      JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(strategy_id, factor_id, usage_type)
);

CREATE INDEX idx_strategy_factors_strategy ON strategy_factors(strategy_id);
CREATE INDEX idx_strategy_factors_factor ON strategy_factors(factor_id);
CREATE INDEX idx_strategy_factors_usage ON strategy_factors(usage_type);
