-- ML #119 / #131 read-only release identity check.
-- Intent: read. No write is authorized.
-- Environment: ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION.
-- Role: OH_LYME_PROD_READ. Warehouse: COMPUTE_WH.
-- Source: PRESENTATION.CURRENT_RELEASE_V. Bound: one release row.
-- Expected release: governed-2026-10-15-january-climate-prod.
-- Expected bundle SHA-256: 53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d.
-- This file is not itself permission to run.

SELECT
    RELEASE_ID,
    BUNDLE_SHA256
FROM PRESENTATION.CURRENT_RELEASE_V;
