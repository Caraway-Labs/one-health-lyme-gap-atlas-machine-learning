# ML #119 leakage review

Dataset `surveillance-latent-class-counties` `v1`. Feature set `surveillance-latent-class-indicators` `v1`. Owning task: [ML #131](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/131).

## Decision

The four categorical statuses are the only indicators. The builder fails when any other column is present, so a floor, a review score, or a land-cover field cannot enter the design matrix by being left on the row.

## Why the excluded fields stay out

- `CASE_COUNT_FLOOR_2023` and `INCIDENCE_FLOOR_2023` are the published human magnitude. They are null exactly where human status is `no_county_linked_record`. Putting them in the class model would turn a documentation status into a censored outcome and would reuse the label later stories still have to define.
- `EVIDENCE_COMPLETENESS` is a recode of the human, tick, and pathogen flags on this release. It adds no independent information and would double-count those flags.
- The September review tier is an output of `tier1-statistical-reference-v1` on an older release. Using it would teach the grouping to copy that score.
- Land cover exists for two counties and is outside automatic model admission for this release.
- No earlier model output is an input. This story is the first grouping in the epic.
- `POPULATION` is stored for the later population share. It is not returned by `estimand_a` or `estimand_b`.
- `STATE` is stored so the evaluation can find Alaska and Hawaii. It is not an indicator, so the class model does not use state policy as a feature.

## Time and availability

The model describes one published snapshot. It does not predict a later outcome, so there is no label from after the release to leak. Human status is the 2023 surveillance year. Tick and pathogen status are cumulative through 2025-12-31. Those vintages differ, and the class names must keep that difference visible. The fit still has to match release `governed-2026-10-06-nlcd-demo-cohort` and bundle SHA-256 `603afb135a1a5c958d1d56d48d580d9942c67eb38986caf8b4b3acf69fcde2c9` before it reads counties.

There is no outcome holdout in this dataset. Class-count selection remains the stability rule in the analysis spec. A random county split would not be a leakage control for a census of one snapshot.

## Missingness

Blanks stay as categories. Nothing is filled with zero, Established, or Present. An unrecognized level stops the build instead of being coerced.
