# Tier 1 county features v1 (ML #24)

**Feature-set version:** `tier1-county-features-v1`  
**Owner:** Atlas ML  
**Snapshot:** DEV `governed-2026-09-17-unknown-coverage`, bundle SHA-256
`55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`.
The release bundle fixes source membership and revisions. Source products below
are the governed CDC 2023 county Lyme surveillance, CDC ArboNET pathogen status
through 2025, and CDC/ATSDR SVI 2022 (2018–2022 ACS). The DEV read role can
read the release and county views but not `SEMANTIC_DATA_SOURCES`; exact source
version IDs are therefore resolved by this immutable bundle, rather than
claimed from an unreadable table. This release is DEV evidence, not PROD.

The canonical population is the release's 3,144 five-digit county FIPS. A row
is generated for each. The five numeric predictor columns below are ordered as
shown; `county_fips` is a string key, not a predictor. Raw state and context
columns follow the predictors. ML #27 can select `FEATURE_COLUMNS` directly.
It must retain evidence state in evaluation and decide model score eligibility
under its own gate. No scaling or imputation occurs here.

| Feature name | Domain | Governed source/measure and version | Type, transformation, units | Missing and zero semantics | Rationale | Tier 1 |
| --- | --- | --- | --- | --- | --- | --- |
| `human_published_floor` | human | CDC Lyme 2023 `human_status`; pinned release above | Indicator: 1 for `published_count_floor`, 0 for `no_county_linked_record`; unitless | 0 means no county-linked published record, **not zero cases**. Any other state fails. | Distinguishes published human surveillance evidence from no county-linked evidence. | yes |
| `pathogen_present` | pathogen | CDC ArboNET *B. burgdorferi* `burgdorferi_status`, cumulative through 2025; pinned release | Indicator: 1 for `Present`, else 0; unitless | 0 is a categorical encoding, not pathogen absence. | Captures reported pathogen status. | yes |
| `pathogen_no_records` | coverage/pathogen | Same source and status | Indicator: 1 for publisher `No records`, else 0; unitless | 1 means publisher no records, not biological absence. | Separates source evidence gap from reported presence. | yes |
| `pathogen_unknown` | coverage/pathogen | Same source and status | Indicator: 1 for `Unknown`, else 0; unitless | 1 retains unknown source coverage; no imputation. | Preserves the restricted source parity gap. | yes |
| `svi_percentile_2022` | SVI | CDC/ATSDR 2022 county `RPL_THEMES`; pinned release | Numeric source percentile in [0, 1], no transform | Null fails generation; numeric 0 is a valid observed percentile. SVI is context, not causal or individual risk. | Adds place-based context to anomaly profiles. | yes |

The three pathogen indicators are mutually exclusive and sum to one. This is
categorical state encoding, not three independent claims. A zero in one
indicator means that category is not the observed category; it does not turn
`Unknown` or `No records` into an observed biological zero. Human absence is
likewise retained in `human_evidence_state`. The raw `pathogen_evidence_state`,
`vector_evidence_state`, `rucc_2023_context`, and
`feature_evidence_state` columns preserve interpretation. `PARTIAL` means
human has no county-linked record or pathogen coverage is unknown; `OBSERVED`
means those two selected evidence families have explicit source states. This
is a feature construction state, not ML #30's sufficiency or tier decision.

## Candidate disposition

| Candidate | Domain | Decision and reason |
| --- | --- | --- |
| `case_count_floor_2023` / `incidence_floor_2023` | human | Excluded: privacy-protected floors are not complete incidence; null for no county-linked record. Preserve state first. |
| `scapularis_status` / `pacificus_status` / `tick_status` | vector/coverage | Excluded as predictors: both species states are `Unknown` for all 3,144 DEV release counties; the combined status is derivative and constant. Raw vector state is retained as context. |
| `rucc_2023` | RUCC | Retained as categorical context for #30 slices; excluded as a predictor to avoid treating codes 1–9 as ordered distances or overweighting nine one-hot classes. |
| `evidence_completeness`, `default_score`, priority tiers | coverage/priority | Excluded: derived from the deterministic County Review Priority framework and would be a shortcut. |
| NEON site/event coverage and testing | coverage | Excluded: site/event evidence is not county representative and has no approved county aggregation. |
| Environmental and other optional sources | optional | Deferred; not needed for Tier 1. |

## Reproduction and guards

From this repository, with a locally configured read-only DEV PAT selector:

```powershell
$env:SNOWFLAKE_CONNECTION_NAME = '<approved read-only DEV connection>'
uv run python -m lyme_gap_atlas_ml.tier1_features --output .local/tier1-counties.csv --report .local/tier1-coverage.json
```

The command checks user, role, database and warehouse before any data read,
then fails if the current release ID or bundle hash differs. It reads only
`PRESENTATION.CURRENT_RELEASE_V` and `PRESENTATION.CURRENT_COUNTY_ATLAS_V`.
It rejects changed source states, duplicate/invalid FIPS, row-count drift,
invalid SVI/RUCC ranges, or constant selected predictors. Output is sorted by
FIPS and contains no score, tier, state identifier, future label, or numeric
county identity as a predictor. Generated CSV and JSON are local artifacts;
the source and this manifest are versioned. The generation timestamp and code
commit identify a run. A changed release needs reviewed feature admission and
a new version rather than silent regeneration.

No Snowflake write, model training, API/Web change, or model tier policy is in
this contract.
