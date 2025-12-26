-- Fix criteria_min_win_rate precision to allow percentages like 40.0
ALTER TABLE optimization_runs
    ALTER COLUMN criteria_min_win_rate TYPE DECIMAL(10, 4);
