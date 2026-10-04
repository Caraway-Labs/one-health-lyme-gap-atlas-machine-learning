-- ML #62 amendment: existing V072 approved DEV consumer route only.
-- No outcome summaries: release/source metadata, source status N, identity
-- and SVI eligibility checks only, before selecting taxon or seeing outcomes.
-- 60s per statement; <=2 release + <=3 source + <=12 status aggregate rows.
ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 60;
SELECT release_id, schema_version, methodology_version, bundle_sha256,
       generated_at, limitations
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_RELEASE_V
LIMIT 2;
SELECT source_key, label, vintage, source_url, note
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_SOURCE_METADATA_V
WHERE source_key IN ('tick', 'context_svi')
ORDER BY source_key
LIMIT 3;
WITH statuses AS (
    SELECT release_id, fips, state, svi_percentile,
           taxon_field, source_status
    FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_ATLAS_V
    UNPIVOT INCLUDE NULLS (
        source_status FOR taxon_field IN (scapularis_status, pacificus_status)
    )
)
SELECT release_id, taxon_field, source_status,
       COUNT(*) AS county_rows,
       COUNT(DISTINCT fips) AS unique_counties,
       COUNT(DISTINCT state) AS unique_states,
       COUNT_IF(fips IS NULL OR NOT REGEXP_LIKE(fips, '^[0-9]{5}$')) AS invalid_fips,
       COUNT_IF(svi_percentile IS NULL) AS svi_null,
       COUNT_IF(svi_percentile < 0 OR svi_percentile > 1) AS svi_invalid_domain
FROM statuses
GROUP BY release_id, taxon_field, source_status
ORDER BY release_id, taxon_field, source_status
LIMIT 12;
SELECT LAST_QUERY_ID() AS screen_query_id;
