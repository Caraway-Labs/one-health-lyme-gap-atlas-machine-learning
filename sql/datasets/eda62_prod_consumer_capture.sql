-- Explicitly authorized ML #62 descriptive EDA capture; existing PROD consumer
-- views only, no object writes/private sources. One acquisition, keep private.
-- Context must first verify the runbook's existing PROD runtime read identity.
-- 30-second statement bounds; max 2 + 3145 + 1 + 2 returned rows.
ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 30;
SELECT release_id, schema_version, methodology_version, bundle_sha256,
       generated_at, limitations
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V
LIMIT 2;
SELECT c.release_id, r.bundle_sha256, c.fips, c.state,
       c.scapularis_status, c.pacificus_status, c.svi_percentile,
       c.burgdorferi_status
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V c
JOIN ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V r
  ON r.release_id = c.release_id
WHERE c.release_id = 'governed-2026-09-18-unknown-coverage'
  AND r.bundle_sha256 = '038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026'
ORDER BY c.fips
LIMIT 3145;
SELECT LAST_QUERY_ID() AS capture_query_id;
SELECT release_id, schema_version, methodology_version, bundle_sha256,
       generated_at, limitations
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V
LIMIT 2;
