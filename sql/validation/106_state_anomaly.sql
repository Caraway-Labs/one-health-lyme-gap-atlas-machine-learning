-- ML #106 state-relative anomaly screen.
-- Intent: read. No write is authorized by this file.
-- Environment: ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION.
-- Role: OH_LYME_ML_AGENT. Warehouse: OH_LYME_ML_LAB_XS_WH.
-- Release pin: governed-2026-10-15-january-climate-prod.
-- The county-row statement is held in memory for the fit. County rows are not
-- exported to a file. Statements are split on lines that start with '-- @@ '.

-- @@ release_identity
SELECT
    RELEASE_ID,
    SCHEMA_VERSION,
    BUNDLE_SHA256,
    METHODOLOGY_VERSION,
    SCOPE
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V

-- @@ cohort_gate
SELECT
    COUNT(*) AS ROW_N,
    COUNT(DISTINCT FIPS) AS FIPS_N,
    SUM(IFF(REGEXP_LIKE(FIPS, '^[0-9]{5}$'), 1, 0)) AS FIPS_PATTERN_N,
    COUNT(DISTINCT RELEASE_ID) AS RELEASE_N,
    SUM(IFF(HUMAN_STATUS = 'published_count_floor', 1, 0)) AS HUMAN_FLOOR_N,
    SUM(IFF(HUMAN_STATUS = 'no_county_linked_record', 1, 0)) AS HUMAN_NONE_N,
    SUM(IFF(
        HUMAN_STATUS = 'no_county_linked_record'
        AND BURGDORFERI_STATUS = 'Present'
        AND TICK_STATUS = 'Established',
        1,
        0
    )) AS DOUBLE_GAP_N
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V

-- @@ source_vintages
SELECT SOURCE_KEY, VINTAGE
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_SOURCE_METADATA_V
ORDER BY SOURCE_KEY

-- @@ cohort_rows
SELECT
    FIPS,
    COUNTY,
    STATE,
    POPULATION,
    SVI_PERCENTILE,
    UNINSURED_PERCENTILE,
    RUCC_2023,
    HUMAN_STATUS,
    TICK_STATUS,
    BURGDORFERI_STATUS,
    RELEASE_ID
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V
