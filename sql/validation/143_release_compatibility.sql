-- ML #143 read-only release compatibility check.
-- Intent: read. No write is authorized.
-- Environment: ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION.
-- Role: OH_LYME_PROD_READ. Warehouse: COMPUTE_WH. Secondary roles: none.
-- Source: PRESENTATION.CURRENT_RELEASE_V. Bound: one release row.
-- Pinned fit release: governed-2026-10-15-january-climate-prod.
-- Pinned bundle SHA-256: 53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d.
-- This file is not itself permission to run. It does not read county rows
-- and it does not repair the Tier 1 release in Data #698.

SELECT
    CURRENT_TIMESTAMP() AS OBSERVED_AT,
    RELEASE_ID,
    SCHEMA_VERSION,
    METHODOLOGY_VERSION,
    SCOPE,
    BUNDLE_SHA256,
    TO_VARCHAR(GENERATED_AT) AS GENERATED_AT,
    TO_VARCHAR(LOADED_AT) AS LOADED_AT
FROM PRESENTATION.CURRENT_RELEASE_V;
