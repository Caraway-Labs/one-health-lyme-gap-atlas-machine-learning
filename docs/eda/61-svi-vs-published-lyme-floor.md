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

**Execution status: ACCESS_BLOCKED. Scientific disposition: pending. Feature implication: UNKNOWN.**
No real association statistics, cohort counts, sensitivity result, or spatial diagnostics
were computed. This is neither evidence of no signal nor a demonstrated NOT_ESTIMABLE
finding. Issue #61 remains incomplete pending governed input validation and review.

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

### Access evidence (2026-10-04 UTC)

Only connection/session context was queried. No governed data table was read.
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
source reads stopped. No stronger role, production route, interactive login,
grant, credential change, ingestion, or warehouse export was attempted.

### Result accounting

| Required evidence | Actual result |
| --- | --- |
| Lyme source observation rows / distinct source geography | unavailable; access blocked |
| Unique canonical counties / eligible analysis N | unavailable; access blocked |
| Missing SVI / invalid population / absent floor / unmatched FIPS | unavailable; no real cohort inspected |
| Zero versus positive observed floor / unknown outcomes | unavailable; preserved separately by code |
| Spearman / uncertainty / distribution | not computed |
| Registered sensitivity | not executed |
| Material spatial dependence | not assessed on real data; county-independent inference prohibited |

Product decision: do not change SVI feature selection or claim any relationship
from this packet. The smallest unblock is an owner-verified authorized DEV
context with an accessible explicit schema, or a reviewed immutable snapshot
whose source authority, 2022 case scope, population compatibility, canonical
mapping and release identity are demonstrated. This asks for evidence/access
resolution, not a stronger role or a new scientific definition.

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

After those prerequisites pass, the snapshot JSON has two arrays:
`svi` (county_fips, population, svi_percentile) and `human`
(source_record_id, county_fips, report_year, case_status, frequency).
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

Final local verification: `uv sync --extra dev` and
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

## Single held issue-comment draft

**Not posted.** Hold for the requesting reviewer's independent scientific/code
review. This is a decision-ready blocker report, not the final four-disposition
result comment required to complete #61. Replace the pending disposition only
after valid evidence permits SIGNAL / WEAK_SIGNAL / NO_SIGNAL / NOT_ESTIMABLE.
Do not map an access failure to NOT_ESTIMABLE merely to fit the issue template.

### EDA #61 result

**Disposition:** pending — ACCESS_BLOCKED (scientific result unavailable).

**Headline:** Governed 2022 SVI versus the published county-linked Lyme floor
cannot yet be evaluated because required least-privilege DEV context validation
failed before source reads.

**Evidence:**

- N counties: unavailable; no real cohort was inspected.
- Spearman/Pearson: not computed; Spearman preregistered.
- Uncertainty: unavailable; no naive county-independent p-value.
- Missing/excluded: unavailable; source-row and county accounting implemented.
- Sensitivity result: not executed; outer 1% population tails preregistered.

**Interpretation:**

- Access failure does not demonstrate no association or scientific NOT_ESTIMABLE.
- SVI population is an ACS 2018–2022 period estimate; 2022 case scope and live
  release/denominator/mapping compatibility remain unvalidated.
- No result supports causal, incidence, individual-risk, underreporting or
  exposure-location claims; real spatial dependence has not been assessed.

**Feature implication:** UNKNOWN.

**Product implication:** Hold SVI feature decisions until an authorized explicit
DEV schema or reviewed immutable snapshot resolves the named prerequisites.
Do not substitute another denominator or year, or infer signal from fixtures.

**Links:** [Draft PR #89](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/89),
[EDA artifact](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/blob/codex/ml-61-svi-floor/docs/eda/61-svi-vs-published-lyme-floor.md),
[candidate source release manifest](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/eb984723080c9ff3a3484a6d30f9adb0197bd847/docs/contracts/semantic-release/governed-2026-09-15-manifest.json).
Exact source versions, runs and digests appear above and remain subject to live
source validation. No merge, closure or issue comment before requesting review.
