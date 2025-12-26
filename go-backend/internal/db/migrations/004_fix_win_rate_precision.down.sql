-- Revert criteria_min_win_rate precision
ALTER TABLE optimization_runs
    ALTER COLUMN criteria_min_win_rate TYPE DECIMAL(5, 4);
