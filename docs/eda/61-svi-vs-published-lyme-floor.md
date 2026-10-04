# EDA #61: SVI and published county-linked Lyme floor

## Current result: geography-amended v3

**Disposition: WEAK_SIGNAL; independent scientific/code review pending.**
Among 577 eligible non-Connecticut counties, overall SVI national percentile
has unweighted Spearman rho **-0.223125** with the published 2022 Confirmed +
Probable county-linked Lyme lower-bound floor per 100,000. The sole registered
outer 1% population-tail sensitivity retains 565 counties, rho **-0.201810**.
These are retrospective descriptive associations, never incidence or causal effects.

The geography amendment was committed as
`591ff5dd5679287d7600060b8058b234869070d5` before association execution;
registered v1 was committed as `fb2ec3165c0caa6db341b7a38dcc3e47589eb211`.
Offline execution used code `6249ddcdd866590098b186bfd79656d6a3708851` and
the retained digest-pinned inputs below. Full input validation passed before
excluding the exact eight CDC Connecticut counties and nine SVI planning regions.
No new source reads were needed for v3.

| Observation unit / outcome state | Actual count |
| --- | ---: |
| Full CDC native rows / unique native IDs | 2,376 / 2,376 |
| Confirmed / Probable native rows | 375 / 2,001 |
| Numeric source rows / distinct source geographies | 2,203 / 585 |
| Geographic exclusions: CDC rows / legacy Connecticut counties | 32 / 8 |
| Geographic exclusions: consumer planning regions | 9 |
| Non-Connecticut analysis-source rows | 2,344 |
| Matched numeric source rows / primary unique counties | 2,171 / 577 |
| Unallocated Suppressed / Unknown rows | 140 / 33 |
| Unallocated published frequency: Suppressed / Unknown | 1,146 / 718 |
| Full consumer projection rows / compatible canonical counties | 3,144 / 3,135 |
| Canonical counties without county-linked records | 2,558 (unknown, not zero) |
| Observed positive / observed zero floor counties | 577 / 0 |
| Eligible exclusions for invalid population / SVI | 0 / 0 |
| Native SVI source observation counts | unknown |

The denominator is the governed ACS **2018-2022 population estimate**, in people;
overall SVI is the national percentile on [0,1] from the same vintage.
The consumer's null auxiliary DENOMINATOR field does not override the population
measure semantics. Native Confirmed + Probable frequencies are summed within
county-of-residence; unallocated frequencies are never allocated to counties.

| Primary cohort distribution | Minimum | Q1 | Median | Q3 | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Population estimate, people | 2,247 | 32,557 | 69,022 | 212,230 | 9,936,690 |
| Overall SVI national percentile | 0.0041 | 0.1833 | 0.3516 | 0.5399 | 0.9965 |
| Published floor per 100,000 | 0.050319 | 21.594636 | 66.099646 | 154.042282 | 1,255.902254 |

Average ranks handle ties. Population has 575 unique values and four tied
observations; SVI and normalized floor each have 577 unique values. The sole
sensitivity uses inclusive linear-quantile population bounds
[6,116.44, 2,257,144.2], removing 12 counties and retaining the weak negative category.

**Spatial dependence and uncertainty:** 31 observed state/DC FIPS-prefix groups
have between-state shares of rank variance of **22.4083% for SVI** and
**52.5053% for floor**. Material state clustering makes county-independent
precision misleading. The registered whole-state bootstrap (seed 61, 2,000
draws, all defined) gives a descriptive 95% percentile interval
**[-0.387094, -0.082937]**. It does not adjust for dependence across state
borders or establish statistical significance. No naive p-value, Moran
statistic, causal model, or additional sensitivity is claimed.

**Interpretation and decision:** only 577 of 3,135 compatible frame counties
have an observed published numeric county floor. The other 2,558 are unknown;
publication selection and geographic restriction limit generalization.
No incidence, individual-risk, causal, underreporting or exposure-location
claim follows. The fresh snapshot is retrospective, not historical as-of
forecasting evidence. Feature implication is **UNKNOWN** under the registered
criteria; retain SVI as context and hold association-based model/product
decisions for independent review. No training or production change follows.

Reproduce from retained bytes with the research replay command below, replacing
`--output outputs/eda61-validation.json --validate-only` with
`--geography-amendment-v3 --output outputs/eda61-v3-result.json`.
Raw data and generated reports remain local and ignored.

## Geography-informed pre-association amendment v3

Independent scientific review and the requesting owner explicitly approve this
eligible-county restriction before any association statistics are computed.
The original national preregistration did not explicitly exclude Connecticut;
this is an honestly labeled geography-informed amendment, not a claim that
the original national cohort was unchanged.

Pin incompatible CDC historical county FIPS to `09001`, `09003`, `09005`,
`09007`, `09009`, `09011`, `09013`, `09015`, and incompatible SVI/ACS planning
region FIPS to `09110`, `09120`, `09130`, `09140`, `09150`, `09160`, `09170`,
`09180`, `09190`. Review identifies these as Connecticut's county-to-planning-
region boundary change. Exclude these exact units for geographic incompatibility
only, without outcome-based selection, geographic allocation or a crosswalk.
Any other unmatched FIPS remains a strict failure. Any other `09`-prefix unit
is an unexpected geography and must also fail, not be silently excluded.

Validate the entire digest-pinned publisher/consumer captures first. Then remove
the eight historical Connecticut geographies from analysis-source membership
and the nine planning regions from the canonical analysis frame. Retain all
native rows in source accounting: 2,376 = 2,171 matched numeric rows + 32
Connecticut-incompatible rows + 173 unallocated rows; consumer 3,144 = nine
incompatible Connecticut units + 3,135 non-Connecticut frame units. Native SVI
source row counts remain unknown. The 577 exact-matched candidates become
primary N only after unchanged population/percentile validity checks pass.

The estimand is now unweighted monotonic association among eligible non-
Connecticut counties with an observed published 2022 Confirmed + Probable
county-linked floor and compatible SVI context. Source, year, case scope,
ACS 2018–2022 population estimate, floor-per-100,000 naming, Spearman,
interpretation thresholds, one 1% population-tail sensitivity and state-cluster
bootstrap settings remain unchanged. No incidence, causal or historical as-of
claim. Use the already-retained inputs, no new acquisition/SVI/PROD query,
warehouse write, ingestion or training. Commit this amendment before execution.

## Historical v2 mapping stop (superseded by registered v3)

**Execution: STOP — MAPPING_BLOCKED. Proposed disposition: NOT_ESTIMABLE under
the registered strict mapping gate, pending independent scientific review.**
This is now a demonstrated geography/denominator incompatibility, not an
inaccessible-private-metadata claim. No coefficient, interval, sensitivity,
primary eligible N, or spatial association result was computed.

The fresh snapshot of the same governed CDC resource passed resource/schema/
year/case-status/frequency/identity/capture-completeness validation. It contains
32 numeric-FIPS source rows for eight Connecticut identifiers `09001`, `09003`,
`09005`, `09007`, `09009`, `09011`, `09013`, `09015`, four rows per identifier.
None matches the shared SVI consumer frame's nine Connecticut identifiers
`09110`–`09190`. There is no supported exact population denominator/join for
those eight published geographies in the supplied frame. No cross-boundary
allocation, population substitution or reinterpretation was made. The input
admission amendment explicitly stops on mapping failure, so aggregation and
association execution stopped. A separately reviewed restriction to mapped
county candidates may be estimable; this packet does not claim otherwise or
silently turn that restriction into a completed analysis.

### Actual input accounting, not fixture evidence

| Observation unit / state | Actual count |
| --- | ---: |
| CDC 2022 native aggregated rows / unique native `:id` | 2,376 / 2,376 |
| Confirmed / Probable source rows | 375 / 2,001 |
| Numeric five-digit FIPS source rows / distinct source geographies | 2,203 / 585 |
| Matched numeric-FIPS source rows / unique matched county candidates | 2,171 / 577 |
| Unmatched numeric-FIPS source rows / source geographies | 32 / 8 |
| Suppressed-FIPS / Unknown-FIPS rows | 140 / 33 |
| Unallocated published frequency attached to Suppressed / Unknown | 1,146 / 718 |
| SVI consumer projection rows / unique canonical FIPS | 3,144 / 3,144 |
| Native SVI source observation/record counts | unknown, never set to 3,144 |
| Primary analysis county N | unavailable; mapping gate stopped admission |

All CDC frequencies are finite nonnegative integers. Unallocated frequencies
are excluded source diagnostics, never county allocations. The 577 count is
an input-level exact-FIPS match count, not a completed primary-cohort estimate.
The prior consumer audit established zero missing/nonpositive population and
missing/invalid SVI values. No-record canonical counties remain unknown rather
than zero; zero observed published frequencies remain distinct.

### Fresh publisher identity, revision and acquisition limits

Input-admission amendment commit:
`b95766b746d0f5715b6a75157df69a1d30c0bc86` preceded publisher row acquisition.
This is a **retrospective research snapshot of the governed source**, not a
new ingestion or a claimed historical warehouse artifact/run. Governed profile:
[cdc_x5j9_wybp.yml at a62f2e3](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/a62f2e32c748d0b23033c19287e7594feb5857a9/config/sources/cdc_x5j9_wybp.yml),
resource `cdc_lyme_x5j9_wybp`, definition 2, CDC `x5j9-wybp`.
DATA110/113 distinguish permitted retrospective published-floor evidence from
strict historical as-of forecasting. No first-publication claim follows.

The successful row query at `https://data.cdc.gov/resource/x5j9-wybp.json`:

```text
$where=year='2022'
$select=:id,:created_at,:updated_at,year,state,fips,case_status,sex,age_cat_yrs,frequency
$order=:id ASC
$limit=250001
```

Native Socrata IDs are opaque tokens: `:id ASC` is the native server-side order,
not a lexical ordering of their displayed string encodings. Native identities
are retained unchanged and proved unique. The separate count query
`$where=year='2022'&$select=count(*) AS row_count` returned 2,376, equal to the
single successful row response length. Metadata before/after resource ID,
name, description, column types and revision timestamps agree; raw metadata
digests are identical. Schema retains seven publisher columns, Confirmed and
Probable categories, county-of-residence geography and surveillance-year era.

| Local retained bytes | SHA-256 |
| --- | --- |
| `outputs/eda61-publisher/rows-2022.json` | `1207f5a211b0ed5e4d39042c7611f2f68d049df2ff1906b263d295996b4c30ec` |
| `metadata-before.json` and `metadata-after.json` | `4187398ebe91f07ac055e6586263fa50e6396f0892b43c80bce5f4b19f60cc6f` |
| `count-2022.json` | `97eff7104e1e3948dd6b774f99d539160d14d495b990c7022e0634b2d5998d78` |
| Parent shared DEV consumer capture | `be74f3affff2e7753f14e7b804d672fb83d21eabe8f1dc4abead873ea21e8e45` |

Acquisition ran 2026-10-04 UTC, first successful metadata response
02:43:35.870416, successful rows 02:45:33.096573 and final metadata
02:45:34.233354. First-to-last successful response interval: 118.363 seconds.
There were **five requests total**, one successful ordered native-row read,
584,720 successful-response bytes, 30-second request timeouts, and zero
automatic retries. The initial wildcard SELECT was rejected HTTP 400 before
any rows were delivered; an explicit syntax correction reused retained
metadata/count and stayed within the request cap. Its error response body was
not retained; its attempted exact URL/status are recorded honestly in the
local receipt. The four successful response bodies, headers, URLs, timestamps
and digests are retained. The acquisition proof's 2.672-second elapsed field
describes the correction stage, not the full 118.363-second acquisition span.

Publisher `rowsUpdatedAt=1755628515` (2025-08-19T18:35:15Z) and
`viewLastModified=1790121303` (2026-09-22T23:55:03Z) are revision evidence,
not first publication times or proof of historical forecast availability.
The shared consumer capture is pinned to DEV release
`governed-2026-09-17-unknown-coverage`, bundle
`55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`.
No new SVI/PROD query or private source/grant retry occurred in this execution.

### Distinct research replay and interpretation

`src/lyme_gap_atlas_ml/eda61_research.py` validates this admitted retrospective
route without fabricating native SVI IDs or marking inaccessible private
warehouse gates PASS. Consumer projection and native-source counts are distinct.
`scripts/eda61_research.py` checks retained-byte digests and writes a reproducible
mapping-failure report with no statistics. It exits 2 for this real snapshot.
The existing strict warehouse replay (`scripts/eda61.py`) remains separate.

```powershell
uv run python scripts/eda61_research.py --consumer outputs/eda-shared-20261004-dev-consumer.json --consumer-sha256 be74f3affff2e7753f14e7b804d672fb83d21eabe8f1dc4abead873ea21e8e45 --publisher-dir outputs/eda61-publisher --publisher-sha256 1207f5a211b0ed5e4d39042c7611f2f68d049df2ff1906b263d295996b4c30ec --metadata-sha256 4187398ebe91f07ac055e6586263fa50e6396f0892b43c80bce5f4b19f60cc6f --count-sha256 97eff7104e1e3948dd6b774f99d539160d14d495b990c7022e0634b2d5998d78 --output outputs/eda61-validation.json --validate-only
uv run python scripts/verify.py
```

The consumer filename in this portable command refers to a byte-identical local
copy/reference of the parent's shared capture; the source remains in its own
worktree and was not changed. `scripts/eda61_acquire.py` is a bounded fresh
acquisition entry point; offline replay of the retained digests is preferred.
An existing capture directory prevents silent re-acquisition.

Feature implication: **UNKNOWN**. Product implication: retain SVI as context;
this packet supports no association-based feature decision. The next review
must resolve the eight-to-nine Connecticut geography incompatibility or approve
a specifically labeled matched-county cohort before any coefficient is computed.
Neither step authorizes incidence, causal, individual-risk, underreporting or
exposure-location claims. Spatial dependence/sensitivity remain unexecuted.
Raw responses, normalized row data, receipts and generated reports remain local
and ignored; no Library upload, warehouse ingestion/write or training occurred.

Final revised local gates passed after merging latest main
`7174168194f48d3f8a88f0289e0a9f27cecb15e9` into this isolated branch:
`uv sync --extra dev`; `uv run python scripts/verify.py` — contract/skill/hygiene,
Ruff, formatting, strict mypy and pytest passed, **265 tests passed, 1 optional
Arize SDK skip**. This includes 56 synthetic #61 cases, with 17 distinct research
adapter cases. The real offline input replay reproduced `MAPPING_BLOCKED`,
exit 2, without association statistics. Original preregistration and amendment
commits were preserved by merging rather than rewriting their history.

## Registered specification v1 (before result inspection)

- Issue: https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/61; follows #59 and `docs/methodology/analysis-spec-v1.md` (#60).
- Question/decision: Within the governed 2022 county cohort, is overall SVI percentile associated with the published county-linked Lyme surveillance floor per 100,000? This informs whether SVI merits later feature investigation.
- Estimand: unweighted county-level Spearman rank correlation between `RPL_THEMES` and `published_county_linked_case_floor_per_100k`, among eligible complete counties. No causal, incidence, individual-risk, underreporting, or exposure-location interpretation.
- Unit/cohort/time: one canonical US county FIPS, surveillance report year 2022, joined to governed SVI vintage 2022. Source Lyme rows are aggregated observation records, not counties or individual cases. SVI population is an ACS 2018–2022 estimate, not measured annual 2022 population. Validate compatibility before division; label it explicitly.
- Sources: reuse exact governed release membership, source version, ingestion run, artifact ID/digest and canonical mapping. The existing data-repository semantic builder uses confirmed plus probable for 2023; proposed scope here is confirmed plus probable in 2022, contingent on validation against the governed source definitions. Do not use its derived 2023 output.
- Outcome: sum only numeric five-digit canonical county-FIPS published frequencies for the validated confirmed/probable scope in 2022. Never allocate suppressed/unknown/noncounty geography. No county-linked record is unknown, never zero. An explicitly observed numeric zero remains zero.
- Eligibility/exclusions: exclude absent outcome, missing/invalid SVI percentile (including negative sentinel), missing/nonpositive/nonfinite population, unmatched canonical FIPS; fail on duplicate SVI FIPS or duplicate immutable source-record identity. Preserve and separately count source observation rows, unique counties, noncounty rows, missingness and excluded county reasons. Reject negative/nonfinite/nonnumeric eligible frequencies rather than silently omitting them. Reject unresolved scope, source authority, denominator semantics or mapping.
- Status: exploratory; no result statistics inspected at registration. One association question, no hypothesis family or multiple-method search.
- Method: Spearman with average ranks for ties, because the estimand is monotonic association and the surveillance floor may be skewed. Report N, coefficient, quantiles, zero/tie counts and coverage; no naive county-independent p-value.
- One sensitivity, frozen: exclude counties in the outer 1% population tails (below the empirical 1st or above 99th percentile, linear interpolation) of the primary complete cohort; repeat Spearman. No outcome-based exclusions or alternate sensitivities.
- Dependence: assess state-level clustering with state summaries and between/within-state rank variance. County independence is not assumed. If feasible, resample entire states with replacement (2,000 draws, deterministic seed 61) for a descriptive cluster-bootstrap interval; explain that state boundaries do not remove cross-border spatial dependence. Without defensible grouping/coverage, report coefficient descriptively and interval unavailable. Do not claim spatial adjustment or significance.
- Interpretation criteria, frozen: absolute rho below 0.1 = NO_SIGNAL; 0.1 to below 0.3 = WEAK_SIGNAL; at least 0.3 = SIGNAL only if sensitivity retains sign and absolute rho at least 0.3; otherwise WEAK_SIGNAL with instability. These are issue-local descriptive decision thresholds, not scientific universal cutoffs. NOT_ESTIMABLE requires a demonstrated scientific identification failure. Inaccessible inputs produce an access-blocked execution status, with N/statistics unavailable, not NOT_ESTIMABLE.
- Feature implication: association alone cannot authorize training or inclusion; TEST_IN_MODEL may be proposed for stable signal, UNKNOWN otherwise. Population/reporting artifacts and spatial structure remain caveats.
- Stop: no alternative denominator, source-year substitution, synthetic cohort counts, production writes, ingestion, model calls/training, or changes to shared contracts.

## Input admission and earlier execution history

The v2 amendment below admits the retrospective research route. The following
v1 access/warehouse-review notes are historical and are superseded as universal
research blockers; the current mapping-stop result above controls interpretation.

### Input-admission amendment v2 (before association result inspection)

The requesting reviewer explicitly authorized this bounded retrospective route
after independent scientific review. DATA110 permits retrospective published
floor EDA using Confirmed + Probable numeric-FIPS frequencies; DATA113 separates
that estimand from strict historical as-of/predictive eligibility. The governed
profile `config/sources/cdc_x5j9_wybp.yml` at data commit
`a62f2e32c748d0b23033c19287e7594feb5857a9` identifies the same public CDC
`x5j9-wybp` resource, definition v2, COUNTY_OF_RESIDENCE geography,
surveillance_year time, and deterministic `:id ASC` order.

The question, 2022 year, Confirmed + Probable case scope, SVI ACS 2018–2022
population denominator, Spearman, single population-tail sensitivity and
interpretation thresholds remain unchanged. This amendment changes input
admission only: use a fresh digest-pinned snapshot of that same governed public
resource, explicitly distinct from historical warehouse artifacts. No invented
ingestion run/source-record hash, private reviewed-envelope claim or historical
first-publication claim. The descriptive research adapter must not bypass or
mislabel the separate warehouse-replay adapter's gates.

Reuse the parent's shared outcome-blind DEV consumer capture, SHA-256
`be74f3affff2e7753f14e7b804d672fb83d21eabe8f1dc4abead873ea21e8e45`,
for independently projected canonical FIPS, population and national SVI
percentile, with exact release metadata. Consumer rows are projection units;
native SVI source row counts/record identity are unknown and must remain so.
There is no additional SVI/PROD query, source ingestion, warehouse write,
training or Library upload.

Only the missing 2022 numerator is acquired. Freeze request caps at five HTTP
requests maximum (metadata before, 2022 row count, one native-row read,
metadata after, optionally one metadata inspection only); zero automatic
retries, 30-second request timeout, 180-second total runtime, 250,000 admitted
rows (250,001 sentinel cap), 64 MiB per response and 128 MiB cumulative.
The one row query is `year='2022'`, ordered `:id ASC`, preserving native ID,
row modification fields, case category and frequency. Keep actual response
bytes, URLs/queries, headers, timestamps, metadata/revision evidence and digests
locally in ignored outputs. Validate expected resource/name/schema/year/FIPS/
case-category semantics, before/after revision equality, expected row count,
unique native IDs, valid frequencies, complete mapping and source-unallocated
exclusions **before aggregation or any association statistics**. Abort on cap,
revision/schema/category/mapping/denominator/completeness failures.

Acquisition/normalization checks and counts are input diagnostics, not cohort
association results. Unknown historical first publication and private lineage
remain limitations, not universal blockers to this explicitly retrospective
estimand. Amendment commit must precede publisher row acquisition and analysis.

**Earlier v1 execution status: ACCESS_BLOCKED for required 2022 outcome/authority inputs.
Scientific disposition: pending. Feature implication: UNKNOWN.**
Existing consumer access to SVI/population is verified below. No real association
statistics, eligible analysis cohort N, sensitivity result, or spatial diagnostics
were computed. Consumer audit counts are distinct from analysis-cohort counts.
This is neither evidence of no signal nor a demonstrated NOT_ESTIMABLE finding.
Issue #61 remains incomplete pending required input validation and review.

The pre-result registration commit is
`fb2ec3165c0caa6db341b7a38dcc3e47589eb211`, based on main
`c063b8aa4cf26b55cfc1b32cf0a660f955948195`. The full current issue bodies
and comments for #59, #60 and #61 were read; #59 and #61 had no comments.
No open PR matching #61 existed at initial inspection. Another issue's worktree
was left untouched. The registered specification above remains unchanged.

### Validated and unresolved semantics

Read-only inspection of the data repository at
`eb984723080c9ff3a3484a6d30f9adb0197bd847` found:

- `docs/contracts/semantic-domain/story-192-source-mapping-matrix-2026-09-24.md`
  maps SVI `E_TOTPOP` to persons for ACS 2018–2022 and `RPL_THEMES` to a
  national county percentile. Percentile is not percent. The denominator is a
  period estimate, so even a valid calculation is not an annual incidence estimate.
- `docs/contracts/county-identity-geometry/county-identity-geometry-v1.md`
  defines canonical `STCNTY` FIPS. Its documented coverage is source-contract
  evidence, **not the real #61 analysis N**. It prohibits duplicate/unmatched
  FIPS and preserves unknown states.
- `src/lyme_gap_atlas_data/semantic_release.py`, `_human_values`, uses confirmed
  plus probable **for 2023**. That implementation is evidence of existing scope
  only; it does not independently approve case-definition compatibility for
  2022. The required 2022 scope remains unresolved until its governed definition
  and actual pinned rows can be inspected. No source-year substitution occurred.
- The existing 2023 release's floor calculation and its historical physical
  naming are not reused. This issue's derived quantity uses the explicit
  published-floor name.

Candidate source identity from the versioned data manifest
`docs/contracts/semantic-release/governed-2026-09-15-manifest.json` (the filename
does not equal its internal release ID):

| Field | Human Lyme | SVI |
| --- | --- | --- |
| Manifest release | `governed-2026-09-18-unknown-coverage` | same |
| Resource / definition | `cdc_lyme_x5j9_wybp` / 2 | `cdc_atsdr_svi_2022_county` / 1 |
| Source version | `6e0cb93f-ea95-4b3a-a358-b343321223b8` | `b8b6bf61-c6a3-4538-b0df-1b88c61720b1` |
| Ingestion run | `819259d8-a362-44ac-903a-16754f28b87c` | `331f367d-9282-4936-9b49-a480db995016` |
| Artifact ID | `df4e8edc-8033-4c17-b237-f72ef6c27a9d` | `cdc_atsdr_svi_2022_county:dc042342a2e5abc108af67b439ec04c8` |
| Artifact SHA-256 | `c00584e1a940f31369ad130f6e67c8bdc2526794f86a81289e106dba67e0b68e` | `dc042342a2e5abc108af67b439ec04c86da8b61f9bdd1cf1b1e5ee0462dea7b2` |

These are **candidate lineage references, not current live DEV approval proof**.
The human manifest's semantic vintage is 2023; its underlying source may contain
2022 but that presence and exact approved scope were not verified. The county
identity contract cites a different original DEV SVI run/version with the same
artifact digest; do not mix its tuple with the later manifest tuple. Each source
must pass the existing governance gate (active approved/conditional decision,
completed run, retained matching artifact, publication, retrieval, blocking DQ)
before reuse. No approved immutable analysis snapshot was located/consumed.

### Initial private-route context evidence (2026-10-04 UTC)

In the initial attempt only connection/session context was queried. No private
governed data table was read. Later consumer-view evidence is recorded separately.
The initial read-only query was:

```sql
SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE();
```

It returned `MATTHEWCARAWAY`, `OH_LYME_DEV_READ`,
`ONE_HEALTH_LYME_GAP_ATLAS_DEV`, **NULL schema**, and
`OH_LYME_DEV_INGEST_XS_WH`. A CLI schema option did not resolve the null.
An explicit session-only schema selection was then attempted:

```sql
USE SCHEMA ONE_HEALTH_LYME_GAP_ATLAS_DEV.CONFORMED;
SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE();
```

It failed with Snowflake `002043 (02000)`, query ID
`01c77e74-040b-d63b-0064-2d0701109736`: “Object does not exist, or operation
cannot be performed.” This does not distinguish a missing schema from missing
privilege. The mandatory five-field context check did not pass, so subsequent
private source reads stopped. No stronger role, production route, interactive login,
grant, credential change, ingestion, or warehouse export was attempted.

### Result accounting

| Required evidence | Actual result |
| --- | --- |
| Lyme source observation rows / distinct source geography | unavailable; access blocked |
| Current consumer county rows / unique FIPS | 3,144 / 3,144 (audit only; see follow-up) |
| Eligible 2022 analysis N | unavailable; required numerator/authority unvalidated |
| Consumer missing SVI / nonpositive or missing population / invalid SVI | 0 / 0 / 0 |
| 2022 absent floor / cross-source unmatched FIPS / cohort exclusions | unavailable; no joined 2022 cohort inspected |
| Zero versus positive observed floor / unknown outcomes | unavailable; preserved separately by code |
| Spearman / uncertainty / distribution | not computed |
| Registered sensitivity | not executed |
| Material spatial dependence | not assessed on real data; county-independent inference prohibited |

Product decision: do not change SVI feature selection or claim any relationship
from this packet. The smallest unblock is an existing-authority evidence packet
or reviewed immutable snapshot of the required 2022 Lyme numerator and approved
case scope, with SVI population/canonical joins and exact source/record/release
identity demonstrated. SVI/population consumer access itself is no longer a gap.
This asks for evidence/access resolution, not a stronger role, alternate year,
denominator or new scientific definition.

### Verified existing consumer route (follow-up, 2026-10-04 UTC)

The parent identified DATA199's existing consumer route. The full current
DATA199/200 comments, merged DATA586 audit at
`e1d6be2e08bbfd670036f1953cad3eb11569970b`, V072 view definitions and semantic
consumer/release contracts were read. These distinguish visible current values
from private source/record/hash and REVIEWED metadata authority.

`USE SCHEMA ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION` followed by the five-field
context query **passed**: `MATTHEWCARAWAY`, `OH_LYME_DEV_READ`,
`ONE_HEALTH_LYME_GAP_ATLAS_DEV`, `PRESENTATION`, `OH_LYME_DEV_INGEST_XS_WH`.
Then `sql/validation/eda61-consumer-preflight.sql` executed once, with a 30-second
statement timeout and SELECT limits of 2/2/2/10/50 rows. It read only existing
`CURRENT_RELEASE_V`, `CURRENT_COUNTY_ATLAS_V`, `CURRENT_SOURCE_METADATA_V` and
`CURRENT_MEASURE_METADATA_V`. No denied private route was retried.

Actual visible current DEV release:
`governed-2026-09-17-unknown-coverage`, bundle SHA-256
`55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`,
schema `1.0.0`, method `semantic-1.0.0`.

- Current county view: **3,144 rows / 3,144 distinct FIPS**; malformed FIPS 0,
  missing/nonpositive population 0, missing SVI 0, invalid SVI 0, selected
  population/SVI `-999` rows 0. This does not establish cross-source set equality,
  source-record authority or the number of eligible 2022 outcome counties.
- SVI source metadata reports **2022 (2018–2022 ACS)**. Measure metadata reports
  `population_2022` as people/source-provided estimate and `svi_percentile_2022`
  as national percentile, both ACS 2018–2022. Both exposed denominator fields
  are null; DATA199 shows V123 constructs this null, so it is not evidence of
  absent denominator semantics or a reviewed #191 envelope.
- Human source metadata reports **2023**. The scoped measure query returned
  `case_count_floor_2023` and the legacy-named `incidence_floor_2023`, period
  2023; no `case_count_floor_2022` was returned. V072's atlas view exposes only
  2023 human fields. This proves that this current consumer projection does
  not supply #61's required 2022 numerator, **not** that governed 2022 source
  records are nonexistent or scientifically unusable. No 2023 outcome was used.
- As requested in the follow-up, a current status visibility audit returned
  scapularis/pacificus `Unknown` in all 3,144 DEV counties; burgdorferi `Present`
  689, `No records` 2,420, `Unknown` 35. These are real current county-view audit
  counts, not fixtures or #61 association findings. Unknown and No records do
  not establish a negative biological state. No PROD or restricted-source read
  was performed and no historical tick-state assumption was substituted.

DATA200 [comment 5965980365](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/200#issuecomment-5965980365)
and the merged DATA199 audit contribute historical source-tuple-to-PROD-bundle
binding: build receipt `35328355391` at
`7b80373187b8aa665891e2f39e6bf7f8c6fb35a1`, publication receipt `35362701191`,
release `governed-2026-09-18-unknown-coverage`, bundle
`038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`.
This is useful contributed historical evidence and is not characterized as
missing. It does not bind the current DEV release, provide a 2022 numerator,
or establish current per-observation record/hash authority and actual REVIEWED
metadata admission. The underlying receipts were not independently replayed here.

**Remaining gap:** approved immutable 2022 confirmed/probable published
numeric-county-FIPS frequencies, their exact scope/source/record/hash lineage,
and defensible joins to the SVI estimate/release. An existing-authority packet
must prove these without widening permissions. A blocked private source path
does not invalidate the successful consumer access reported above.

**Warehouse coordination:** no atlas row export or source export occurred.
The parent assigned one outcome-blind, release-pinned consumer capture to #63;
this issue will reuse that handoff if applicable and will not perform a second
capture. That input alone cannot substitute the 2023 floor for the 2022 numerator.

## Earlier strict warehouse-replay contract and review history

Pure analysis: `src/lyme_gap_atlas_ml/eda61.py`; offline snapshot entry point:
`scripts/eda61.py`; synthetic safeguard tests: `tests/test_eda61.py`.
Existing analysis-spec and mandatory `scripts/verify.py` harnesses are reused;
there was no existing executable association harness to extend.

Prepared, **unexecuted** SQL is in `sql/validation/eda61-source-preflight.sql`
and `sql/datasets/eda61-pinned-inputs.sql`. Use existing governed source gates
and adapters rather than treating SQL presence as authority. Both require
the documented least-privilege context first, a 30-second statement timeout,
bound source identities, and stated row limits. Prefer an existing pinned
snapshot; any export must be sequential and capped, never repeatedly scanned.
Do not use a truncated extract. Snapshot caps are 250,000 Lyme source rows
and 3,144 SVI rows, with one extra sentinel row in SQL to detect overflow.

After those prerequisites pass, the snapshot JSON has three arrays:
`canonical_fips` (independently approved canonical county identifiers),
`svi` (source_record_id, county_fips, population, svi_percentile), and `human`
(source_record_id, county_fips, report_year, case_status, frequency).
SVI contains actual source rows only, never county-frame placeholders; absent
SVI source rows are exclusions with `missing_svi_source_row`, not unmapped Lyme
counties. A numeric Lyme or SVI FIPS outside the independent canonical frame
fails mapping validation. Actual SVI rows with missing/sentinel fields remain
source observations and receive field-level exclusions. Source row IDs must be
nonempty/unique and the reviewed canonical-mapping gate must bind this frame's
exact identity/digest to the source releases. The snapshot digest covers all
three arrays; no county frame is inferred from SVI presence.
The separate reviewed approval JSON requires `snapshot_sha256`, exactly the
two governed `sources` with resource_key/release_id/data_source_version_id/
ingestion_run_id/artifact_id/artifact_sha256/source_query_sha256, and `gates`.
Each gate has `status: PASS` and a durable `evidence_ref`: `source_authority`,
`case_scope_2022`, `population_acs_2018_2022_compatibility`,
`canonical_mapping`, `source_record_identity`, `source_release_membership`.
These are evidence checks, not permission invented by the script. Supply only
reviewed factual records; the entry point cannot independently prove authority.

```powershell
uv sync --extra dev
uv run python scripts/verify.py
uv run python scripts/eda61.py --snapshot data/local/eda61-snapshot.json --approval data/local/eda61-approval.json --output outputs/eda61-summary.json
Get-FileHash sql/validation/eda61-source-preflight.sql -Algorithm SHA256
Get-FileHash sql/datasets/eda61-pinned-inputs.sql -Algorithm SHA256
```

Before any real result, implementation details freeze the cluster-bootstrap
coverage threshold at at least 20 state groups and at least 1,900 valid draws
out of 2,000 for an interval. This is a pragmatic descriptive guard, not proof
of independent states. State median summaries and between-state rank variance
shares flag clustering, but do not establish absence of spatial dependence.
No naive p-values are implemented. Python's deterministic seed is 61;
dependencies are pinned in the existing `uv.lock` (unchanged).

No raw extracts, generated snapshots, caches, row outputs or plots are committed.
Synthetic test counts are only algorithm verification. Independent scientific
and code review is pending; no claim of scientific PASS or issue completion.

Initial local verification: `uv sync --extra dev` and
`uv run python scripts/verify.py` passed (contract/skill/hygiene validation,
Ruff, formatting, strict mypy, **151 passed, 1 optional Arize SDK skip**).
The #61 tests cover ties, undefined correlation, missing-versus-zero outcome,
duplicate identity/mapping, invalid frequencies, sentinel exclusions, the
registered sensitivity, state-cluster determinism and snapshot integrity gates.
Latest main was re-fetched and remained the base SHA above. Local checks do not
prove warehouse access or scientific suitability. No hosted-check result is
claimed here.

Prepared SQL SHA-256 (LF repository content):

- `sql/validation/eda61-source-preflight.sql`:
  `d3139ad0a03c05defc37460ff6e3f9ce63cd714704de5e310b01cef49c861153`.
- `sql/datasets/eda61-pinned-inputs.sql`:
  `048bdf375811172c55c1d5097405936ef1845641db5420c5907e8bef0832211b`.
- `sql/validation/eda61-consumer-preflight.sql` (executed follow-up):
  `f704c8ca447eecfaaa9270e2b0f0ea40e42db9e405f64d710bda88671d4489a3`.

Independent review identified that the original implementation conflated SVI
presence with the canonical county frame. Before any real replay, this was
corrected as described above. Regression tests separately cover absent source
rows, true mapping failure and placeholder rejection, successful snapshot
replay, every prerequisite gate, every row cap and multi-county state resampling.
The question, method, sensitivity and scientific eligibility specification did
not change, and no real result statistics have been examined.

Post-review local verification: `uv run python scripts/verify.py` passed all
contract/skill/hygiene, Ruff, format, strict mypy and pytest gates: **176 passed,
1 optional Arize SDK skip**, including 39 synthetic #61 cases. Latest ML main
remained `c063b8aa4cf26b55cfc1b32cf0a660f955948195`. These tests establish code
safeguards, not scientific input acceptance or a real cohort result.

## Final v3 verification

Latest origin/main was re-fetched and remained
`7174168194f48d3f8a88f0289e0a9f27cecb15e9`, already merged into this branch.
`uv sync --extra dev` and `uv run python scripts/verify.py` passed contract,
skill and hygiene validation, Ruff, format, strict mypy and pytest:
**268 passed, 1 optional Arize SDK skip**. A sandbox pytest-cache permission
warning did not affect verification. The 59 synthetic #61 tests verify methods
and guards; actual cohort counts and results above come from retained real inputs.

## Single held issue-comment draft

**Not posted.** Hold for independent scientific/code review.

### EDA #61 result

**Disposition:** WEAK_SIGNAL (proposed; review pending).

**Headline:** Overall SVI has a weak negative association with the published
2022 Confirmed + Probable county-linked Lyme lower-bound floor per 100,000
among eligible non-Connecticut counties, never incidence.

**Evidence:**

- N counties: 577; unweighted Spearman rho -0.223125.
- Uncertainty: descriptive whole-state bootstrap 95% percentile interval
  [-0.387094, -0.082937], seed 61, 2,000/2,000 valid draws; no naive p-value.
- Spatial dependence: 31 state/DC groups; between-state rank-variance shares
  22.4083% for SVI and 52.5053% for floor. Cross-border dependence remains unmodeled.
- Missing/excluded: 2,376 native source rows; v3 excludes 32 rows from eight
  legacy Connecticut counties and nine incompatible consumer planning regions;
  173 Suppressed/Unknown rows remain unallocated. Of 3,135 compatible frame
  counties, 2,558 have no county-linked record (unknown, not zero), 577 have
  positive floors and zero have observed zero floors. No invalid eligible
  population/SVI exclusions. Native SVI observation counts remain unknown.
- Sensitivity: the sole outer 1% population-tail exclusion retains 565 counties,
  rho -0.201810, preserving the weak negative category.

**Interpretation:** The governed population denominator is the ACS 2018-2022
estimate in people; overall SVI is a national percentile. The explicitly
registered v3 geography amendment preceded statistics and preserved method,
case scope and sensitivity. Publication selection, missing outcomes and state
clustering limit generalization. This retrospective snapshot supports no
incidence, causal, individual-risk, underreporting or exposure-location claim.

**Feature implication:** UNKNOWN.

**Product implication:** Retain SVI as context; hold association-based feature
and product decisions for independent review. No training or production change.

**Links:** [Draft PR #89](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/89),
[EDA artifact](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/blob/codex/ml-61-svi-floor/docs/eda/61-svi-vs-published-lyme-floor.md),
[governed CDC source profile](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/a62f2e32c748d0b23033c19287e7594feb5857a9/config/sources/cdc_x5j9_wybp.yml).
Exact capture digests, queries and release identity appear above. No issue
comment, merge or closure before reviewer approval.
