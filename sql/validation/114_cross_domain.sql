-- ML #114 cross-domain associations.
-- Intent: read. No write is authorized by this file.
-- Environment: ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION.
-- Role: OH_LYME_ML_AGENT. Warehouse: OH_LYME_ML_LAB_XS_WH.
-- Release pin: governed-2026-10-15-january-climate-prod.
-- County rows stay in memory. They are not exported to a file.
-- Climate day values are not selected. Geometry text is not selected.
-- Statements are split on lines that start with '-- @@ '.

-- @@ release_identity
SELECT
    RELEASE_ID,
    SCHEMA_VERSION,
    BUNDLE_SHA256,
    METHODOLOGY_VERSION,
    SCOPE
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V

-- @@ cohort_rows
SELECT
    FIPS,
    COUNTY,
    STATE,
    RELEASE_ID,
    POPULATION,
    SVI_PERCENTILE,
    UNINSURED_PERCENTILE,
    RUCC_2023,
    HUMAN_STATUS,
    TICK_STATUS,
    BURGDORFERI_STATUS,
    IN_CONTIGUOUS_TICK_SCOPE
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V
