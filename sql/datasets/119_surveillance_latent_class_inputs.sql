-- ML #119 / #131 read-only county extract.
-- Intent: read. No write is authorized.
-- Environment: ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION.
-- Role: OH_LYME_PROD_READ. Warehouse: COMPUTE_WH.
-- Source: PRESENTATION.CURRENT_COUNTY_ATLAS_V.
-- Release: governed-2026-10-06-nlcd-demo-cohort.
-- Bundle SHA-256: 603afb135a1a5c958d1d56d48d580d9942c67eb38986caf8b4b3acf69fcde2c9.
-- Bound: one row per county. The admitted cohort has 3,144 rows.
-- Confirm that release identity with sql/validation/119_release_identity.sql
-- before using the rows. This file is not itself permission to run.

SELECT
    FIPS,
    STATE,
    HUMAN_STATUS,
    SCAPULARIS_STATUS,
    PACIFICUS_STATUS,
    BURGDORFERI_STATUS,
    POPULATION
FROM PRESENTATION.CURRENT_COUNTY_ATLAS_V;
