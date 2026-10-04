-- ML #61; prepared read-only DEV extraction, NOT executed in the blocked run.
-- Prefer an existing immutable snapshot with matching lineage before executing.
-- Run only after context, authority, source release, case scope, population and
-- canonical mapping preflight PASS. Review counts first; one sequential export.
-- Set statement_timeout_in_seconds=30; never widen scope or cap automatically.
-- Bind approved :human_version/:human_run/:svi_run, never interpolate selectors.
-- Fetch a sentinel beyond the permitted row cap; abort if it is returned.
-- Output is transient in ignored data/local/, never committed.
SELECT source_record_id, county_fips, report_year, case_status, frequency
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.CONFORMED.CONFORMED_CDC_LYME_X5J9_WYBP
WHERE data_source_version_id=:human_version AND ingestion_run_id=:human_run
  AND report_year=2022
ORDER BY source_record_id
LIMIT 250001;

-- Uses the retained revision route from data semantic_release._read_source_rows.
-- Do not combine revisions with the fallback table: that duplicates source rows.
-- If revisions are empty, use the existing data harness's reviewed fallback only
-- after proving exact run/definition/digest/row-count identity; record that query.
SELECT source_record_id, source_row_hash,
       payload:STCNTY::VARCHAR AS county_fips,
       payload:E_TOTPOP AS population,
       payload:RPL_THEMES AS svi_percentile
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.GOVERNANCE.GOVERNED_SOURCE_RECORD_REVISIONS
WHERE resource_key='cdc_atsdr_svi_2022_county'
  AND ingestion_run_id=:svi_run AND source_definition_version=1
ORDER BY source_record_id
LIMIT 3145;
