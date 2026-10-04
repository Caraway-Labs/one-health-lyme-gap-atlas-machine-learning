# EDA #65: vector/pathogen documentation states

**Issue status: INPUT_PENDING for PROD; scientific review pending.** See the
pre-result [PROD scope amendment](../methodology/65-prod-scope-amendment.md),
registered at `fb0a6a8`. The DEV result below does not settle #65. The shared
PROD capture is owned by #63; no duplicate export or PROD statistics have been
performed here. The same pairing/category/method rules will be applied after
the retained input and provenance gates pass.

**DEV-only disposition: NOT_ESTIMABLE.** The v1 registered association has zero eligible
counties in the current governed DEV release: both vector-species statuses are
Unknown for every county. This is a demonstrated data limitation, **not an
access blocker, zero association, or biological absence**.

Issue: [ML #65](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/65),
parent #59; specification contract #60. The
[analysis plan](../methodology/65-analysis-plan.md) was committed at
`459d53d` before any live read or result statistics. This exploratory analysis
has one fixed pairing and one fixed sensitivity; no model or protected holdout
was used. Independent scientific/code review remains pending.

## Question, cohort and source identity

Is county pathogen documentation state associated with vector documentation
state in one governed CDC release? Pairing: **Ixodes scapularis or Ixodes
pacificus + Borrelia burgdorferi sensu stricto**. The source defines pathogen
Present as identification in host-seeking ticks of either species; it does not
attribute a record to one species. The approved aggregate taxon and distinct
pathogen target come from the normalization registry v1.0.4. The analysis
combines two explicit vector source statuses only under the frozen union rules.

- Live observation: `2026-10-04T01:01:38.848876+00:00`.
- Environment: DEV; release `governed-2026-09-17-unknown-coverage`, schema
  `1.0.0`, methodology `semantic-1.0.0`.
- Release bundle SHA-256:
  `55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`.
- Publisher/source: CDC ArboNET Tick Module, source ID
  `cdc_arbonet_tick_module`; separate datasets
  `cdc-ixodes-county-status-2025` and `cdc-ixodes-pathogen-status-2025`.
- Both source vintages verified as `through 2025-12-31`. These are cumulative
  documentation states, **not annual incidence or annual status observations**.
- Source observation units: county/species vector status and county/pathogen
  status. The analysis unit is one unique county; the governed projection
  exposes neither source-native row counts nor internal artifact/run IDs.
  Those counts/IDs were not reconstructed or claimed to be independently read.
- Cohort: unique five-digit county FIPS with explicit contiguous-tick scope.
  No population weights, percentile adjustments or category reinterpretation.

The current-county **annual observation** view cannot answer this question;
its allowlist excludes cumulative tick/pathogen statuses. Instead, this analysis
used the existing governed county-atlas projection. No internal semantic table,
restricted workbook, Alpha fixture or synthetic dataset supplied cohort counts.

## Measured counts and missingness

The returned projection has **3,144 rows and 3,144 unique county FIPS**.
No duplicate, invalid FIPS, missing scope or mixed release was found.

| Cohort/exclusion | Unique counties |
| --- | ---: |
| Explicit contiguous-tick scope | 3,109 |
| Outside contiguous-tick scope | 35 |
| Missing scope | 0 |
| Vector unknown, within scope | 3,109 |
| Pathogen unknown, within scope | 0 |
| Both families unknown, within scope | 0 |
| Union of unknown-family exclusions, within scope | 3,109 |
| Eligible primary association N | **0** |

These exclusion counts overlap only as specified; scope exclusion precedes
unknown-family exclusion. Outside-scope pathogen Unknown values are still
reported below and are not counted twice as eligible-cohort exclusions.

| Evidence state in all projected counties | Counties |
| --- | ---: |
| I. scapularis Unknown | 3,144 |
| I. pacificus Unknown | 3,144 |
| B. burgdorferi Present | 689 |
| B. burgdorferi source-reported No records | 2,420 |
| B. burgdorferi Unknown | 35 |

Complete projected cross-tabulation, before scope/unknown exclusion:

| Aggregate vector state | Pathogen Present | Pathogen No records | Pathogen Unknown |
| --- | ---: | ---: | ---: |
| Unknown | 689 | 2,420 | 35 |

All 689 Present and 2,420 No records pathogen counties are in scope; all 35
pathogen Unknown counties are out of scope. The source metadata note mentions
33 absent canonical counties, while the live projection has 35 Unknown values.
Those are different evidence surfaces; this analysis does not infer the reason
for their difference or substitute the note's count for the measured count.
Resolving that provenance detail belongs to the source owner and does not change
the all-unknown-vector result.

Primary eligible table (counts of qualifying pairs, **not absence counts**):

| Vector documentation category | Pathogen Present | Pathogen No records |
| --- | ---: | ---: |
| Established | 0 | 0 |
| Reported | 0 | 0 |
| Source-reported No records | 0 | 0 |

## Method, uncertainty and sensitivity

The prespecified estimand is unweighted Cramer's V on the 3-by-2 documentation
table, with source-reported No records eligible only as a record-availability
category. Unknown/unavailable/NO_QUALIFYING_RECORD are excluded and never made
negative. Both vector statuses must be explicit; missingness in either excludes
the combined category, even if the other species has a documented positive.

The reusable implementation reports expected cells and Pearson residuals when
two nonempty margins remain on both axes. It uses a chi-square IID reference
only if every expected count is at least five; otherwise it performs two-sided
fixed-margin exact probability-ordering enumeration (Fisher for 2-by-2,
Freeman-Halton for 3-by-2), capped at 100,000 tables. A cap failure produces an
unavailable exact probability, never an asymptotic fallback. These methods
address cell sparsity, not surveillance selection or county dependence.

**Executed result:** zero eligible pairs, so expected cells, test statistic,
reference p-value, Cramer's V and residuals are undefined. No hypothesis test
or bootstrap was run; no p-value or interval can quantify this missing contrast.
The implementation returns null for the effect and probability rather than
claiming V = 0. The planned state-cluster robustness interval (2,000 resamples,
seed 6501, minimum ten represented state clusters, at most 5% degenerate draws)
is likewise unavailable because there are zero eligible clusters.

The prespecified sensitivity collapses Established + Reported to Documented
vector record, preserving source-reported No records and keeping unknowns
excluded. Its 2-by-2 table is also entirely zero, N = 0; V, probability and
robustness interval remain undefined. A positive-only restriction would also
make the pathogen margin constant, so it was not selected after inspection.

County ecology and surveillance systems are spatially dependent. Future
estimable tables would remain descriptive finite-release associations; IID
test probabilities would be reference diagnostics only. State resampling does
not eliminate cross-state dependence or establish a probability sample.
Cumulative states give neither timing of annual events nor absence, tested-tick
denominators, prevalence, individual exposure or causal effects.

## Decision and useful implications

The current release cannot establish redundancy or complementary predictive
value between vector and pathogen blocks. In this release the vector block has
no observed information to compare; pathogen documentation states distinguish
689 Present counties from 2,420 No records counties within scope. Do not call
the evidence families independent or redundant, convert the vector Unknowns
to negatives, or train a model from this finding.

Product implication: show separate evidence availability and preserve Unknown
versus source-reported No records; describe the statuses as cumulative
surveillance documentation. No Web code or product contract is changed here.

The minimal prerequisite for a future association is a separately governed,
accessible immutable release with explicit vector categories and enough
variation in both families. ADR 0032 documents the DEV all-unknown coverage
exception, consistent with what was measured. This issue does not authorize a
new derivation, grant, production read, ingestion or release. The result is
scientifically NOT_ESTIMABLE **for this DEV release**; no extrapolation to PROD
or an unrestricted source workbook is supported. The issue comment is prepared
for review and will not be posted, merged or closed before Matthew's review.

## Public PROD route check after cross-repository steering

The requested existing public consumer route was checked at
`https://api.carawaylabs.com/v1/atlas/metadata` with one anonymous GET, limited
to 30 seconds and 262,144 bytes. HTTP 200 returned 4,359 bytes at
`2026-10-04T01:14:05Z`; response byte SHA-256
`648cbaa80b7595bec80283d62916c5f2492f9b26c9d6fc996f519abdc5fe42ff`.
It identifies **a different PROD release**,
`governed-2026-09-18-unknown-coverage`, bundle SHA-256
`038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`,
schema `1.0.0`, method `semantic-1.0.0`, and separate tick/pathogen source
descriptions with cumulative vintage `through 2025-12-31`. The metadata is
accessible; no claim that the PROD input is inaccessible has been made.

The existing [DATA #200 receipt review](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/200#issuecomment-5965980365)
links successful build/publication receipts for that same release/hash. The
[manifest at the exact build head](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/7b80373187b8aa665891e2f39e6bf7f8c6fb35a1/docs/contracts/semantic-release/governed-2026-09-15-manifest.json)
was inspected directly (Git blob `ef7e08c2919d38bdf6bdaa8ef79316b1bafd00f5`).
Its tick tuple is source version `b81c116f-d93d-4c6b-9d11-ac2477e0e242`, run
`ec14cc85-85d6-4064-80f1-1354238b88d6`, artifact
`e0db2aaf-7412-47d1-ac14-ba8807375549`, SHA-256
`e35a5066a7c77b2e79c50f315a18e042405ab7baa8a414a1a907792bb25d2adc`.
Its distinct pathogen tuple is source version
`92b22f19-0d5d-4576-a7c6-6c9af9343edf`, run
`796731a3-cd7f-4510-aa0c-738ab74a6a76`, artifact
`d93ff6a3-4201-4a06-bfa3-da6026a706d9`, SHA-256
`68baef5f20b1e41821d0e6955cbb1809262e0f3624e387e88c04f6ddb0266f2f`.
These are historical manifest identities, not a fresh restricted-source read
or a substitution of PROD lineage for this analysis's DEV snapshot.

The remaining PROD association input would be release-bound **paired county
species/pathogen states**, with the existing provenance receipts preserved.
Metadata alone has no county-state contingency table. API models expose the
species states on county detail; the score summary does not expose those
species fields. No PROD county detail/score rows, production Snowflake role,
restricted source, denied internal table or alternate identity was used here.
Per the subsequent shared-capture coordination instruction, the existing DEV
capture was reported and no second county export was made. PROD scientific
estimability is **unassessed**, not proven NOT_ESTIMABLE. This check does not
expand or rewrite the frozen DEV analysis or infer source absence from the
release's name. The [PROD scope amendment](../methodology/65-prod-scope-amendment.md)
is now registered at `fb0a6a8`, before PROD statistics. The local-only shared
input path is implemented and synthetically tested; the precise fields,
sidecar keys, source/release/receipt/context/digest gates and replay command are
in the [shared-capture handoff](../methodology/65-shared-capture-handoff.md).
Actual shared input and independent scientific review remain pending. No
synthetic counts are substituted for PROD evidence, and no extra scan is made.

Reproduce the metadata-only check, without county or warehouse export:

```powershell
curl.exe --fail --silent --show-error --max-time 30 --max-filesize 262144 --output outputs/65-public/metadata.json https://api.carawaylabs.com/v1/atlas/metadata
Get-FileHash outputs/65-public/metadata.json -Algorithm SHA256
```

## Reproduction and retained evidence

Read-only objects, and no others:

1. `ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_RELEASE_V`
2. `ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_SOURCE_METADATA_V`
3. `ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_ATLAS_V`

The CLI and adapter both validated user `MATTHEWCARAWAY`, role
`OH_LYME_DEV_READ`, database `ONE_HEALTH_LYME_GAP_ATLAS_DEV`, schema
`PRESENTATION`, warehouse `OH_LYME_DEV_INGEST_XS_WH`. The adapter sets a
30-second statement/queue bound and 30-second login/network bounds; SQL returns
at most 2 release rows, 3 source rows and 3,145 county rows. There were five
read-only SELECTs total including the two context checks, and one county fetch.
No warehouse scan was repeated; subsequent verification replays locally.

| Versioned query | Query ID | Returned rows | Executed UTF-8 SQL SHA-256 |
| --- | --- | ---: | --- |
| `sql/datasets/65_release_identity.sql` | `01c77e7d-040b-dea2-0064-2d070110a392` | 1 | `9117859c63c7f7177a5eb0580b2fa7c1e0f68bd94020d11c54543f997ef03d07` |
| `sql/datasets/65_source_identity.sql` | `01c77e7d-040b-d63b-0064-2d07011097be` | 2 | `4cf486a5539a3ecbbaeed499b9719a25398d89718d612dcb9e90894f8b750f1f` |
| `sql/datasets/65_county_evidence.sql` | `01c77e7d-040b-dea2-0064-2d070110a396` | 3,144 | `b6d2278038721fa12266ff88f6ff05eb65442d1306225cf85387c54f130e2f42` |

Private snapshot byte SHA-256:
`4ba8b92f9e2a5967bd68c5e5a7a545a70a688aba794dbcfbe770d092f5b3c062`.
The exact bytes and transient summaries stay in ignored `outputs/`; they are
not committed or uploaded. Reproduction from that snapshot verifies its digest.
New acquisition is blocked if the source identity/period changes; current-view
pointers are mutable, so a future different release is a new analysis, not an
exact replay of this result. The release bundle digest binds governed source
lineage; internal per-source artifact IDs/digests are intentionally unavailable
through the views. This is not an independent raw-artifact integrity audit.

```powershell
uv sync --extra dev --extra snowflake
# First acquisition only, after the documented CLI context check:
# Set SNOWFLAKE_CONNECTION_NAME locally to an existing authorized DEV read
# connection; never log/commit its value or credentials.
uv run python scripts/eda_65.py --acquire --output outputs/65
# Exact local replay, no Snowflake connection:
uv run python scripts/eda_65.py --snapshot outputs/65/snapshot.json --expected-sha256 4ba8b92f9e2a5967bd68c5e5a7a545a70a688aba794dbcfbe770d092f5b3c062 --output outputs/65-replay
uv run python scripts/verify.py
```

Core code: `src/lyme_gap_atlas_ml/evidence_association_65.py`;
I/O boundary: `src/lyme_gap_atlas_ml/snowflake/evidence_65.py`.
Offline tests use explicitly synthetic examples solely for category/exclusion,
exact probability, effect, degenerate/bootstrap and context/denial behavior.
Their numbers are not used in any empirical table above. Runtime: Python
3.13.15, Snowflake connector 4.7.5; dependencies resolved from unchanged
`uv.lock`. Repository gates and final reviewed code identity are recorded in
the PR, whose head contains the reproduction implementation. The registration
commit remains a separate ancestor and has not been amended after inspection.

Pinned Data contract revision: `614dbb7e95766e586e4cac6332d126e53e23933e`.
No shared contract was edited. References:

- [Canonical tick surveillance](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/614dbb7e95766e586e4cac6332d126e53e23933e/docs/contracts/tick-surveillance/canonical-tick-surveillance-v1.md)
- [Normalization vocabulary](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/614dbb7e95766e586e4cac6332d126e53e23933e/docs/contracts/tick-surveillance/tick-surveillance-normalization-v1.json)
- [Pathogen source meaning](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/614dbb7e95766e586e4cac6332d126e53e23933e/docs/operations/cdc-ixodes-pathogen-source-review.md)
- [Governed semantic release](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/614dbb7e95766e586e4cac6332d126e53e23933e/docs/contracts/semantic-release/README.md)
- [DEV unknown-coverage decision](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/614dbb7e95766e586e4cac6332d126e53e23933e/docs/adr/0032-dev-evidence-only-tick-semantic-coverage.md)
