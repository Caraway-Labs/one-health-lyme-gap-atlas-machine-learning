-- ML #40: read-only DEV connectivity proof, not a training dataset/target.
-- Source: Data #513 / V127, current-county-observations-v1 contract.
-- Reads only the published current release's approved 2023 county projection.
-- Fixed one-county sample, at most 10 rows; no private lineage or raw records.
SELECT observation_id, measure_id, county_fips, period_start, period_end,
       temporal_grain, value, value_state, unit, denominator,
       semantic_contract_version, release_version, source_key, source_label,
       source_vintage, source_url, retrieved_at, transformation_version,
       methodology, release_methodology_version, observation_limitations,
       measure_limitation, release_limitations
FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V
WHERE county_fips = '01001'
ORDER BY measure_id, county_fips, period_start, observation_id
LIMIT 10;
