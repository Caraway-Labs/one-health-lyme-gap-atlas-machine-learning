-- READ ONLY, ML #65. Bind release ID after context and release validation.
-- Governed source metadata only; 30-second timeout, max 3 rows detects duplicates.
SELECT release_version, source_key, source_id, dataset_id, vintage, source_url, note
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_SOURCE_METADATA_V
WHERE release_version = %s AND source_key IN ('tick', 'pathogen')
ORDER BY source_key
LIMIT 3;
