-- Issue 110 peer-county cluster inputs. Aggregates and one county row per FIPS.
-- No geometry, payload, part text, limitation text, case floor, or incidence floor.

-- @@ release_identity
SELECT
    RELEASE_ID,
    SCHEMA_VERSION,
    METHODOLOGY_VERSION,
    SCOPE,
    BUNDLE_SHA256
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V

-- @@ atlas_rows
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
ORDER BY FIPS

-- @@ climate_county
SELECT
    COUNTY_FIPS,
    AVG(IFF(
        MEASURE_ID = 'nclimgrid_tavg_county_day'
        AND VALUE_STATE IN ('OBSERVED', 'ZERO')
        AND VALUE_NATIVE_DOUBLE IS NOT NULL,
        VALUE_NATIVE_DOUBLE,
        NULL
    )) AS TAVG_C,
    SUM(IFF(
        MEASURE_ID = 'nclimgrid_tavg_county_day'
        AND VALUE_STATE IN ('OBSERVED', 'ZERO')
        AND VALUE_NATIVE_DOUBLE IS NOT NULL,
        1,
        0
    )) AS TAVG_DAYS,
    AVG(IFF(
        MEASURE_ID = 'nclimgrid_prcp_county_day'
        AND VALUE_STATE IN ('OBSERVED', 'ZERO')
        AND VALUE_NATIVE_DOUBLE IS NOT NULL,
        VALUE_NATIVE_DOUBLE,
        NULL
    )) AS PRCP_MM,
    SUM(IFF(
        MEASURE_ID = 'nclimgrid_prcp_county_day'
        AND VALUE_STATE IN ('OBSERVED', 'ZERO')
        AND VALUE_NATIVE_DOUBLE IS NOT NULL,
        1,
        0
    )) AS PRCP_DAYS
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V
WHERE MEASURE_ID IN ('nclimgrid_tavg_county_day', 'nclimgrid_prcp_county_day')
GROUP BY COUNTY_FIPS

-- @@ nlcd_county_total
SELECT COUNT(DISTINCT COUNTY_FIPS) AS COUNTY_N
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V
WHERE STARTSWITH(MEASURE_ID, 'nlcd_')
