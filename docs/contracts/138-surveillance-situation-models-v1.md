# Surveillance-situation models v1

**Contract:** `surveillance-situation-models` `v1`.
**Owner:** Atlas ML, [story #138](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/138), [task #141](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/141).
**Machine-readable form:** [138-surveillance-situation-models-v1.json](../../config/models/138-surveillance-situation-models-v1.json).
**Names confirmed:** [task #140](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/140), 2026-10-18, all eight names as written in [119-surveillance-latent-classes.md](../eda/119-surveillance-latent-classes.md).

This contract names the two production models. It does not build the county file, approve publication, or write Snowflake.

## Two fits

| | Four-state | Tick and pathogen |
| --- | --- | --- |
| Model | `surveillance-situation-four-state` `v1` | `surveillance-situation-tick-pathogen` `v1` |
| Role | Primary descriptive classification | Secondary grouping |
| Indicators | Human status, blacklegged tick, western blacklegged tick, pathogen | Blacklegged tick, western blacklegged tick, pathogen |

A class identifier from one model is not a class identifier in the other model. The research fit used indexes 0, 1, 2, and 3 inside each fit. Those indexes stay in `fit_class_index` so the research result can be read. The production identifier adds the model and version, for example `surveillance-situation-four-state.v1.class-0`. The same index in the other fit is `surveillance-situation-tick-pathogen.v1.class-0`. Same index, different counties, different identifier.

## Pinned input

| Field | Value |
| --- | --- |
| Release | `governed-2026-10-15-january-climate-prod` |
| Bundle SHA-256 | `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d` |
| Primary seed | `1192026` |
| Counties | 3,144 |
| Research merge | `a2f9bad41f1ddb793e364399afbdd5fbad008b7a` |
| Fit code revision | `cd936fe345664e606c916b137dd642caa0d6d73b` |

`No records` stays a category. `Unknown` stays a real class. It is not a missing assignment. Do not impute. Unavailable surveillance is not zero.

A later Atlas release does not silently inherit these assignments. Carry-forward, a new batch version, or a block requires a dated decision.

## Classes

### `surveillance-situation-four-state` v1

| Identifier | Name | Counties |
| --- | --- | ---: |
| `surveillance-situation-four-state.v1.class-0` | Established blacklegged tick | 801 |
| `surveillance-situation-four-state.v1.class-1` | Unknown tick and pathogen status | 35 |
| `surveillance-situation-four-state.v1.class-2` | Western blacklegged tick recorded | 112 |
| `surveillance-situation-four-state.v1.class-3` | Pathogen not recorded | 2,196 |

Class 3 means the pathogen has no record and the western blacklegged tick has no records. Blacklegged tick status inside that class is mixed.

### `surveillance-situation-tick-pathogen` v1

| Identifier | Name | Counties |
| --- | --- | ---: |
| `surveillance-situation-tick-pathogen.v1.class-0` | Established blacklegged tick | 1,325 |
| `surveillance-situation-tick-pathogen.v1.class-1` | Blacklegged tick not established, pathogen not recorded | 1,687 |
| `surveillance-situation-tick-pathogen.v1.class-2` | Western blacklegged tick established | 97 |
| `surveillance-situation-tick-pathogen.v1.class-3` | Unknown tick and pathogen status | 35 |

Class 0 contains counties with pathogen present and counties with no pathogen record. Its probability does not measure pathogen presence. Human status was not an input.

## Not permitted

Do not read either model as disease risk, incidence, pathogen absence, or a Tier 1 priority. Do not use a four-state class as a tick-and-pathogen class. Do not use a tick-and-pathogen class as a four-state class. Do not serve these identifiers through an API in this task.
