-- ============================================================================
-- KOLMO.wiazor.com v.2.1.1 - Initial Database Schema
-- 
-- 🔒 NORMATIVE: This schema implements Technical Specification v.2.1.1
-- 
-- Tables:
--   - mcol1_external_data: Raw provider exchange rates (immutable audit trail)
--   - mcol1_compute_data: Derived KOLMO metrics with Amendment A1 constraints
--   - mcol1_provider_stats: Operational telemetry for provider monitoring
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- Table: mcol1_external_data (Raw Provider Data)
-- 🔒 REQ-4.2: Immutable audit trail - append-only for numeric rate columns
-- ============================================================================

DROP TABLE IF EXISTS mcol1_external_data CASCADE;

CREATE TABLE mcol1_external_data (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL UNIQUE,
    
    -- Raw EUR-based rates (Frankfurter/CBR format)
    eur_usd NUMERIC(18, 6),
    eur_usd_pair_desc VARCHAR(10) CHECK (eur_usd_pair_desc IN ('EUR/USD', 'USD/EUR')),
    
    eur_cny NUMERIC(18, 6),
    eur_cny_pair_desc VARCHAR(10) CHECK (eur_cny_pair_desc IN ('EUR/CNY', 'CNY/EUR')),
    
    eur_rub NUMERIC(18, 6),
    eur_rub_pair_desc VARCHAR(10) CHECK (eur_rub_pair_desc IN ('EUR/RUB', 'RUB/EUR')),
    
    eur_inr NUMERIC(18, 6),
    eur_inr_pair_desc VARCHAR(10) CHECK (eur_inr_pair_desc IN ('EUR/INR', 'INR/EUR')),
    
    eur_aed NUMERIC(18, 6),
    eur_aed_pair_desc VARCHAR(10) CHECK (eur_aed_pair_desc IN ('EUR/AED', 'AED/EUR')),
    
    -- Audit trail
    mcol1_snapshot_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    trace_id UUID NOT NULL DEFAULT gen_random_uuid(),
    sources JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indices for time-series queries
CREATE INDEX idx_external_date_desc ON mcol1_external_data (date DESC);
CREATE INDEX idx_external_snapshot ON mcol1_external_data (mcol1_snapshot_id);
CREATE INDEX idx_external_sources ON mcol1_external_data USING GIN (sources);

-- Documentation comments
COMMENT ON TABLE mcol1_external_data IS 
'🔒 Immutable raw exchange rates from external providers. NEVER modify numeric rate fields after insert - append-only for audit compliance per SEC/CFTC requirements.';

COMMENT ON COLUMN mcol1_external_data.mcol1_snapshot_id IS
'UUID linking this raw snapshot to derived metrics in mcol1_compute_data. Enables audit query: "Show me the provider data that produced Winner=IOU2 on 2026-01-15"';

COMMENT ON COLUMN mcol1_external_data.sources IS
'JSONB provenance tracking. Example: {"eur_usd": "frankfurter", "eur_cny": "cbr", "fetch_time": "2026-01-15T22:00:05-05:00"}';

-- ============================================================================
-- Table: mcol1_compute_data (Derived KOLMO Metrics)
-- 🔒 REQ-4.4 (Amendment A1): kolmo_value MUST be NUMERIC(28,18) exact product
-- 🔒 REQ-4.5: winner_reason MUST contain explainability metadata
-- ============================================================================

DROP TABLE IF EXISTS mcol1_compute_data CASCADE;

CREATE TABLE mcol1_compute_data (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL UNIQUE,
    
    -- KOLMO rates (standardized notation)
    r_me4u NUMERIC(18, 6) NOT NULL CHECK (r_me4u > 0),
    r_iou2 NUMERIC(18, 6) NOT NULL CHECK (r_iou2 > 0),
    r_uome NUMERIC(18, 6) NOT NULL CHECK (r_uome > 0),
    
    -- 🔒 KOLMO invariant (Amendment A1: EXACT decimal)
    kolmo_value NUMERIC(28, 18) NOT NULL,
    kolmo_deviation NUMERIC(28, 18) NOT NULL,
    kolmo_state VARCHAR(25) NOT NULL 
        CHECK (kolmo_state IN ('OK', 'WARN', 'CRITICAL')),
    
    -- Distance metrics (deviation from parity)
    dist_me4u NUMERIC(10, 4) NOT NULL,
    dist_iou2 NUMERIC(10, 4) NOT NULL,
    dist_uome NUMERIC(10, 4) NOT NULL,
    
    -- RelativePath metrics (improvement tracking)
    relpath_me4u NUMERIC(10, 4),
    relpath_iou2 NUMERIC(10, 4),
    relpath_uome NUMERIC(10, 4),
    
    -- Volatility metrics (daily volatility index)
    vol_me4u NUMERIC(28, 18),
    vol_iou2 NUMERIC(28, 18),
    vol_uome NUMERIC(28, 18),
    
    -- Winner selection
    winner VARCHAR(5) NOT NULL CHECK (winner IN ('ME4U', 'IOU2', 'UOME')),
    winner_reason JSONB NOT NULL,
    
    -- Audit trail (link to raw data)
    mcol1_snapshot_id UUID NOT NULL 
        REFERENCES mcol1_external_data(mcol1_snapshot_id) ON DELETE RESTRICT,
    mcol1_snapshot_compute_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    trace_compute_id UUID NOT NULL DEFAULT gen_random_uuid(),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 🔒 AMENDMENT A1: Exact KOLMO constraint
    CONSTRAINT chk_kolmo_exact_product 
        CHECK (kolmo_value = r_me4u * r_iou2 * r_uome)
);

-- Indices for query performance
CREATE INDEX idx_compute_date_desc ON mcol1_compute_data (date DESC);
CREATE INDEX idx_compute_winner ON mcol1_compute_data (winner, date DESC);
CREATE INDEX idx_compute_state ON mcol1_compute_data (kolmo_state, date DESC);
CREATE INDEX idx_compute_snapshot ON mcol1_compute_data (mcol1_snapshot_id);

-- Documentation comments
COMMENT ON TABLE mcol1_compute_data IS
'Derived KOLMO metrics computed from mcol1_external_data. Every row MUST link to exactly one external snapshot via mcol1_snapshot_id FK.';

COMMENT ON COLUMN mcol1_compute_data.r_me4u IS
'ME4U coin rate: USD/CNY (US Dollars per 1 Chinese Yuan). Example: 0.1434 means 1 yuan = 0.1434 dollars.';

COMMENT ON COLUMN mcol1_compute_data.r_iou2 IS
'IOU2 coin rate: EUR/USD (Euros per 1 US Dollar). Example: 0.8599 means 1 dollar = 0.8599 euros.';

COMMENT ON COLUMN mcol1_compute_data.r_uome IS
'UOME coin rate: CNY/EUR (Chinese Yuan per 1 Euro). Example: 8.11 means 1 euro = 8.11 yuan.';

COMMENT ON COLUMN mcol1_compute_data.kolmo_value IS
'🔒 CRITICAL: Exact unrounded product r_me4u * r_iou2 * r_uome stored as NUMERIC(28,18) per Amendment A1. MUST NOT be approximated or cast to float. Database constraint chk_kolmo_exact_product enforces exact equality.';

COMMENT ON COLUMN mcol1_compute_data.winner_reason IS
'🔒 EXPLAINABILITY: JSONB explaining Winner selection. Example: {"me4u_relpath": -0.35, "iou2_relpath": 3.24, "uome_relpath": 0.05, "selection_rule": "max_positive_alphabetical_tiebreak", "winner": "IOU2"}';

COMMENT ON CONSTRAINT chk_kolmo_exact_product ON mcol1_compute_data IS
'🔒 Amendment A1 enforcement: Database rejects any INSERT/UPDATE where stored kolmo_value differs from the exact product of r_me4u * r_iou2 * r_uome. This prevents rounding bugs at the database layer (defense-in-depth).';

-- ============================================================================
-- Trigger: validate_kolmo_exact (Defense-in-Depth)
-- 🔒 REQ-5.10: Database MUST have validation trigger on mcol1_compute_data
-- ============================================================================

CREATE OR REPLACE FUNCTION validate_kolmo_exact()
RETURNS TRIGGER AS $$
DECLARE
    computed_product NUMERIC(28,18);
BEGIN
    computed_product := NEW.r_me4u * NEW.r_iou2 * NEW.r_uome;
    
    -- Check if stored value equals computed product
    IF NEW.kolmo_value <> computed_product THEN
        RAISE EXCEPTION 
            '🔒 Amendment A1 Violation: kolmo_value (%) != r_me4u * r_iou2 * r_uome (%). Difference: %. Row rejected.',
            NEW.kolmo_value,
            computed_product,
            (NEW.kolmo_value - computed_product)
        USING ERRCODE = '23514';  -- check_violation
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_kolmo_invariant
    BEFORE INSERT OR UPDATE ON mcol1_compute_data
    FOR EACH ROW
    EXECUTE FUNCTION validate_kolmo_exact();

COMMENT ON FUNCTION validate_kolmo_exact IS
'🔒 Amendment A1 enforcement trigger: Rejects any row where kolmo_value is not the EXACT product of r_me4u * r_iou2 * r_uome. Provides defense-in-depth if application layer has bugs.';

-- ============================================================================
-- Table: mcol1_provider_stats (Operational Telemetry)
-- 🔒 REQ-4.7: Track provider reliability for SLA monitoring
-- ============================================================================

DROP TABLE IF EXISTS mcol1_provider_stats CASCADE;

CREATE TABLE mcol1_provider_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    provider_name VARCHAR(20) NOT NULL 
        CHECK (provider_name IN ('frankfurter', 'cbr', 'twelvedata')),
    attempt_order INTEGER NOT NULL CHECK (attempt_order BETWEEN 1 AND 3),
    success BOOLEAN NOT NULL,
    latency_ms INTEGER CHECK (latency_ms >= 0),
    error_type VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_provider_stats_date ON mcol1_provider_stats (date DESC);
CREATE INDEX idx_provider_stats_name ON mcol1_provider_stats (provider_name, success);

COMMENT ON TABLE mcol1_provider_stats IS
'🔒 Operational telemetry: Track provider success rates, latencies, and error patterns. Used for SLA monitoring and alerting when primary provider degrades.';

COMMENT ON COLUMN mcol1_provider_stats.attempt_order IS
'Provider fallback order: 1=primary (Frankfurter), 2=fallback1 (CBR), 3=fallback2 (TwelveData).';

COMMENT ON COLUMN mcol1_provider_stats.error_type IS
'Standardized error codes: HTTP_500, HTTP_404, TIMEOUT, PARSE_ERROR, MISSING_CURRENCY, RATE_OUT_OF_BOUNDS.';

-- ============================================================================
-- Helper Views
-- ============================================================================

-- View: Latest winner (for quick API queries)
CREATE OR REPLACE VIEW v_latest_winner AS
SELECT 
    c.date,
    c.winner,
    c.r_me4u,
    c.r_iou2,
    c.r_uome,
    c.kolmo_value,
    c.kolmo_deviation,
    c.kolmo_state,
    c.dist_me4u,
    c.dist_iou2,
    c.dist_uome,
    c.relpath_me4u,
    c.relpath_iou2,
    c.relpath_uome,
    c.winner_reason,
    c.mcol1_snapshot_id
FROM mcol1_compute_data c
ORDER BY c.date DESC
LIMIT 1;

COMMENT ON VIEW v_latest_winner IS
'Quick access to most recent winner data for /api/v1/winner/latest endpoint.';

-- View: Provider success rate (rolling 7 days)
CREATE OR REPLACE VIEW v_provider_success_rate AS
SELECT 
    provider_name,
    COUNT(*) FILTER (WHERE success = true) AS success_count,
    COUNT(*) AS total_count,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE success = true) / NULLIF(COUNT(*), 0), 
        2
    ) AS success_rate_pct,
    AVG(latency_ms) FILTER (WHERE success = true) AS avg_latency_ms
FROM mcol1_provider_stats
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY provider_name
ORDER BY provider_name;

COMMENT ON VIEW v_provider_success_rate IS
'Rolling 7-day provider success rates for SLA monitoring. REQ-4.8: Alert if Frankfurter < 95%.';

-- ============================================================================
-- Seed Data (Optional - for testing)
-- ============================================================================

-- Uncomment to insert sample data for testing:
-- INSERT INTO mcol1_external_data (date, eur_usd, eur_usd_pair_desc, eur_cny, eur_cny_pair_desc, sources)
-- VALUES 
--     ('2026-01-15', 1.163, 'EUR/USD', 8.11, 'EUR/CNY', 
--      '{"provider": "frankfurter", "fetch_time": "2026-01-15T22:00:00Z"}'::jsonb);

-- ============================================================================
-- Grant Permissions (Production)
-- 🔒 REQ-7.6: API service MUST use read-only role
-- ============================================================================

-- Create read-only role for API service
-- DO $$
-- BEGIN
--     IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kolmo_reader') THEN
--         CREATE ROLE kolmo_reader WITH LOGIN PASSWORD 'CHANGE_IN_VAULT';
--     END IF;
-- END $$;

-- GRANT SELECT ON mcol1_external_data TO kolmo_reader;
-- GRANT SELECT ON mcol1_compute_data TO kolmo_reader;
-- GRANT SELECT ON mcol1_provider_stats TO kolmo_reader;
-- GRANT SELECT ON v_latest_winner TO kolmo_reader;
-- GRANT SELECT ON v_provider_success_rate TO kolmo_reader;

-- ============================================================================
-- Migration Complete
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '=============================================================';
    RAISE NOTICE '✅ KOLMO v.2.1.1 Schema Migration COMPLETED';
    RAISE NOTICE '=============================================================';
    RAISE NOTICE 'Tables created:';
    RAISE NOTICE '  - mcol1_external_data (raw provider data)';
    RAISE NOTICE '  - mcol1_compute_data (derived KOLMO metrics)';
    RAISE NOTICE '  - mcol1_provider_stats (operational telemetry)';
    RAISE NOTICE 'Views created:';
    RAISE NOTICE '  - v_latest_winner';
    RAISE NOTICE '  - v_provider_success_rate';
    RAISE NOTICE 'Triggers installed:';
    RAISE NOTICE '  - trg_validate_kolmo_invariant (Amendment A1)';
    RAISE NOTICE '=============================================================';
END $$;
