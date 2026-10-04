# EDA #61: SVI and published county-linked Lyme floor

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

## Execution evidence

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

**Execution status: ACCESS_BLOCKED for required 2022 outcome/authority inputs.
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

## Reproduction and review

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

## Single held issue-comment draft

**Not posted.** Hold for the requesting reviewer's independent scientific/code
review. This is a decision-ready blocker report, not the final four-disposition
result comment required to complete #61. Replace the pending disposition only
after valid evidence permits SIGNAL / WEAK_SIGNAL / NO_SIGNAL / NOT_ESTIMABLE.
Do not map an access failure to NOT_ESTIMABLE merely to fit the issue template.

### EDA #61 result

**Disposition:** pending — ACCESS_BLOCKED (scientific result unavailable).

**Headline:** SVI/population are visible in the existing authorized consumer
view, but #61's required 2022 Lyme numerator and exact authority are not yet
available in a validated reproducible input.

**Evidence:**

- N counties: eligible 2022 N unavailable; current consumer audit is 3,144 unique
  FIPS, not analysis N.
- Spearman/Pearson: not computed; Spearman preregistered.
- Uncertainty: unavailable; no naive county-independent p-value.
- Missing/excluded: consumer SVI/population checks pass; 2022 outcome missingness,
  joins and exclusions remain unavailable. Source-row/county accounting implemented.
- Sensitivity result: not executed; outer 1% population tails preregistered.

**Interpretation:**

- Access failure does not demonstrate no association or scientific NOT_ESTIMABLE.
- SVI population is an ACS 2018–2022 period estimate; 2022 case scope and exact
  outcome/SVI source-record and release compatibility remain unvalidated.
- No result supports causal, incidence, individual-risk, underreporting or
  exposure-location claims; real spatial dependence has not been assessed.

**Feature implication:** UNKNOWN.

**Product implication:** Hold SVI feature decisions until an existing-authority
packet or reviewed immutable 2022 snapshot resolves the named prerequisites.
Consumer access is verified; do not substitute another denominator/year, or
infer signal from fixtures. Reuse the parent's single capture where applicable.

**Links:** [Draft PR #89](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/89),
[EDA artifact](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/blob/codex/ml-61-svi-floor/docs/eda/61-svi-vs-published-lyme-floor.md),
[candidate source release manifest](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/eb984723080c9ff3a3484a6d30f9adb0197bd847/docs/contracts/semantic-release/governed-2026-09-15-manifest.json).
Exact source versions, runs and digests appear above and remain subject to the
named authority gates. No merge, closure or issue comment before reviewer approval.
