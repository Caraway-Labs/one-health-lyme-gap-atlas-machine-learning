-- ML #61 existing authorized DEV consumer route; read-only value/provenance audit.
-- Validate context first with this same connection/schema. No private sources,
-- grants or role changes. Each SELECT returns at most 50 rows, timeout 30 sec.
-- This verifies visible current consumer fields, never substitutes 2023 for 2022.
USE SCHEMA ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION;
ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=30;

SELECT release_id, bundle_sha256, schema_version, methodology_version, generated_at, limitations
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_RELEASE_V
LIMIT 2;

SELECT release_id, COUNT(*) AS county_rows, COUNT(DISTINCT fips) AS unique_fips,
       COUNT_IF(NOT REGEXP_LIKE(fips, '^[0-9]{5}$')) AS malformed_fips,
       COUNT_IF(population IS NULL OR population <= 0) AS missing_or_nonpositive_population,
       COUNT_IF(svi_percentile IS NULL) AS missing_svi,
       COUNT_IF(svi_percentile < 0 OR svi_percentile > 1) AS invalid_svi,
       COUNT_IF(population=-999 OR svi_percentile=-999) AS sentinel_rows
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_ATLAS_V
GROUP BY release_id
LIMIT 2;

SELECT source_key, label, vintage, source_url, note
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_SOURCE_METADATA_V
WHERE source_key IN ('human', 'context_svi')
LIMIT 2;

SELECT measure_id, unit, denominator, temporal_grain, missingness_semantics, release_version
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_MEASURE_METADATA_V
WHERE measure_id IN ('population_2022', 'svi_percentile_2022',
                     'case_count_floor_2022', 'case_count_floor_2023', 'incidence_floor_2023')
LIMIT 10;

-- Scope requested in follow-up: current status visibility only, no tick EDA.
SELECT scapularis_status, pacificus_status, burgdorferi_status, COUNT(*) AS county_rows
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_ATLAS_V
GROUP BY scapularis_status, pacificus_status, burgdorferi_status
LIMIT 50;
