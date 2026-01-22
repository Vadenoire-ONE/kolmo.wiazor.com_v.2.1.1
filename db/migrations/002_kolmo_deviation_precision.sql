-- ============================================================================
-- KOLMO.wiazor.com v.2.1.1 - Migration 002: Increase kolmo_deviation precision
-- 
-- Changes kolmo_deviation from NUMERIC(8, 4) to NUMERIC(18, 12)
-- to preserve 12 decimal places for precise JSON export
-- ============================================================================

-- Alter kolmo_deviation column to increase precision to 18 decimal places
ALTER TABLE mcol1_compute_data 
    ALTER COLUMN kolmo_deviation TYPE NUMERIC(28, 18);

COMMENT ON COLUMN mcol1_compute_data.kolmo_deviation IS
'KOLMO deviation from perfect invariant (1.0) with 18 decimal places precision. Formula: deviation = |kolmo_value - 1.0|';
