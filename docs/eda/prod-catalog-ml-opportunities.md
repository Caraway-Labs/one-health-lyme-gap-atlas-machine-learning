# Production catalog: what the published Atlas can support

- Issue: none. This is an unscoped exploratory briefing requested against
  `ONE_HEALTH_LYME_GAP_ATLAS_PROD`.
- Question / intended use: describe the consumer-visible production data and
  identify unsupervised and semi-supervised questions it can support. It does
  not approve a target, a training run, or a public interpretation.
- Data: `ONE_HEALTH_LYME_GAP_ATLAS_PROD` presentation, governance, and lineage
  views. Current release `governed-2026-10-06-nlcd-demo-cohort`, schema
  `1.0.0`, method `semantic-1.0.0`, bundle SHA-256
  `603afb135a1a5c958d1d56d48d580d9942c67eb38986caf8b4b3acf69fcde2c9`,
  generated 2026-10-05, loaded 2026-10-10.
- Cohort: 3,144 unique county FIPS, 51 state codes including the District of
  Columbia. Human measures are calendar year 2023. SVI and uninsured context
  are the 2022 county layer (ACS 2018–2022). RUCC is 2023. Tick and pathogen
  status are cumulative through 2025-12-31. NLCD land cover is calendar year
  2025 for two selected geographies only.

## Method and assumptions

Exploratory catalog, specified after inspection. Read-only aggregates on the
views the `OH_LYME_PROD_READ` role can see. No raw or semantic base tables
were visible to that role, and none were queried. Missing human, tick, and
pathogen states were kept as their own categories. Numeric summaries of case
and incidence floors use the 651 counties with a published floor. Population
totals use the atlas population field. County rows are spatially dependent, so
every count below is descriptive. No model was fit. No holdout labels were
used for tuning.

Context at read time: user `MATTHEWCARAWAY`, role `OH_LYME_PROD_READ`,
database `ONE_HEALTH_LYME_GAP_ATLAS_PROD`, schema `PRESENTATION`, warehouse
`COMPUTE_WH`, secondary roles empty. The session warehouse was selected
explicitly. The warehouse named on the local read connection was not usable
by this role.

## Material findings and limits

The read role sees 12 business views, all views and no base tables:
`PRESENTATION.CURRENT_COUNTY_ATLAS_V` (3,144 counties, 21 columns),
`PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V` (9,446 rows),
`PRESENTATION.CURRENT_RELEASE_V` (1 row),
`PRESENTATION.CURRENT_INDICATOR_METADATA_V` (7),
`PRESENTATION.CURRENT_MEASURE_METADATA_V` (21),
`PRESENTATION.CURRENT_SOURCE_METADATA_V` (6),
`PRESENTATION.CURRENT_METHODOLOGY_METADATA_V` (3),
`PRESENTATION.CURRENT_TIER1_COUNTY_REVIEW_V` (3,144),
`PRESENTATION.INTELLIGENCE_FEED_V` (0),
`PRESENTATION.INTELLIGENCE_FEED_V2` (0),
`GOVERNANCE.V_USER_FEEDBACK_ANALYST` (4),
`LINEAGE_AUDIT.SEMANTIC_LINEAGE_AUDIT_V` (88,046).

The wide county atlas is the national product. The long observations view
carries three human measures for every county and seven land-cover measures
for two counties. Tick, pathogen, SVI, uninsured, and RUCC are on the atlas,
not in the observations grain.

Human surveillance: 651 counties `published_count_floor`, 2,493
`no_county_linked_record`. Published case floors run from 5 to 3,262
(median 49, 90th percentile 337). Published incidence floors run from 0.15 to
1,640 per 100,000 (median 81). Those 651 counties hold 158.7 million of the
331.1 million people on the atlas. Among them, 103 counties under 10 per
100,000 hold 71.2 million people, and 290 counties at or above 100 per
100,000 hold 28.8 million. Nineteen states have no published county floor.
State-unallocated human records are constant within each state and sum to
1,944; they are not in the county floors. The minimum published case floor of
5 is consistent with small-count protection.

Tick and pathogen, same 3,144 counties: tick Established 1,404, Reported 490,
No records 1,215, Unknown 35. *I. scapularis* Established 1,307, Reported 475.
*I. pacificus* Established 97, Reported 15. *B. burgdorferi* Present 689,
No records 2,420, Unknown 35. The 35 Unknown counties are Alaska (30) and
Hawaii (5), and they are the counties outside `IN_CONTIGUOUS_TICK_SCOPE`.

Cross-signal counts: 443 counties have a published human floor, established
ticks, and pathogen present. 228 have established ticks and pathogen present
with no human floor (22.7 million people). 810 have established ticks and no
human floor (83.2 million). 207 have a human floor and no pathogen record.
1,189 have no human, tick, or pathogen documentation. The largest
established-tick gaps are Indiana 80, North Carolina 51, Illinois 50,
California 49, Kentucky 48, Florida 43, Iowa 43, Mississippi 40, Georgia 39,
and Ohio 37. Florida has 55 established-tick counties and zero pathogen-present
counties.

Among the 651 published counties, incidence floor correlates 0.42 with RUCC,
−0.41 with log population, −0.22 with SVI percentile, and −0.10 with uninsured
percentile. Case floor correlates 0.38 with log population. SVI and uninsured
percentile correlate 0.48. Published-floor share falls from 38% in the largest
metro code to 6.5% in the most rural code. These are descriptive associations
inside a selected, censored subset.

`CURRENT_TIER1_COUNTY_REVIEW_V` is populated for all 3,144 counties but pinned
to release `governed-2026-09-18-unknown-coverage`, model
`tier1-statistical-reference-v1`, features `tier1-county-features-v2`,
generated 2026-10-07. Tiers are HIGH 315, MEDIUM 628, LOW 2,201. Sufficient
evidence is exactly the 651 current published-floor counties. That alignment
was checked; predictor-by-predictor equality with the October release was not
recomputed in this pass.

Land cover is a labeled demonstration: seven 2025 NLCD shares for FIPS 09110
(Capitol Planning Region, Connecticut) and 51013 (Arlington County, Virginia).
The release limitation states that this layer is descriptive context and is
not automatic ML admission. Intelligence feeds are empty. Analyst-visible
feedback is four rows from 26 Sep through 1 Oct 2026.

Lineage retains both the current release (44,030 rows) and
`governed-2026-09-18-unknown-coverage` (44,016 rows). Context sources match as
`LEGACY_CONFORMED`. Tick and pathogen match as `RESTRICTED_CDC_CONFORMED`
except the 35 Unknown counties. Every human measure row is `UNMATCHED`.
That is a lineage-resolution gap for the human source, observed on both
retained releases. The atlas still publishes the human values with CDC 2023
source metadata.

The release `SCORE_DEFAULTS` object describes a deterministic community and
ecology mix. This pass did not find that mix materialized as a county column.

## Decision

FOLLOW_UP. The published county table can support a descriptive typology and a
carefully validated positive-unlabeled or censored-floor analysis of
surveillance follow-up. It cannot support a national land-cover model, a text
model, a time-series model, or a claim about individual risk or true incidence.

Smallest next step: freeze an analysis spec for one question — rank unlabeled
counties by resemblance to published-floor counties — with leave-one-state-out
evaluation, an explicit missingness rule, and a prohibition on using the
September tier score as a label. Ask the data owner whether human
`UNMATCHED` lineage is expected before that rank is treated as operational.

## Reproduction and retained evidence

- Code revision at read time: `024bbbf74a7da8e54566bd60e8e762d85a51e24f`.
- Data identity: release and bundle above. Objects read: the 12 views listed
  in the findings, plus `INFORMATION_SCHEMA.TABLES` and
  `INFORMATION_SCHEMA.COLUMNS` for the catalog.
- Commands: `snow sql` against `PRESENTATION` on `COMPUTE_WH` after the
  context check. Headline county counts:

```sql
SELECT HUMAN_STATUS, TICK_STATUS, BURGDORFERI_STATUS, COUNT(*) AS COUNTIES
FROM PRESENTATION.CURRENT_COUNTY_ATLAS_V
GROUP BY 1, 2, 3
ORDER BY COUNTIES DESC;
```

- Lifecycle / review: exploratory briefing only. The September tier view was
  read as an existing output, not re-scored.
- Transient artifacts intentionally not committed: ignored
  `outputs/eda-prod-catalog/` query files and JSON extracts.
- Snowflake writes: none.
