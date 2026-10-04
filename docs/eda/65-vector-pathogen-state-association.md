# EDA #65: aggregate Ixodes/pathogen documentation association

**Disposition: STRONG_ASSOCIATION by the registered point-estimate bin, pending
independent scientific/code review.** In the published governed PROD consumer
release, **3,109 eligible counties** give Cramer's **V = 0.560660**. The
prespecified state-cluster 95% robustness interval is **0.464977–0.652404**,
spanning the moderate/strong communication bins. The fixed category-collapse
sensitivity gives **V = 0.425779**, interval **0.339043–0.515744**. Category detail
therefore materially affects the descriptive magnitude. The DEV all-unknown
release is separately NOT_ESTIMABLE and is not substituted for PROD evidence.

Issue: [ML #65](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/65),
parent #59, specification contract #60; [draft PR #91](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/91).
Keep #65 open and the final issue comment/merge held until review. No training,
feature admission, source change, causal or biological conclusion is authorized.

## Question, registration and representation

Does cumulative county pathogen documentation state co-occur with vector
documentation state in one governed CDC release? Pairing: **Ixodes scapularis
or Ixodes pacificus + Borrelia burgdorferi sensu stricto**. The pathogen source
defines Present as identification in host-seeking ticks of either species;
this is an aggregate Ixodes question, not a species-specific association.

Registration sequence is retained without amendments to earlier commits:

1. [v1 plan](../methodology/65-analysis-plan.md), commit `459d53d`, before DEV
   live reads/results. DEV subsequently proved all vector states unknown.
2. [PROD scope amendment v2](../methodology/65-prod-scope-amendment.md), commit
   `fb0a6a8`, before PROD statistics, for an existing shared paired-state input.
3. [Public aggregate input amendment v3](../methodology/65-public-aggregate-amendment.md),
   commit `00ad62d`, before any PROD category profiling, association statistics
   or fixed detail-probe result. The shared bulk capture lacked species fields.
   Existing source/producer contracts supported direct aggregate semantics.

This remains **exploratory**, with the prior DEV result, public metadata and
Matthew's statement that PROD has positive source evidence disclosed before v3.
No PROD result was used to choose a pairing, collapse, effect cutoff or method.
The question, three vector categories, unknown rules, effect/uncertainty,
expected-cell rule and one sensitivity stayed fixed. Environments are not pooled.

The bulk `tick_status` is used directly as the **governed aggregate**; no
`scapularis_status` or `pacificus_status` is manufactured. At the actual build
head `7b80373187b8aa665891e2f39e6bf7f8c6fb35a1`, Data's `_assemble_counties`
stores `_tick_status(scapularis, pacificus)`: Established if either species is
Established, otherwise Reported if either is Reported, otherwise Unknown for
unknown coverage, otherwise No records. V088's restricted source loader validates
both source statuses as Established / Reported / No records; missing source
coverage in `_surveillance_values` sets **both** species to Unknown. Under that
closed producer domain, this rollup equals the original conservative union.

This equivalence depends on the approved source/producer domain and historical
build binding. A changed producer allowing a positive species to mask a partially
unknown other species would violate the registered rule and block this route.
The single detail check verifies one projection, not the whole private lineage.
No per-species missingness/distribution or species-specific association can be
estimated from the shared bulk response.

## Source identity, cohort and measured counts

- Published PROD release: `governed-2026-09-18-unknown-coverage`; bundle SHA-256
  `038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`.
- Schema `1.0.0`; methodology `semantic-1.0.0`; scope `US_COUNTIES`.
- Separate CDC ArboNET Tick Module source resources: `tick` and `pathogen`,
  lineage source `cdc_arbonet_tick_module`, datasets
  `cdc-ixodes-county-status-2025` and `cdc-ixodes-pathogen-status-2025`.
- Both public source vintages are `through 2025-12-31`, verified in retained
  before/after metadata and source resources. These are **cumulative states**,
  not annual incidence, annual status observations or individual exposure.
- Source observation units: county/species tick status and county/pathogen
  status; source-native row counts are not exposed and remain unavailable.
  Analysis unit: one unique county in the consumer projection.
- Shared capture manifest generated at `2026-10-04T01:24:24.383786+00:00`;
  that is capture evidence time, not upstream retrieval/publication time.
- Exactly **3,144 rows / 3,144 unique five-digit FIPS**; canonical county-set
  digest checked. No duplicates, invalid IDs, mixed release or missing scope.
- Eligible cohort: explicit `in_contiguous_tick_scope = true` and known vector
  and pathogen documentation categories. No population weights, percentiles,
  derived scores, human outcomes or protected holdouts are used.

| Cohort/exclusion | Unique counties |
| --- | ---: |
| Total consumer projection | 3,144 |
| Explicit contiguous-tick scope | 3,109 |
| Outside contiguous-tick scope | 35 |
| Missing scope | 0 |
| Vector Unknown in scope | 0 |
| Pathogen Unknown in scope | 0 |
| Both/union unknown exclusions in scope | 0 |
| Eligible primary and sensitivity N | **3,109** |

All 35 excluded counties are out of scope and have both aggregate vector and
pathogen Unknown. Unknown overlap is 35 overall, zero in scope; do not double
count it after scope exclusion. There is no access blocker for these public
consumer values. Source-native counts and private authority are separate gaps,
not values inferred from consumer row counts.

| State in all consumer counties | Counties |
| --- | ---: |
| Aggregate vector Established | 1,404 |
| Aggregate vector Reported | 490 |
| Aggregate vector source-reported No records | 1,215 |
| Aggregate vector Unknown | 35 |
| Pathogen Present | 689 |
| Pathogen source-reported No records | 2,420 |
| Pathogen Unknown | 35 |

Primary eligible contingency table:

| Aggregate vector documentation | Pathogen Present | Pathogen No records | Row total |
| --- | ---: | ---: | ---: |
| Established | 671 | 733 | 1,404 |
| Reported | 17 | 473 | 490 |
| Source-reported No records | 1 | 1,214 | 1,215 |
| Total | 689 | 2,420 | **3,109** |

Source-reported No records is included **only as a documentation category**,
never a negative test or biological absence. Unknown/unavailable/
NO_QUALIFYING_RECORD are excluded and remain explicit. This table is real
retained consumer evidence; no fixture or source-profile counts were substituted.

## Method, uncertainty and sensitivity

Registered estimand: unweighted county-level Cramer's V, finite-release
documentation association. All expected cells are at least **108.591**:

| Expected counts under IID independence | Present | No records |
| --- | ---: | ---: |
| Established | 311.147 | 1,092.853 |
| Reported | 108.591 | 381.409 |
| No records | 269.262 | 945.738 |

Thus the frozen chi-square reference criterion (every expected count >=5) is
satisfied. An **observed** cell of one does not by itself violate that criterion.
Pearson chi-square **977.281254**, df **2**; IID reference probability
**6.1104e-213**. This is a diagnostic reference, not dependence-adjusted or
representative-population significance evidence.

The implementation's sparse branch uses two-sided probability-ordering
fixed-margin enumeration (Fisher 2-by-2; Freeman-Halton 3-by-2), capped at
100,000 tables, with no asymptotic fallback at cap failure. It was not needed
for this observed primary or sensitivity table. Its known-reference and cap
behavior are tested with explicitly synthetic tables.

Cramer's V **0.560660**. The prespecified 95% state-cluster percentile
**robustness interval 0.464977–0.652404** uses **49 state-prefix clusters**,
2,000 resamples, seed **6501**, zero nonestimable replicates. The point falls in
the registered strong bin (V >=0.5); the interval crosses that communication
cutoff, so a uniformly strong regional relationship is not established.
These are heuristic reporting bins, not universal scientific thresholds.

Bounded interpretation aid: Pearson residuals in the Present column are
**+20.401 Established, -8.789 Reported, -16.348 No records**. No separate cell
tests or post-hoc hypothesis family were performed. Observed Present fractions
are 47.79%, 3.47% and 0.082%, respectively, describing publication evidence
availability, not infection probability or exposure risk.

The **one fixed sensitivity** collapses Established + Reported to Documented
vector record, retaining source-reported No records and identical exclusions:

| Simplified vector documentation | Present | No records |
| --- | ---: | ---: |
| Documented (Established + Reported) | 688 | 1,206 |
| Source-reported No records | 1 | 1,214 |

Sensitivity V **0.425779**, state-cluster 95% robustness interval
**0.339043–0.515744**, 49 clusters, zero failed replicates; chi-square
**563.623459**, df **1**, minimum expected **269.262**, IID reference
probability **1.3690e-124**. Its point falls in the registered moderate bin.
The reduced V demonstrates that preserving Established versus Reported carries
material category detail; do not select the larger estimate as if the collapse
had not been run. No positive-only sensitivity was added after inspection.

County ecology and surveillance/reporting practices are spatially dependent.
State-cluster resampling addresses within-state grouping only; cross-state
dependence, unequal surveillance effort, publication selection and cumulative
timing remain. This is neither a survey-design confidence interval nor causal
evidence. The finite-release V itself is deterministic conditional on retained
input; the interval is a robustness diagnostic under state reweighting.

## ML/product interpretation and remaining limits

**ML implication:** documentation families strongly co-occur but are not
interchangeable. 688 of 689 pathogen Present counties (99.85%) have documented
vector evidence, while 1,206 of 1,894 documented-vector counties (63.67%) have
pathogen No records. Pathogen documentation therefore distinguishes a subset
inside documented vector evidence. This suggests potential feature overlap
alongside complementary documentation detail; it does **not** establish
predictive redundancy, conditional feature importance or permission to train.

**Product implication:** preserve both family states and Established/Reported
detail; do not count correlated documentation as independent biological evidence.
Keep Unknown separate from source-reported No records and show cumulative
timing. One pathogen Present county with vector No records is a documentation
discordance, not proof of biological contradiction or a negative tick result.
Any source-owner follow-up on that single case must use existing authority;
this analysis makes no extra lookup or new ingestion request.

Remaining authority/evidence limits are explicit:

- Public source `source_version` and acquisition/update timestamps are null;
  that does not prove retained source dates or versions are absent. Exact
  version/run/artifact tuples come from historical manifest/build receipts.
- No fresh private per-record/hash integrity audit or authoritative REVIEWED
  metadata admission envelope was accessed or established. This is a governed
  **consumer documentation association**, not raw-source scientific validation,
  target/feature admission or source publication approval.
- Individual species distributions/unknown counts cannot be reconstructed from
  the aggregate bulk payload. The source/producer closed-domain proof is a
  material assumption reviewed through the pinned build code and source contract.
- Public responses can be cached. Stable before/after release/hash and pinned
  scores identity are verified; no warehouse transaction consistency is claimed.
- Source metadata's note about 33 absent canonical counties is not substituted
  for the measured 35 Unknown/out-of-scope consumer counties.
- Cumulative states are not annual incidence, tested-tick counts, prevalence,
  absence, diagnoses, individual risk or causal effects.

No source-admission gap has been silently treated as unknown-negative or as
scientific NOT_ESTIMABLE for PROD. The observable aggregate contrast is
estimable under the declared public producer contract; independent review must
assess that representation and its scope before the held result comment.

## Reproduction, identities and bounded access

Code paths: `src/lyme_gap_atlas_ml/evidence_association_65.py` (pure analysis),
`public_capture_65.py` (local retained-file gates), `shared_capture_65.py` (v2
six-field alternative), `scripts/eda_65.py` (runner),
`scripts/probe_65_public_detail.py` (single fixed probe). No statistical logic
connects to Snowflake. Tests use synthetic cases solely for code verification.

All #63 row files remained private/read-only. No duplicate bulk export, warehouse
query, credential/role/grant, raw source read, ingestion, paid call, training,
telemetry or Web/API change was made for PROD. One additional fixed county GET
was authorized by v3, at most 30 seconds / 262,144 bytes; it returned HTTP 200,
5,117 bytes at `2026-10-04T01:41:20.370427+00:00`. Its `01001` release/hash,
scope, closed species domain, registered union, and bulk fields all matched.
No detail fanout was performed. Do not rerun network probes to replay statistics.

| Retained input | SHA-256 |
| --- | --- |
| #63 public capture manifest | `1691467c100965fb6d5beb413179d4769dc51451cfb9424c8cd1df97186d0315` |
| `prod-api-scores.json` | `5dbc0e4a66e1d702b5deafc3a430d62fe317984a6ee2e5c1759b74182f06e9ed` |
| Before/after metadata (each) | `648cbaa80b7595bec80283d62916c5f2492f9b26c9d6fc996f519abdc5fe42ff` |
| Public sources | `a7c1940826ee3fb5271959725db8d493034e5ed2cea67dbc556985c6c9ce7867` |
| Public measures | `37032afc750e0053f944405621c89b3462d19e83ef91c11f6a67e708d0f86776` |
| Canonical sorted FIPS + newline digest | `f2651ec6a9375476e3ff09efb4c2a699cd5690ffd3f0c982aeacad967c21c241` |
| Fixed county detail `01001` | `54b38cbd3de770f3a64b0eea6c24daf7bda5a5fd03cb5b46422605bd138942c6` |

The loader verifies the manifest and all five retained response digests/byte
bounds, before/after identity, source datasets/vintages, canonical FIPS and fixed
detail match before statistics. Score query:
`GET /v1/atlas/scores?dataset_version=governed-2026-09-18-unknown-coverage`;
metadata `GET /v1/atlas/metadata`; sources/measures `GET /v1/sources?page_size=100`
and `/v1/measures?page_size=100`; detail
`GET /v1/counties/01001?dataset_version=governed-2026-09-18-unknown-coverage`.
Shared capture bounds are 30 seconds each, 5 MB scores / 1 MB metadata responses.
All are existing anonymous documented consumer routes, not alternate warehouse
identities. Durable code and aggregates are committed; retained row files and
temporary result summaries are ignored and never uploaded.

For local replay, arrange the already-retained files under an ignored directory
(paths below are examples, not a request to re-export):

```powershell
uv sync --extra dev --extra snowflake
uv run python scripts/eda_65.py --public-capture-directory data/local/shared --public-manifest data/local/shared/eda-shared-20261004-prod-public-manifest.json --expected-manifest-sha256 1691467c100965fb6d5beb413179d4769dc51451cfb9424c8cd1df97186d0315 --expected-sha256 5dbc0e4a66e1d702b5deafc3a430d62fe317984a6ee2e5c1759b74182f06e9ed --detail outputs/65-public-detail/detail-01001.json --expected-detail-sha256 54b38cbd3de770f3a64b0eea6c24daf7bda5a5fd03cb5b46422605bd138942c6 --output outputs/65-prod-public
uv run python scripts/verify.py
```

Runtime: Python 3.13.15; unchanged `uv.lock`. PROD replay uses the standard
library only and performs no network/Snowflake operation. Final PR head contains
the runnable implementation; preregistration commits remain its ancestors.
Mandatory local/hosted check evidence is reported separately in the PR.

## Historical source/producer evidence references

Data contract revision `614dbb7e95766e586e4cac6332d126e53e23933e`:
[canonical tick surveillance](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/614dbb7e95766e586e4cac6332d126e53e23933e/docs/contracts/tick-surveillance/canonical-tick-surveillance-v1.md),
[normalization registry v1.0.4](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/614dbb7e95766e586e4cac6332d126e53e23933e/docs/contracts/tick-surveillance/tick-surveillance-normalization-v1.json),
[pathogen source meaning](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/614dbb7e95766e586e4cac6332d126e53e23933e/docs/operations/cdc-ixodes-pathogen-source-review.md).

Actual build head `7b80373187b8aa665891e2f39e6bf7f8c6fb35a1`:
[manifest](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/7b80373187b8aa665891e2f39e6bf7f8c6fb35a1/docs/contracts/semantic-release/governed-2026-09-15-manifest.json)
(Git blob `ef7e08c2919d38bdf6bdaa8ef79316b1bafd00f5`),
[release builder/rollup](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/7b80373187b8aa665891e2f39e6bf7f8c6fb35a1/src/lyme_gap_atlas_data/semantic_release.py),
[V088 source-domain guard](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/7b80373187b8aa665891e2f39e6bf7f8c6fb35a1/migrations/V088__prod_restricted_cdc_tick_derivation.sql).
[Build receipt](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/actions/runs/35328355391),
[publication receipt](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/actions/runs/35362701191),
and [DATA #200 receipt review](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/200#issuecomment-5965980365)
bind the published release/hash historically; they do not establish fresh private
record-level integrity or comprehensive metadata admission.

| Manifest source | Version | Run | Artifact | Artifact SHA-256 |
| --- | --- | --- | --- | --- |
| Tick | `b81c116f-d93d-4c6b-9d11-ac2477e0e242` | `ec14cc85-85d6-4064-80f1-1354238b88d6` | `e0db2aaf-7412-47d1-ac14-ba8807375549` | `e35a5066a7c77b2e79c50f315a18e042405ab7baa8a414a1a907792bb25d2adc` |
| Pathogen | `92b22f19-0d5d-4576-a7c6-6c9af9343edf` | `796731a3-cd7f-4510-aa0c-738ab74a6a76` | `d93ff6a3-4201-4a06-bfa3-da6026a706d9` | `68baef5f20b1e41821d0e6955cbb1809262e0f3624e387e88c04f6ddb0266f2f` |

Public source-version/timestamp fields are not used to fabricate these anchors.
Source attribution: CDC ArboNET Tick Module. API projection documentation was
inspected at `64244569b3f3950f68709c3a0329ef32dbb2c182`; no shared contracts
or other worktrees were changed.

## Retained DEV finding, distinct from PROD

The earlier DEV release `governed-2026-09-17-unknown-coverage`, bundle
`55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`,
observed at `2026-10-04T01:01:38.848876+00:00`, has 3,144 unique counties and
both vector species Unknown in all 3,144. Of 3,109 in-scope counties, all are
excluded for vector unknown; 35 are out of scope. Pathogen states are 689
Present, 2,420 No records, 35 Unknown overall (zero pathogen unknown in scope).
Eligible N = 0; primary/sensitivity V and uncertainty undefined. This is a valid
release-specific **NOT_ESTIMABLE**, not an access blocker or zero association.
It is consistent with the [DEV unknown-coverage decision](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/614dbb7e95766e586e4cac6332d126e53e23933e/docs/adr/0032-dev-evidence-only-tick-semantic-coverage.md).

CLI and adapter both validated user `MATTHEWCARAWAY`, role `OH_LYME_DEV_READ`,
database `ONE_HEALTH_LYME_GAP_ATLAS_DEV`, schema `PRESENTATION`, warehouse
`OH_LYME_DEV_INGEST_XS_WH`. Only the DEV `CURRENT_RELEASE_V`,
`CURRENT_SOURCE_METADATA_V` and `CURRENT_COUNTY_ATLAS_V` were read; five agent
SELECTs including two context checks, one county fetch, 30-second adapter limits.
The annual observation view was not used for cumulative states. No internal,
raw, restricted or production warehouse table read was attempted.

| DEV SQL | Query ID | Rows | Executed byte SHA-256 |
| --- | --- | ---: | --- |
| `sql/datasets/65_release_identity.sql` | `01c77e7d-040b-dea2-0064-2d070110a392` | 1 | `9117859c63c7f7177a5eb0580b2fa7c1e0f68bd94020d11c54543f997ef03d07` |
| `sql/datasets/65_source_identity.sql` | `01c77e7d-040b-d63b-0064-2d07011097be` | 2 | `4cf486a5539a3ecbbaeed499b9719a25398d89718d612dcb9e90894f8b750f1f` |
| `sql/datasets/65_county_evidence.sql` | `01c77e7d-040b-dea2-0064-2d070110a396` | 3,144 | `b6d2278038721fa12266ff88f6ff05eb65442d1306225cf85387c54f130e2f42` |

Private DEV snapshot byte SHA-256
`4ba8b92f9e2a5967bd68c5e5a7a545a70a688aba794dbcfbe770d092f5b3c062`;
exact local replay:

```powershell
uv run python scripts/eda_65.py --snapshot outputs/65/snapshot.json --expected-sha256 4ba8b92f9e2a5967bd68c5e5a7a545a70a688aba794dbcfbe770d092f5b3c062 --output outputs/65-replay
```

The later supplied DEV shared-capture digest
`be74f3affff2e7753f14e7b804d672fb83d21eabe8f1dc4abead873ea21e8e45`
was verified for intake, but its rows were not used to replace or recompute the
registered PROD association. No fixtures or raw extracts are committed.
