# EDA #62: SVI by positive vector evidence state

**Execution status: ACCESS_BLOCKED. Scientific disposition: pending.**
The current authorized consumer route publishes neither tick status nor overall
SVI. This does not prove scientific NOT_ESTIMABLE, inadequate positive-group N,
or no difference. No taxon was selected, no SVI outcomes inspected, and no test,
effect estimate, p-value or uncertainty interval was computed.

Issue: [ML #62](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/62).
Question: Do counties with stronger source-reported vector establishment evidence
differ in overall SVI from counties with weaker-but-positive evidence?
The [registered specification](../methodology/62-svi-vector-evidence-spec.md)
was committed at `a05e83ccce4e27f717a16dd24f2fe1105bb59dbd` before the live
availability audit. Parent #59 and the #60 analysis-spec contract apply.

## Evidence and scope

On 2026-10-04 UTC, the laptop CLI verified user `MATTHEWCARAWAY`, role
`OH_LYME_DEV_READ`, database `ONE_HEALTH_LYME_GAP_ATLAS_DEV`, schema
`PRESENTATION`, warehouse `OH_LYME_DEV_INGEST_XS_WH`. Secondary roles were NONE.
The only data object read was
`ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V`.
The audit set a session-only 60-second statement timeout and returned three
aggregate rows under LIMIT 10. No database object was written; no internal
SEMANTIC/RAW/STAGING/CONFORMED object or source artifact was scanned.

| Published measure | Source | Observation rows | Unique county FIPS |
| --- | --- | ---: | ---: |
| case_count_floor_2023 | human | 3,144 | 3,144 |
| human_status | human | 3,144 | 3,144 |
| incidence_floor_2023 | human | 3,144 | 3,144 |

Live release: `governed-2026-09-17-unknown-coverage`.
Profile query ID: `01c77e7b-040b-dea2-0064-2d070110a36e`.
These are **published county-measure observation counts**, not original source
row counts, eligible vector-group N or SVI complete-case N. The same counties
occur in three measures; 9,432 observations are not 9,432 independent counties.
The raw tick/SVI source-row counts, positive-state counts, source missingness,
geography exclusions, duplicate conflicts, and SVI outcome-state counts are all
unknown because their inputs are not published through this route.

The current [Data V127 consumer contract](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-release/current-county-observations-v1.md)
(Git blob `effe7315a908da1e44408a4e821e4b413ad0f40f`) closes its allowlist to
these three human measures. It explicitly excludes cumulative tick status for
lack of a governed start date and ACS context pending an explicit period
contract. It grants no access to release internals or source artifacts. Thus
absence here is **unpublished input**, never biological absence or missing SVI
at the source. The audit does not inspect human outcome values either.

## Planned sources and method; not executed

The governed [manifest](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-release/governed-2026-09-15-manifest.json)
(Git blob `ef7e08c2919d38bdf6bdaa8ef79316b1bafd00f5`) identifies candidate
CDC sources below. Despite its filename, this manifest declares release
`governed-2026-09-18-unknown-coverage`, **different from the live release**.
These identities are documentary candidate provenance, not a verified linkage
to any analyzed live tick/SVI data. Freeze a matching release before resuming.

| Source | Definition | Source-version ID | Ingestion-run ID | Artifact SHA-256 |
| --- | --- | --- | --- | --- |
| CDC ArboNET cdc-ixodes-county-status-2025, through 2025-12-31 | 1 | b81c116f-d93d-4c6b-9d11-ac2477e0e242 | ec14cc85-85d6-4064-80f1-1354238b88d6 | e35a5066a7c77b2e79c50f315a18e042405ab7baa8a414a1a907792bb25d2adc |
| CDC/ATSDR atsdr-svi-2022-county-layer, ACS 2018–2022 | 1 | b8b6bf61-c6a3-4538-b0df-1b88c61720b1 | 331f367d-9282-4936-9b49-a480db995016 | dc042342a2e5abc108af67b439ec04c86da8b61f9bdd1cf1b1e5ee0462dea7b2 |

Candidate canonical contrast is ESTABLISHED versus REPORTED for one taxon;
not DETECTED pathogen-test results, pooled taxa, UNKNOWN or NO_RECORDS.
Exact source-to-canonical mappings and adequate unique-county N must be checked
before taxon selection. Legacy alpha snapshot counts and fictional fixtures
cannot supply governed eligible N. No substitution was made.

The registered plan screens IXODES_SCAPULARIS then IXODES_PACIFICUS using only
semantics/geography/positive-state N (>=30 each), then national overall SVI
percentile, county-weighted. Planned Mann–Whitney concerns distributions,
not medians alone; probability of superiority, central tendency and overlap
accompany uncertainty. State shares, dominance exclusions and within-state
checks address geographic concentration. There is no observed concentration
result yet. Independent county inference is not justified by county N alone.
The spec sets descriptive-only and NOT_ESTIMABLE limits when dependence-aware
inference cannot be supported. No causal or individual-risk inference is allowed.

## Decision and next step

Keep #62 open pending independent review and accessible governed inputs.
The smallest next step is an owner-approved, read-only immutable consumer
snapshot/projection containing taxon-specific cumulative status and national
SVI with explicit temporal semantics, canonical county identity, source states,
release membership and digests. This work changes no shared contract or grant.
Once accessible, perform outcome-blind eligibility screening and commit the
selected taxon/exact contrast/source identity before inspecting SVI outcomes.

ML implication: no evidence yet that SVI confounds or adds information relative
to vector status. Product implication: no change to vector-evidence or SVI
interpretation. An access blocker cannot support a material/small/no-difference
scientific disposition. The issue's four result categories therefore remain
pending rather than falsely choosing NOT_ESTIMABLE.

## Reproduction and verification

From this repository, with an already selected least-privilege local connection:

```powershell
snow sql -c $env:SNOWFLAKE_CONNECTION_NAME --schema PRESENTATION --secondary-roles NONE -q 'SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE()' --format JSON
# Compare all five fields to the authorized DEV context before continuing.
New-Item -ItemType Directory -Force outputs | Out-Null
snow sql -c $env:SNOWFLAKE_CONNECTION_NAME --schema PRESENTATION --secondary-roles NONE -f sql/validation/62-vector-svi-availability.sql --format JSON | Tee-Object -FilePath outputs/62-availability-cli.txt
$audit62Raw = Get-Content outputs/62-availability-cli.txt -Raw | ConvertFrom-Json
$audit62Raw[1] | ConvertTo-Json | Set-Content outputs/62-profile.json -Encoding utf8
uv run python scripts/eda62_availability.py outputs/62-profile.json
uv run python scripts/verify.py
```

SQL SHA-256 (LF UTF-8):
`da8f2baad19a8f0643b8687e106d93312580e39c22500b26dd1992e1d6cef887`.
Observed transient profile-byte SHA-256:
`3ee71bb02a1b2492dc580973532c7ebdd9916261ca9254fd42969b0b1236e337`.
JSON whitespace may change the latter; the table above retains substantive
evidence. The current pointer can advance, so a fresh audit must report its own
release and cannot silently reproduce historical identity from the pointer.

Mandatory checks passed: contracts/skills/lifecycle/hygiene, Ruff, format,
mypy, **147 pytest tests passed**, one optional Arize SDK skip. Ten issue-local
tests cover unpublished-input/unknown-N safety, publication-versus-eligibility,
single-taxon availability, ambiguous/truncated input, mixed releases,
duplicates and invalid counts. Test profiles are explicitly fictional and
were never used as analysis evidence. No predictive model/experiment/holdout
was created. Live context/profile evidence is separate from offline test proof.

Transient CLI output/profile JSON, caches and virtual environment are ignored
and intentionally not committed. No raw data export, credentials, production
write, paid model call, training, web change, posting, merge or closure occurred.
The [single issue comment draft](62-issue-comment-draft.md) awaits owner review.
