# ML #62 outcome-blind PROD selection freeze

This record is committed before any SVI distribution/test/effect inspection.
Use the original [analysis specification](62-svi-vector-evidence-spec.md),
including the published-projection descriptive EDA amendment committed at
`42324b7ff1eb53bf3c660300121b7bf738ac43c6`. This is descriptive exploratory EDA
of the governed published county projection, not native lineage validation or
ML feature admission. No question, threshold or method was chosen from outcomes.

## Frozen input identity

- Release: `governed-2026-09-18-unknown-coverage`, schema `1.0.0`, method `semantic-1.0.0`.
- Served bundle SHA-256: `038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`.
- Capture raw-byte SHA-256: `a62e522c2da8482a20fd1ad055fe280acd15c60e49f63d6b2d331f9fef50395e`.
- Canonical FIPS normalized SHA-256: `f2651ec6a9375476e3ff09efb4c2a699cd5690ffd3f0c982aeacad967c21c241`.
- Context capture SHA-256: `88c2c875bc79e6cea13c0fcc6dad5e7c5d722802066aff308762386eb78774af`.
- County capture query: `01c77eba-040b-dea2-0064-2d070110a5fa`.
- Read-only context: user MATTHEWCARAWAY, role OH_LYME_PROD_RUNTIME,
  database ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION,
  warehouse OH_LYME_PROD_INGEST_XS_WH; secondary roles NONE.
- One authorized capture from existing `CURRENT_COUNTY_ATLAS_V` and
  `CURRENT_RELEASE_V`, query `sql/datasets/eda62_prod_consumer_capture.sql`.
  All 3,144 ordered unique FIPS match the canonical county universe; zero
  malformed/duplicate identities. Before/after release/bundle match and each
  county row is pinned to that release/bundle. Limit 3,145 county rows and
  30-second statement timeout; no raw/private-source reads or object writes.
- Raw capture remains private and ignored. Reuse it, including its pathogen
  state column for parent-coordinated #65 review; do not upload or recapture.

## Outcome-blind counts and selected contrast

| Source-defined species field | Established | Reported | No records | Unknown |
| --- | ---: | ---: | ---: | ---: |
| scapularis_status | 1,307 | 475 | 1,327 | 35 |
| pacificus_status | 97 | 15 | 2,997 | 35 |

These are actual unique consumer-county status counts from the frozen capture,
not fixture/synthetic counts and not original sampling-event/source-row N.
Both fields describe the same 3,144 counties; do not pool taxa as independent.

**Selected taxon: IXODES_SCAPULARIS; selected field: `scapularis_status`.**
Exact consumer states `Established` versus `Reported` map to canonical
ESTABLISHED versus REPORTED under the existing approved source vocabulary.
The taxon is first in the preregistered candidate order and both positive groups
meet the >=30 county N floor. IXODES_PACIFICUS additionally fails that floor in
Reported (15); no outcomes were used in either decision.

The primary source-positive cohort is **1,782 unique counties** (1,307 / 475).
Exclude 1,327 No records and 35 Unknown counties without claiming biological
absence. SVI missing/sentinel/domain and complete-case counts have not been
inspected at this selection stage; apply the preregistered rules next and never
switch taxa because of outcomes. County weighting, not population weighting.

## Source and interpretation scope

CDC ArboNET `cdc-ixodes-county-status-2025`, definition 1, cumulative through
2025-12-31; SVI `atsdr-svi-2022-county-layer`, definition 1, overall national
county `RPL_THEMES` percentile using ACS 2018–2022. Source tuples/artifact
digests remain those in the matching September 18 governed manifest and
historical release receipts documented in the EDA artifact. Cumulative status
and 2022 context are not contemporaneous annual measurements or causal effects.
Private per-record/native metadata validation remains an unclaimed limitation,
not a universal requirement for this authorized published-projection EDA.

Execute registered Mann–Whitney/effect/descriptive outputs and whole-state
bootstrap (seed 62, 2,000 draws). Retain spread/overlap and dominant-state/
within-state sensitivity. Rank neutrality does not mean distribution equivalence.
Record all exclusions, uncertainty and unsupported inference explicitly.
