# Surveillance latent-class counties v1

**Dataset:** `surveillance-latent-class-counties` `v1`.
**Feature set:** `surveillance-latent-class-indicators` `v1`.
**Owner:** Atlas ML, [story #119](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/119), [task #131](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/131).
**Question:** [119-analysis-spec.md](../eda/119-analysis-spec.md).

This contract admits one county snapshot for latent class analysis. It does not approve a production model, a Snowflake write, an API, or a disease-risk interpretation. Governed ingestion and canonical normalization stay in the data repository. The supervised v1 lineage bundle is not filled here: this story has no outcome label, and the split, evaluation, experiment, registry, and Arize links belong to later stages or are out of scope.

## Snapshot

| Field | Value |
| --- | --- |
| Release | `governed-2026-10-06-nlcd-demo-cohort` |
| Bundle SHA-256 | `603afb135a1a5c958d1d56d48d580d9942c67eb38986caf8b4b3acf69fcde2c9` |
| View | `PRESENTATION.CURRENT_COUNTY_ATLAS_V` |
| Database | `ONE_HEALTH_LYME_GAP_ATLAS_PROD` |
| Grain | one row per five-digit county FIPS |
| Cohort | 3,144 counties and county equivalents, including the District of Columbia, Connecticut planning regions, Alaska, and Hawaii |
| Human vintage | calendar year 2023 |
| Tick and pathogen vintage | cumulative through 2025-12-31 |
| Population vintage | 2022 county population, reporting denominator only |
| Provenance already recorded | [prod-exhaustive-eda.md](../eda/prod-exhaustive-eda.md) |

The bundle SHA above is the identity published by that read-only catalog pass. The fit must run [119_release_identity.sql](../../sql/validation/119_release_identity.sql) with the approved read-only role and refuse the extract when the live release or bundle differs. This data task did not open a new warehouse session.

## Admitted columns

| Column | Role | Allowed values |
| --- | --- | --- |
| `FIPS` | identity | five-digit string |
| `STATE` | identity for the later Alaska and Hawaii check | two-letter code |
| `HUMAN_STATUS` | Estimand A indicator | `published_count_floor`, `no_county_linked_record` |
| `SCAPULARIS_STATUS` | Estimand A and B indicator | `Established`, `Reported`, `No records`, `Unknown` |
| `PACIFICUS_STATUS` | Estimand A and B indicator | `Established`, `Reported`, `No records`, `Unknown` |
| `BURGDORFERI_STATUS` | Estimand A and B indicator | `Present`, `No records`, `Unknown` |
| `POPULATION` | reporting denominator | positive integer |

`STATE` and `POPULATION` are not model indicators. Estimand B uses the two tick columns and the pathogen column only.

The human blank on this release is `no_county_linked_record`. There is no human `Unknown` level to invent. `No records` and `Unknown` stay as their own tick and pathogen levels. A null, a blank string, or any other level fails the build. Counties are not dropped to finish the table.

## Extract

The read list is [119_surveillance_latent_class_inputs.sql](../../sql/datasets/119_surveillance_latent_class_inputs.sql). The offline builder is `lyme_gap_atlas_ml.latent_class_inputs`. It rejects every column outside the admitted set, including the case floor, the incidence floor, evidence completeness, a review tier, and land cover.

## Permitted use

Build the two latent-class estimands in the analysis spec. Report county counts and population totals after the class count is chosen. Keep the tick-and-pathogen probabilities separate from the four-state assignment.

## Not permitted

Do not impute or standardize. Do not treat a class as disease risk or incidence. Do not publish a production score. Do not serve the assignment through an API. Do not use this dataset as a labeled training target for a later story.
