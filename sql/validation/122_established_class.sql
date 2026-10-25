-- ML #122 established-tick class rows for an in-memory anomaly screen.
-- Intent: read. No write is authorized by this file.
-- Environment: ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION.
-- Role: OH_LYME_ML_AGENT. Warehouse: OH_LYME_ML_LAB_XS_WH.
-- Release pin: governed-2026-10-15-january-climate-prod.
-- The class-row statement is held in memory for the fit. County rows are not
-- exported to a file. Statements are split on lines that start with '-- @@ '.

-- @@ release_identity
SELECT
    RELEASE_ID,
    SCHEMA_VERSION,
    BUNDLE_SHA256,
    METHODOLOGY_VERSION,
    SCOPE
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V

-- @@ class_gate
SELECT
    COUNT(*) AS CLASS_N,
    COUNT(DISTINCT FIPS) AS FIPS_N,
    SUM(IFF(REGEXP_LIKE(FIPS, '^[0-9]{5}$'), 1, 0)) AS FIPS_PATTERN_N,
    COUNT(DISTINCT RELEASE_ID) AS RELEASE_N,
    MIN(RELEASE_ID) AS RELEASE_MIN,
    MAX(RELEASE_ID) AS RELEASE_MAX,
    SUM(IFF(
        HUMAN_STATUS = 'no_county_linked_record' AND BURGDORFERI_STATUS = 'Present',
        1,
        0
    )) AS DOUBLE_GAP_N,
    SUM(IFF(HUMAN_STATUS = 'no_county_linked_record', 1, 0)) AS GAP_810_N
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V
WHERE TICK_STATUS = 'Established'

-- @@ class_rows
SELECT
    FIPS,
    COUNTY,
    STATE,
    POPULATION,
    SVI_PERCENTILE,
    UNINSURED_PERCENTILE,
    RUCC_2023,
    HUMAN_STATUS,
    BURGDORFERI_STATUS,
    TICK_STATUS
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V
WHERE TICK_STATUS = 'Established'
