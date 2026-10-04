-- READ ONLY, ML #65; one immutable published DEV release, no internal/raw reads.
-- Execute only after validated DEV READ context. Bind the verified release ID.
-- 30-second execute timeout; 3,145 output cap detects excess canonical counties.
-- No geometry, population, human outcomes or restricted source rows exported.
SELECT release_id, fips, in_contiguous_tick_scope,
       scapularis_status, pacificus_status, burgdorferi_status
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_ATLAS_V
WHERE release_id = %s
ORDER BY fips
LIMIT 3145;
