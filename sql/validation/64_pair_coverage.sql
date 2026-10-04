-- ML #64: read-only aggregate feasibility coverage; no frequency statistics/tests.
-- Authorized DEV connection/context required; never escalate role implicitly.
-- Execute with session STATEMENT_TIMEOUT_IN_SECONDS=30 and
-- STATEMENT_QUEUED_TIMEOUT_IN_SECONDS=30. One SELECT; LIMIT 7 output rows.
-- Source: governed CONFORMED_CDC_LYME_QTBI_XD4I publication, 2011–2019.
-- Do not treat five-digit FIPS syntax as proof of historical boundary identity.
-- Candidate denominator: window-observed county union x within-window contrasts.
-- Excludes 2016->2017. Does not invent missing county values or exact totals.
WITH windows AS (
    SELECT column1 era, column2 y1, column3 y2 FROM VALUES
    ('cdc_2011',2011,2016),('cdc_2017',2017,2019)
), source_rows AS (
    SELECT county_fips,report_year,data_source_version_id,ingestion_run_id
    FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.CONFORMED.CONFORMED_CDC_LYME_QTBI_XD4I
    WHERE report_year BETWEEN 2011 AND 2019
), county_year AS (
    SELECT DISTINCT county_fips,report_year FROM source_rows
    WHERE REGEXP_LIKE(county_fips,'[0-9]{5}')
), counties AS (
    SELECT DISTINCT w.era,w.y1,w.y2,cy.county_fips
    FROM windows w JOIN county_year cy ON cy.report_year BETWEEN w.y1 AND w.y2
), years AS (
    SELECT column1 earlier_year FROM VALUES (2011),(2012),(2013),(2014),(2015),(2017),(2018)
), pairs AS (
    SELECT c.era,y.earlier_year,c.county_fips,
           a.county_fips IS NOT NULL has_earlier,b.county_fips IS NOT NULL has_later
    FROM counties c JOIN years y ON y.earlier_year BETWEEN c.y1 AND c.y2-1
    LEFT JOIN county_year a ON a.county_fips=c.county_fips AND a.report_year=y.earlier_year
    LEFT JOIN county_year b ON b.county_fips=c.county_fips AND b.report_year=y.earlier_year+1
), identities AS (
    SELECT COUNT(DISTINCT data_source_version_id) source_versions,
           COUNT(DISTINCT ingestion_run_id) source_runs,
           MIN(data_source_version_id)::VARCHAR source_version_id,
           MIN(ingestion_run_id)::VARCHAR ingestion_run_id
    FROM source_rows
)
SELECT p.era,p.earlier_year,p.earlier_year+1 later_year,
       COUNT(DISTINCT p.county_fips) window_counties,COUNT(*) candidate_pairs,
       COUNT_IF(NOT has_earlier AND NOT has_later) neither_year,
       COUNT_IF(has_earlier AND NOT has_later) earlier_only,
       COUNT_IF(NOT has_earlier AND has_later) later_only,
       COUNT_IF(has_earlier AND has_later) both_years,
       i.source_versions,i.source_runs,i.source_version_id,i.ingestion_run_id
FROM pairs p CROSS JOIN identities i
GROUP BY p.era,p.earlier_year,i.source_versions,i.source_runs,i.source_version_id,i.ingestion_run_id
ORDER BY p.earlier_year LIMIT 7;
