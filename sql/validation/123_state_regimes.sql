-- Issue 123 state reporting-regime inputs. One county row per FIPS.
-- No spatial column, payload, part text, limitation text, or case floor.

-- @@ release_identity
SELECT
    RELEASE_ID,
    SCHEMA_VERSION,
    METHODOLOGY_VERSION,
    SCOPE,
    BUNDLE_SHA256
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V

-- @@ state_rows
SELECT
    STATE,
    FIPS,
    RUCC_2023,
    HUMAN_STATUS,
    TICK_STATUS,
    BURGDORFERI_STATUS,
    INCIDENCE_FLOOR_2023,
    RELEASE_ID
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V
ORDER BY FIPS
