-- ML #62: bounded DEV consumer availability audit, no outcome values.
-- Approved object: DEV.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V (Data V127).
-- Source identity comes from its PUBLISHED immutable release, not alpha fixtures.
-- At most 10 aggregate rows. Session-only 60s timeout; no object writes.
ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 60;
SELECT release_version, measure_id, source_key,
       COUNT(*) AS observation_rows,
       COUNT(DISTINCT county_fips) AS unique_counties
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V
GROUP BY release_version, measure_id, source_key
ORDER BY release_version, measure_id, source_key
LIMIT 10;
SELECT LAST_QUERY_ID() AS profile_query_id;
