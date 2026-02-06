-- Migration 004: Add RUB-based columns and populate from existing EUR-based columns
-- This migration is additive and non-destructive: it creates new `rub_*` columns,
-- populates them from existing `eur_*` columns when available, and leaves the
-- original `eur_*` columns intact for rollback/inspection.

BEGIN;

ALTER TABLE mcol1_external_data
    ADD COLUMN IF NOT EXISTS rub_usd NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS rub_usd_pair_desc VARCHAR(10),
    ADD COLUMN IF NOT EXISTS rub_cny NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS rub_cny_pair_desc VARCHAR(10),
    ADD COLUMN IF NOT EXISTS rub_eur NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS rub_eur_pair_desc VARCHAR(10),
    ADD COLUMN IF NOT EXISTS rub_inr NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS rub_inr_pair_desc VARCHAR(10),
    ADD COLUMN IF NOT EXISTS rub_aed NUMERIC(18,6),
    ADD COLUMN IF NOT EXISTS rub_aed_pair_desc VARCHAR(10);

-- Populate RUB columns using EUR-based columns when present.
-- Conversions follow the same logic used in application code:
--   rub_usd = eur_rub / eur_usd
--   rub_cny = eur_rub / eur_cny
--   rub_eur = eur_rub
--   rub_inr = eur_rub / eur_inr
--   rub_aed = eur_rub / eur_aed

UPDATE mcol1_external_data
SET
    rub_usd = CASE WHEN eur_rub IS NOT NULL AND eur_usd IS NOT NULL AND eur_usd <> 0 THEN (eur_rub / eur_usd) ELSE NULL END,
    rub_cny = CASE WHEN eur_rub IS NOT NULL AND eur_cny IS NOT NULL AND eur_cny <> 0 THEN (eur_rub / eur_cny) ELSE NULL END,
    rub_eur = eur_rub,
    rub_inr = CASE WHEN eur_rub IS NOT NULL AND eur_inr IS NOT NULL AND eur_inr <> 0 THEN (eur_rub / eur_inr) ELSE NULL END,
    rub_aed = CASE WHEN eur_rub IS NOT NULL AND eur_aed IS NOT NULL AND eur_aed <> 0 THEN (eur_rub / eur_aed) ELSE NULL END;

-- Set pair description strings to match application enum values where we populated values
UPDATE mcol1_external_data
SET
    rub_usd_pair_desc = CASE WHEN rub_usd IS NOT NULL THEN 'RUB/USD' ELSE NULL END,
    rub_cny_pair_desc = CASE WHEN rub_cny IS NOT NULL THEN 'RUB/CNY' ELSE NULL END,
    rub_eur_pair_desc = CASE WHEN rub_eur IS NOT NULL THEN 'RUB/EUR' ELSE NULL END,
    rub_inr_pair_desc = CASE WHEN rub_inr IS NOT NULL THEN 'RUB/INR' ELSE NULL END,
    rub_aed_pair_desc = CASE WHEN rub_aed IS NOT NULL THEN 'RUB/AED' ELSE NULL END;

COMMIT;

-- Note: This migration intentionally does not DROP the original `eur_*` columns.
-- Removing or renaming those columns is a breaking change and should be planned
-- separately (schema migration + application deploy coordination).
