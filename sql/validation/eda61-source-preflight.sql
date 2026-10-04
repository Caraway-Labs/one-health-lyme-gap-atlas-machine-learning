-- ML #61; read-only DEV preflight, NOT executed in the blocked session.
-- First validate all five context fields through the approved named PAT route.
-- Requires OH_LYME_DEV_READ, DEV database and explicit approved non-null schema.
-- Set connector statement_timeout_in_seconds=30, maximum 50 returned rows.
-- Bind :human_version, :human_run, :svi_version, :svi_run, :human_artifact,
-- :svi_artifact, :human_sha256, :svi_sha256 from reviewed release membership.
-- No production, no writes, no export. Existing release identities are candidates,
-- not proof of current DEV approval or 2022 case scope.
SELECT data_source_version_id, resource_key, status, approved_decision_id, retired_at
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.GOVERNANCE.DATA_SOURCE_VERSIONS
WHERE data_source_version_id IN (:human_version, :svi_version)
LIMIT 2;

SELECT ingestion_run_id, resource_key, status
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.GOVERNANCE.INGESTION_RUNS
WHERE ingestion_run_id IN (:human_run, :svi_run)
LIMIT 2;

SELECT artifact_id, ingestion_run_id, sha256
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.GOVERNANCE.RAW_ARTIFACTS
WHERE (artifact_id=:human_artifact AND ingestion_run_id=:human_run AND sha256=:human_sha256)
   OR (artifact_id=:svi_artifact AND ingestion_run_id=:svi_run AND sha256=:svi_sha256)
LIMIT 2;

SELECT ingestion_run_id, COUNT(*) AS quality_checks,
       COUNT_IF(severity='BLOCKING' AND status='FAILED') AS blocking_failures
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.GOVERNANCE.DATA_QUALITY_RESULTS
WHERE ingestion_run_id IN (:human_run, :svi_run)
GROUP BY ingestion_run_id
LIMIT 2;

-- These are source-row counts, not unique county N. Validate every returned case
-- status and its governed definition before confirming confirmed+probable scope.
SELECT report_year, case_status, COUNT(*) AS source_observation_rows,
       COUNT(DISTINCT county_fips) AS distinct_source_geographies,
       COUNT_IF(REGEXP_LIKE(county_fips, '^[0-9]{5}$')) AS numeric_fips_rows
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.CONFORMED.CONFORMED_CDC_LYME_X5J9_WYBP
WHERE data_source_version_id=:human_version AND ingestion_run_id=:human_run
  AND report_year=2022
GROUP BY report_year, case_status
LIMIT 20;
