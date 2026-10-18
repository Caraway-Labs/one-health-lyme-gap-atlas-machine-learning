-- ML #119 / #131 read-only release identity check.
-- Intent: read. No write is authorized.
-- Environment: ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION.
-- Role: OH_LYME_PROD_READ. Warehouse: COMPUTE_WH.
-- Source: PRESENTATION.CURRENT_RELEASE_V. Bound: one release row.
-- Expected release: governed-2026-10-06-nlcd-demo-cohort.
-- Expected bundle SHA-256: 603afb135a1a5c958d1d56d48d580d9942c67eb38986caf8b4b3acf69fcde2c9.
-- This file is not itself permission to run.

SELECT
    RELEASE_ID,
    BUNDLE_SHA256
FROM PRESENTATION.CURRENT_RELEASE_V;
