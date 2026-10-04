-- ML #63: read-only DEV published presentation route; no internal/raw reads.
-- Run after separate verified DEV context. Session-only timeout, no object writes.
-- Three SELECT statements: <=1 release, <=10 source metadata, <=3145 county rows.
-- 3145 is an overflow sentinel; require exact canonical identity before analysis.
-- Source versions/digests are pinned by the data-owned release manifest.
ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=30;
SELECT release_id, schema_version, generated_at, bundle_sha256, methodology_version
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_RELEASE_V
LIMIT 1;
SELECT source_key, label, vintage, source_url, note
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_SOURCE_METADATA_V
ORDER BY source_key
LIMIT 10;
SELECT release_id, fips, state, svi_percentile, rucc_2023
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_ATLAS_V
WHERE release_id = 'governed-2026-09-17-unknown-coverage'
ORDER BY fips
LIMIT 3145;
