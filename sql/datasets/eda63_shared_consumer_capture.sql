-- Parent-requested shared outcome-blind consumer capture for ML #61-65.
-- Existing DEV read authority only; no private tables, writes or role changes.
-- Run after separate five-field context validation. At most 150 seconds SQL
-- across five bounded SELECTs; session timeout does not alter persisted objects.
-- Freeze a new local output, then require before/after release/hash equality.
-- Human floors here are 2023, never substitute for #61's required 2022 numerator.
-- No source-record authority or REVIEWED metadata admission follows from values.
ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=30;
SELECT release_id, schema_version, generated_at, bundle_sha256, methodology_version
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_RELEASE_V
LIMIT 1;
SELECT *
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_SOURCE_METADATA_V
ORDER BY source_key
LIMIT 10;
SELECT *
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_MEASURE_METADATA_V
LIMIT 100;
SELECT release_id, fips, state, population, human_status,
       case_count_floor_2023, incidence_floor_2023, state_unallocated_records_2023,
       tick_status, scapularis_status, pacificus_status, burgdorferi_status,
       svi_percentile, uninsured_percentile, uninsured_percent, rucc_2023,
       evidence_completeness
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_ATLAS_V
WHERE release_id = 'governed-2026-09-17-unknown-coverage'
ORDER BY fips
LIMIT 3145;
SELECT release_id, schema_version, generated_at, bundle_sha256, methodology_version
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_RELEASE_V
LIMIT 1;
