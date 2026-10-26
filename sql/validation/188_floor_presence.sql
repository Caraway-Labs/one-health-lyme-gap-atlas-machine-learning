-- Issue 188 published-floor presence inputs. One county row per FIPS.
-- Regime shares use tick status, pathogen status, and rural-urban code.
-- Case floors, tier scores, land cover, and free text are not selected.

-- @@ release_identity
SELECT
    RELEASE_ID,
    SCHEMA_VERSION,
    METHODOLOGY_VERSION,
    SCOPE,
    BUNDLE_SHA256
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V

-- @@ cohort_rows
SELECT
    STATE,
    FIPS,
    RELEASE_ID,
    POPULATION,
    SVI_PERCENTILE,
    UNINSURED_PERCENTILE,
    RUCC_2023,
    HUMAN_STATUS,
    TICK_STATUS,
    BURGDORFERI_STATUS
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V
ORDER BY FIPS
