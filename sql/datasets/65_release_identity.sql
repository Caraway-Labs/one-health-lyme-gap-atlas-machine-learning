-- READ ONLY, ML #65. Validated DEV READ; execute timeout 30 seconds; max 2 rows.
SELECT release_id, schema_version, methodology_version, bundle_sha256, limitations
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_RELEASE_V
LIMIT 2;
