-- ============================================================================
-- KOLMO.wiazor.com v.2.1.1 - Migration 003: Update Provider Names
-- 
-- Changes:
--   - Remove CBR and TwelveData from provider_name constraint
--   - Add FreeCurrencyAPI as new fallback provider
-- ============================================================================

-- Drop the old constraint
ALTER TABLE mcol1_provider_stats 
DROP CONSTRAINT IF EXISTS mcol1_provider_stats_provider_name_check;

-- Add new constraint with updated provider list
ALTER TABLE mcol1_provider_stats 
ADD CONSTRAINT mcol1_provider_stats_provider_name_check 
CHECK (provider_name IN ('frankfurter', 'freecurrencyapi'));

-- Update comment
COMMENT ON COLUMN mcol1_provider_stats.provider_name IS
'Provider name. Valid values: frankfurter (primary), freecurrencyapi (fallback)';
