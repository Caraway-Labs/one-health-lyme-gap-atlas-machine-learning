# ML #104: PROD Tier 1 feature admission and selected-model check

**Decision:** admit the pinned PROD release as `tier1-county-features-v2`,
with the same six predictor meanings and selected
`tier1-statistical-reference-v1`. This is experimental county
surveillance-review priority, never Lyme disease risk or incidence.

## Read-only source proof

`ATLAS_PROD_READ` was verified as `OH_LYME_PROD_READ` in
`ONE_HEALTH_LYME_GAP_ATLAS_PROD`; `COMPUTE_WH` was explicitly selected for
each PROD query. DEV used `ATLAS_DEV_READ`, `OH_LYME_DEV_READ`, and
`OH_LYME_DEV_INGEST_XS_WH`. Only `PRESENTATION.CURRENT_RELEASE_V` and
`PRESENTATION.CURRENT_COUNTY_ATLAS_V` were read. No Snowflake object was
written. Local raw query captures remain ignored under `.local/ml-104/`.

| Input | DEV | PROD | FIPS-level difference |
| --- | --- | --- | ---: |
| Release | `governed-2026-09-17-unknown-coverage` | `governed-2026-09-18-unknown-coverage` | lineage |
| Bundle SHA-256 | `55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233` | `038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026` | lineage |
| FIPS | 3,144 unique | 3,144 unique | 0 |
| Human status | 651 published, 2,493 no linked record | same | 0 |
| Published count floor | 651 nonnull, range 5–3,262 | same | 0 |
| Pathogen status | 689 Present, 2,420 No records, 35 Unknown | same | 0 |
| SVI percentile | complete, range 0–1 | same | 0 |
| RUCC | complete, codes 1–9 | same | 0 |
| *I. scapularis* | 3,144 Unknown | 1,307 Established, 475 Reported, 1,327 No records, 35 Unknown | 3,109 |
| *I. pacificus* | 3,144 Unknown | 97 Established, 15 Reported, 2,997 No records, 35 Unknown | 3,109 |

The exact sorted-LF (no trailing LF) FIPS-set SHA-256 in both environments is
`4a74ab4f8638b4a02a18b0db4abe9597fc2a6bf364a103314de346338015c690`.
Generated feature matrices have zero differences in all 18,864 predictor
cells and zero differences in feature-evidence state. PROD aggregate vector
context is 1,404 Established, 490 Reported, 1,215 No records, 35 Unknown.

## Model validity

The statistical reference aggregates standardized human published-floor,
log-floor magnitude, pathogen modal-state mismatch, and SVI deviations. It
does not read vector state or RUCC. Identical ordered FIPS and predictor
values give identical raw scores, tied-rank percentiles, and materialized
tiers. The rerun score min/median/p90/max is 0.4431 / 0.7803 / 1.6473 /
2.5400; HIGH 315, MEDIUM 628, LOW 2,201. SUFFICIENT 651,
INSUFFICIENT 2,493, NOT_ESTIMABLE 0. The top 10 all have published human
floors and pathogen Present. None of the 35 vector-Unknown or 35
pathogen-Unknown counties appears in the top 50. The top 50 have vector
Established context, but vector is not a scoring input; this co-occurs with
the published human/pathogen evidence that drove the unchanged DEV ranks.
The prior selected-model limitations, including concentration in high
published floors and Northeast/urban counties, remain. Floors are protected
lower bounds, not population-adjusted incidence.

## Reproduction and publication boundary

Run the v2 feature command in its contract, then run
`tier1_persisted --environment prod` from the reviewed source commit. The
builder validates exact release, role, warehouse, 3,144 unique FIPS,
selected model, score/tier/evidence invariants, and output lineage before
writing ignored JSON artifacts. The batch ID includes the source commit,
release, bundle, feature version, model, evaluation, and policy. A PR-head
candidate is review evidence only; a squash merge changes its source commit
and requires one post-merge regeneration before DATA #627 publication.
The generated timestamp participates in the canonical digest, so preserve
the first approved artifacts rather than casually regenerating them.
