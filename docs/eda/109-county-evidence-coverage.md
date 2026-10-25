# 109: What is covered, missing, censored, or vintage-mismatched in each county signal?

- Issue: [ML #109](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/109), part of [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Question: on the pinned PROD release, what is covered, missing, censored, or vintage-mismatched in each published county signal, and do the 13 October 2026 coverage figures in epic #22 section 4.1 reproduce?
- Spec: [109-county-evidence-coverage/v1.1](109-analysis-spec.md), frozen before any coverage statistic. A status is a reported-burden or surveillance signal. It is not disease risk, incidence, biological absence, or a training label. `No records` and `Unknown` are not negatives. A missing human floor is not zero. A published human count is a lower bound.
- Data: `ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`, `CURRENT_SOURCE_METADATA_V`, `CURRENT_COUNTY_OBSERVATIONS_V` (NLCD measure ids only), and `CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V` (counts, statuses, and period bounds only). Pinned release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`.
- Cohort: one row per county on that release, including the District of Columbia, Connecticut planning-region FIPS, Alaska, and Hawaii. Census region is the state-group grain. The 13 October reference release `governed-2026-10-06-nlcd-demo-cohort` was not re-queried.

## Method and assumptions

Context check before any data query, from `uv run python scripts/check_ml_agent_context.py`: `prod_select` pass, `scratch_write` pass, `prod_write_denied` pass. Role `OH_LYME_ML_AGENT`, warehouse `OH_LYME_ML_LAB_XS_WH`, database `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`. PROD stayed read-only. No `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, historical CDC snapshot, free-text column, payload, or geometry text was selected. Geometry entered only as `GEOMETRY_JSON IS NULL`.

Counts and shares answer the coverage question. No model, imputation, or interval. Counties in a state share reporting rules, so the run stores no confidence interval. Seed `1092026` is recorded and unused. Small cells use the ML Lab writers: a denominator below 11 clears the row, a count of 1–10 is removed, a zero on a denominator of at least 11 is kept, and a complement of 1–10 is also removed so a tiny present count cannot be recovered by subtraction. `REGISTRY.QUERIES.ROWS_RETURNED` is statement cardinality and is not suppressed.

The heatmap undocumented share is prespecified: human status and the two human floors use `no_county_linked_record` or SQL null; tick and pathogen use `No records` or `Unknown`; numeric context fields use SQL null. A high western-blacklegged undocumented share is the species range. Cells whose share is suppressed are drawn gray and labeled `<11`.

## Material findings and limits

Disposition on the frozen rule: **keep**. The three section 4.1 headline counts match exactly, the alignment checks hold, and the remaining differences are named vintage or release-scope differences. Keep is permission to use this coverage table in analyst review. It is not permission to train or publish a score.

### Headlines, compared with 13 October

| Coverage state | 13 October reference | This release |
| --- | ---: | ---: |
| Counties | 3,144 | 3,144 |
| Published 2023 human count floor | 651 | 651 |
| No county-linked human record | 2,493 | 2,493 |

The unpublished share is 2,493 / 3,144 = 0.793. Case-floor SQL nulls are 2,493 and incidence-floor SQL nulls are 2,493, the same counties as `no_county_linked_record`. Context fields have no SQL nulls nationally: social vulnerability, uninsured percent, uninsured percentile, population, rural-urban code, and geometry.

### Surveillance statuses

National county counts, all at or above 11:

| Signal | Levels |
| --- | --- |
| Human | published floor 651; no county-linked record 2,493 |
| Tick rollup | Established 1,404; Reported 490; No records 1,215; Unknown 35 |
| Blacklegged tick | Established 1,307; Reported 475; No records 1,327; Unknown 35 |
| Western blacklegged tick | Established 97; Reported 15; No records 2,997; Unknown 35 |
| *B. burgdorferi* | Present 689; No records 2,420; Unknown 35 |
| Contiguous tick scope | TRUE 3,109; FALSE 35 |

Established tick status equals the sum of the two species Established counts (1,404 = 1,307 + 97). Unknown tick and pathogen status is 35, the same count as counties outside the contiguous tick scope. These human, tick, and pathogen level counts match the October 6 exhaustive description, so that layer did not move between the reference release and this pin.

Derived evidence-completeness scores, profiled only as a recode: 50 on 1,224 counties, 67 on 1,050, 83 on 426, and 100 on 444. Rural-urban codes 1 through 9: 443, 385, 358, 201, 76, 379, 247, 466, and 589.

### Joint partition

Human, tick, and pathogen status partition the 3,144 counties. Publishable cells, largest first:

| Human | Tick | Pathogen | Counties |
| --- | --- | --- | ---: |
| no county-linked record | No records | No records | 1,189 |
| no county-linked record | Established | No records | 582 |
| published floor | Established | Present | 443 |
| no county-linked record | Reported | No records | 442 |
| no county-linked record | Established | Present | 228 |
| published floor | Established | No records | 151 |
| no county-linked record | Unknown | Unknown | 35 |
| published floor | Reported | No records | 31 |
| published floor | No records | No records | 25 |
| no county-linked record | Reported | Present | 16 |

Two additional joint cells are stored suppressed. Established tick with no county-linked human floor is 582 + 228 = 810. Epic #22 section 5.1 named the same large cells; the two cells it described as singletons are the two suppressed cells here and are not restated.

### Vintages and the release difference

The signals are not one time base. Human surveillance is calendar year 2023. Tick and pathogen status are cumulative through 2025-12-31. Social vulnerability is the 2022 index on the 2018–2022 ACS window. Population on the atlas is the 2022 county layer. The rural-urban code is 2023. Land-cover vintage is 2025. Climate on this pin is a county-day window from 2025-01-01 through 2025-01-31.

That climate window is the material difference from 13 October. This release covers 3,144 counties across 31 climate days. Publishable climate status cells: COMPLETE/OBSERVED, 3,109 counties and 321,313 rows; COMPLETE/ZERO, 3,109 counties and 64,203 rows; OUT_OF_SOURCE_COVERAGE/UNAVAILABLE, 35 counties and 4,340 rows. The 13 October note described the climate view as empty or not national. The January 2025 layer is national and is still one month, not a multi-year habitat series.

Land-cover geography remains below the small-cell minimum, so it is not a national layer. The 13 October description of a tiny non-national 2025 land-cover demo still fits. The county count is stored suppressed and is not restated.

Four region undocumented shares are suppressed and labeled `<11` on the heatmap: Northeast human status, Northeast case floor, Northeast incidence floor, and West blacklegged-tick status. A zero share is drawn as zero. It is not the same mark as a suppressed cell.

## Decision

**KEEP**, mapped here to **PROCEED** only for analyst review of this coverage table. The headline counts reproduce. Alignment holds. Vintage mismatch and the new January climate window are named and do not overturn the keep rule.

Smallest next step, as a later story: a multi-year human panel, a national land-cover layer, or a single shared time base. Do not train on the Tier 1 score or on latent-class membership from this result.

## Reproduction and retained evidence

- Run: `109-coverage-missingness-20261025T2105Z`. Issue 109. Status succeeded. Git commit recorded on the run: `ff1f2557b6b14e9249461aea5b85ca8d0e0e9ac7`. A later commit changes chart labels and this write-up only. It does not rerun the PROD audit.
- Release: `governed-2026-10-15-january-climate-prod`. Reference release, not re-queried: `governed-2026-10-06-nlcd-demo-cohort`. Seed `1092026`, unused.
- Entry points: `sql/validation/109_county_signal_coverage.sql`, `scripts/eda_109_coverage.py`, `src/lyme_gap_atlas_ml/coverage_audit.py`, `src/lyme_gap_atlas_ml/snowflake/eda_lab_writers.py`.
- ML Lab rows for this run: `REGISTRY.RUNS` 1; `EDA.METRICS_LONG` 375 (84 suppressed); `EDA.MISSINGNESS` 95 (12 suppressed); `EDA.COLUMN_PROFILES` 15 (0 suppressed); `EDA.FINDINGS` 5; `REGISTRY.QUERIES` 14; `EDA.CORRELATIONS` 0. `EVIDENCE_COMPLETENESS` and `RUCC_2023` each have a duplicate national SQL-null missingness row from the categorical and numeric loops. Both stored missing counts are 0.
- Charts are git-ignored under `artifacts/charts/109/`. Drive file links are added on `REGISTRY.ARTIFACTS` only after a successful upload of each PNG.
- The climate coverage aggregate finished in about 398 seconds, under the 10-minute stop. No county-level extract, free-text column, or chart of named counties left Snowflake.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_109_coverage.py
uv run python scripts/verify.py
```

`--redraw-charts` rebuilds the three PNGs from ML Lab metrics for the existing run. It does not read PROD and does not insert another run.
