-- Read-only ML #86 feasibility inventory; approved DEV presentation view only.
-- Validate DEV user/role/database/schema/warehouse before execution.
-- A single aggregate returns one row; no raw/private lineage or source extraction.
-- DATA #513 owns this current-release projection. Counts are NOT label admission.
SELECT COUNT(*) AS source_observations,
       COUNT(DISTINCT county_fips) AS counties,
       MIN(period_start) AS first_period,
       MAX(period_end) AS last_period
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V;
