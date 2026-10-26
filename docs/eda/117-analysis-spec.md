# ML #117 visual diagnostics: registered specification v1

- **Spec/version and owning issue:** `117-visual-diagnostics/v1`, [ML #117](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/117), parent [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway authorized this story through the EDA orchestrator. This run does not authorize a Tier 1 change, a PROD write, a UI, a deployment, or a public score. It does not reopen #112. It does not refit the #114 register or the #110 clusters.
- **Question / decision / allowed interpretation:** Which visual summaries reveal defensible Atlas county, space, or time patterns that standard tables and choropleths miss? The decision is keep, revise, or stop for analyst use of the diagnostic panel. A chart is a surveillance-documentation display. It is not incidence, risk, burden, or causation. `No records` and `Unknown` are documentation states, not biological negatives. A missing human floor is not zero. A published count is a lower bound (CDC floor 5). Do not train on the Tier 1 score, on `EVIDENCE_COMPLETENESS`, or on latent-class membership. No interpolated geospatial surface and no 3D surface.
- **Estimand:** Four pre-registered diagnostics. (a), (b), and (c) are visual comparisons against a simpler baseline. (d) is a documented limitation unless an approved fitted model with a valid held-out evaluation already exists. None is known, so (d) is expected to stay not estimable. No new model is fit. `EXPERIMENTS` is not written.

## (a) Hexbin of two continuous county means

- **Data it needs:** County means of January 2025 `nclimgrid_tavg_county_day` (degrees Celsius) and `nclimgrid_prcp_county_day` (millimeters per day). A day is eligible when `VALUE_STATE` is `OBSERVED` or `ZERO` and the #107 parsed value is non-null. The parsed value is `county_distributions._climate_value_sql`: `COALESCE(VALUE_NATIVE_DOUBLE, TRY_TO_DOUBLE(TO_VARCHAR(VALUE)))`, with a recorded `ZERO` and a null payload treated as 0. This is the #107 numeric estimand. It is not the #110 / #114 native-double rule, which found no county with 20 usable `VALUE_NATIVE_DOUBLE` days. A county enters only when both measures have at least 20 eligible days. The optional stratifier is `HUMAN_STATUS`, two panels: `published_count_floor` and `no_county_linked_record`. Any other human status is excluded from the panels and counted. Human status is a 2023 documentation label drawn beside January 2025 climate. It is not a climate effect.
- **Baseline simpler chart:** Two marginal histograms on the same county means, using the edges below, plus one Spearman coefficient and one Pearson coefficient on the same complete pairs. Spearman is `cross_domain.spearman_arrays`, which matches `test_selection.spearman_rho`. Pearson is the linear baseline only. It is not a new discovery pair and it is not added to the #114 family.
- **Usefulness criterion, frozen before the fit:** The hexbin is useful when any one of these holds on the eligible cohort.
  1. The modal hex is not the cell at the pair of one-dimensional hex modes (the axial `q` with the most in-extent counties, and the axial `r` with the most). That is a joint mode the separate hex margins do not show. Ties break toward the smaller axial coordinate.
  2. The absolute difference of Spearman and Pearson is at least 0.10.
  3. The two human-status panels both have a publishable modal hex, and their centers differ by at least 2 degrees Celsius or at least 0.5 millimeters per day.

  A hex with a count from 1 to 10 cannot be the mode and does not enter a one-dimensional hex margin. Marginal histogram bins, used only as the baseline chart, tie toward the lower edge. The frozen extents are temperature [-20, 20] degrees Celsius and precipitation [0, 12] millimeters per day. Points outside an extent are overflow. They stay in the Spearman and Pearson pair and are omitted from the hex counts. If fewer than 500 counties have 20 days on both measures, or if more than 20 percent of that cohort falls outside either extent, (a) is not estimable. The extents are not widened after the result is seen.
- **Grid:** Normalize each axis to the unit interval on those extents. Hex size is 0.12 on that square (pointy-top axial coordinates, cube rounding). Marginal temperature edges are -20, -18, ..., 20. Marginal precipitation edges are 0, 0.5, 1, 1.5, 2, 3, 4, 6, 8, 12.

## (b) Hierarchically ordered correlation heatmap

- **Data it needs:** The #114 cross-domain columns on the same prepared county cohort: `log_population`, `svi_percentile`, `uninsured_percentile`, `rucc_2023`, `human_published`, `tick_established`, `tick_reported`, `pathogen_present`. Definitions, the unit rule, and the Unknown / out-of-scope exclusions are `cross_domain._frame` and `cross_domain.prepare_counties`. Pairwise complete observations. A missing feature is not filled with zero. Climate does not enter this matrix. #114 already dropped January climate under the native-double rule, and this story does not reopen that register.
- **Baseline simpler chart:** The same Spearman matrix printed in the frozen definition order above (the order of the #114 redundancy heatmap), plus the #114 ranked coefficients where the pair exists. This story does not recompute state-cluster intervals. Where a pair matches a #114 or #116 display, the write-up cites that interval instead of a new one.
- **Usefulness criterion:** Average-linkage (UPGMA) order on distance `1 - abs(Spearman)`. A pair with n below 11, or a missing coefficient, has distance 1. The diagonal distance is 0. Ties merge the lower index first. The heatmap is useful when some contiguous block of at least three variables in that leaf order has every pairwise absolute Spearman at least 0.40 with n at least 11, and that same set is not a contiguous block in the definition order or in its reverse.
- **Missingness:** For each column, the count of prepared counties where the column is null, over 3,144. Pairwise n is the heatmap annotation. Clustering method in the caption: average linkage on `1 - abs(Spearman)`.

## (c) County-by-time view

- **Data it needs:** A repeated county time grain. The only supported grain on the allow-listed presentation release is the January 2025 climate window, `CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V`, measure `nclimgrid_tavg_county_day`, same eligibility and #107 parse as (a), days taken from `PERIOD_START`. Human surveillance is one calendar year (2023). Tick and pathogen statuses are cumulative through 2025-12-31. Those vintages are a #109 coverage fact, not a county time series. `CDC_HISTORICAL_VALIDATED_SNAPSHOTS` and CONFORMED history objects are not read. #112 is not authorized and is not run.
- **What is drawn:** A state-by-day heatmap of the unweighted mean of eligible county days. A state-day with fewer than 11 counties is suppressed. The national daily mean used for the baseline is the unweighted mean of counties in publishable states that day, so a suppressed state cannot be recovered by subtraction. A labeled county-by-day image is not drawn. It would be a county-level series on a Drive chart. Census-region membership comes from `coverage_audit.CENSUS_REGIONS`.
- **Baseline simpler chart:** One national daily mean line over the same days, and a one-number-per-state January mean (the table a single choropleth of the month would also show).
- **Usefulness criterion:** The heatmap is useful relative to the national line when the cross-state range of publishable daily means exceeds 10 degrees Celsius on at least 15 days, counting only days that have at least 10 publishable states. It is useful relative to a single January map or state table when the national daily mean range (maximum minus minimum) exceeds 5 degrees Celsius and at least three distinct states are the coldest publishable state on some day. Both parts are required. If fewer than two distinct `PERIOD_START` dates exist, (c) is not estimable: the release has no county-by-time grain, and that limitation is the result. The extents and thresholds are not revised after the series is seen.

## (d) Feature contribution

- **Data it would need:** An already-approved fitted model and a valid held-out evaluation, with the feature matrix and the held-out predictions still identified. Permutation importance would be read as predictive association, not causal contribution.
- **Baseline:** A table of the model's held-out metric with and without each feature.
- **Usefulness criterion, if a model existed:** The importance display is useful only when the held-out metric is identified and the largest permutation drop is at least 0.02 on that metric's scale. That rule is not applied. No such model is in scope. #114 PCA (three-feature two-component share 0.8847 against the 13 October target 0.8850; cross-domain share 0.5758) is an in-sample variance split, not held-out importance. The stored Tier 1 review batch is not used. (d) is not estimable. No chart is drawn for it.

- **Unit / cohort / geography / time:** One county on the pinned release for (a) and (b). One state-day for the (c) display. Expected atlas count 3,144. This is not a change contrast and not a forecast. Vintages stay misaligned: human calendar 2023, tick and pathogen cumulative through 2025-12-31, SVI and uninsured 2022, population 2022, rural-urban code 2023, climate January 2025.
- **Variables / source / version:** Execution reads `PRESENTATION.CURRENT_RELEASE_V` first and stops unless the pin equals release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. County attributes come from `PRESENTATION.CURRENT_COUNTY_ATLAS_V` using the #114 column list only. Climate uses `PRESENTATION.CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V` columns `COUNTY_FIPS`, `MEASURE_ID`, `PERIOD_START`, `VALUE_STATE`, `VALUE_NATIVE_DOUBLE`, and `VALUE`. No other column is selected. County rows may stay in memory. They are not written to a file, to git, or to Drive. No county name is placed in a chart image.

  October 13 figures that this spec compares, and does not replace:

  | Item | Cited value | Source |
  | --- | --- | --- |
  | Counties / published floor / no county-linked record | 3,144 / 651 / 2,493 | #109, reproduced on this pin |
  | County-mean January average temperature | n=3,109, mean -1.412, median -2.159 | #107 decimal parse |
  | County-mean January precipitation | n=3,109, mean 1.459, median 1.171 | #107 decimal parse |
  | Spearman SVI x log population | 0.1334, interval 0.0155 to 0.2555 | #114 D2 |
  | Spearman log population x RUCC | -0.7596 | #114 D6 |
  | Three-feature two-component share | 0.8847 versus 0.8850 | #114 and the 13 October PCA note |

  No October 13 hexbin, clustered heatmap, or county-by-time figure is in the repository. Absence of that figure is recorded. It is not filled with a new target after the charts are drawn.
- **Missingness rule:** Do not impute. Do not replace a gap with zero, Established, or Present. A recorded climate `ZERO` with a null payload stays an observed zero, as in #107. A null human, tick, or pathogen field stays missing on the #114 coding. `No records` on a binary documentation feature remains the zero level defined by #114, not an imputed gap. Exclusion counts are results. A duplicate `FIPS`, a `FIPS` that is not five digits, a mixed release, or a state missing from the Census map stops the run.
- **Exploratory or confirmatory:** Confirmatory for the release pin, the counts 3,144 / 651 / 2,493, and the decision to leave (d) not estimable. Exploratory for the three usefulness calls. Nothing in the charts is used to change an extent, a hex size, a distance, a threshold, or the #114 feature list.
- **Method / assumption rationale:** The question is whether a display shows a pattern a table or a one-layer map does not. A hexbin shows joint density. A clustered heatmap shows blocks. A state-by-day heatmap shows a within-month path. Each is judged against the baseline named above. Counties in one state share reporting rules. These displays do not report a p-value and do not treat counties as independent. Seed `1172026` is recorded. No draw uses it. Linkage and hex rounding are deterministic.
- **Spatial / temporal dependence:** State-by-day means are descriptive. They are not a spatial model and not a neighbor contrast, so they are not a #113 input. The January window is not a multi-year human panel, so it is not a #112 analysis. The note to #112, when (c) is useful, says only that a within-month temperature path exists.
- **Effect-size / uncertainty output:** Spearman and Pearson for the climate pair, pairwise Spearman and n for the #114 columns, modal-hex centers, cross-state temperature ranges, and the three usefulness flags. No new confidence interval. #114 and #116 intervals are cited, not refit.
- **Key caveat / stop conditions:** Stop if `scripts/check_ml_agent_context.py` is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Stop if the live release id, schema, methodology, scope, or bundle SHA differs from the pin. Stop if the county count is not 3,144, if `FIPS` are not unique five-digit ids, or if any state is outside the Census map. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, CONFORMED history, or `CDC_HISTORICAL_VALIDATED_SNAPSHOTS`. Do not select payload, part text, limitation text, or geometry. A query still running at 10 minutes is cancelled. A county-level climate mean may be held in memory and is not written out.

  This story writes no new table. Rows go to existing `REGISTRY.RUNS`, `EDA.METRICS_LONG`, `EDA.CORRELATIONS`, `EDA.MISSINGNESS`, `EDA.FINDINGS`, `REGISTRY.QUERIES`, and, after a Drive upload, `REGISTRY.ARTIFACTS`. Inserts are insert-only. A second invocation reuses the run id and does not insert again. No `DELETE`. No `GRANT`: no new table is created. `OH_LYME_PROD_READ` has no new object to be granted. The #114 chart registration requested by the ML Lead is a separate insert into `REGISTRY.ARTIFACTS` for run `114-cross-domain-20261026T0822Z`. This story does not upload or edit those Drive files.
- **Result disposition:** **PLANNED.** After execution, apply this rule without changing it.

  **stop** when a gate above fails, or when (a), (b), and (c) are all not estimable.

  **keep** when at least two of (a), (b), and (c) meet their usefulness criteria and (d) remains the documented not-estimable limitation.

  **revise** when the gates pass, (d) remains not estimable, and fewer than two of (a), (b), and (c) meet their usefulness criteria. A chart that is estimable but not useful is still reported. revise means the panel should not be quoted as revealing patterns that tables and choropleths miss.

  keep is permission to cite the named displays with their baselines. It is not permission to train, to rank counties, or to build a UI.

  Follow-up sentences, chosen after the flags and not rewritten:

  | Flag | #114 | #113 | #112 note, not a work order | UI candidate |
  | --- | --- | --- | --- | --- |
  | (a) useful | Joint January climate shape is outside the #114 matrix. Do not add it to that PCA in this run. | No. The hexbin is not a neighbor contrast. | One climate month is not a surveillance panel. | No. The hexbin is an analyst memo, not a UI. |
  | (a) not useful or not estimable | No climate-shape follow-up. | No. | No. | No. |
  | (b) useful | The named block is a feature-reduction note for a later #114 design. This run does not refit PCA. | No. | No. | Yes, as an aggregate correlation view. |
  | (b) not useful | The #114 table and redundancy heatmap are enough. | No. | No. | No. |
  | (c) useful | No. | No. State means are not a neighbor model. | Within-January temperature path and cross-state range exist. #112 is not authorized. | Yes, as a state-by-day aggregate with no county names. |
  | (c) not useful or not estimable | No. | No. | No temporal follow-up. | No. |
  | (d) not estimable | Do not read PCA loadings as importance. | No. | No. | No. |
- **Reproduction / evidence:** SQL in `sql/validation/117_visual_diagnostics.sql`. Runner `scripts/eda_117_visual_diagnostics.py`. Logic `src/lyme_gap_atlas_ml/visual_diagnostics.py`. County preparation and Spearman reuse `cross_domain`. The climate parse reuses `county_distributions`. Run id pattern `117-visual-diagnostics-<UTC yyyymmddThhmmZ>`. Charts under git-ignored `artifacts/charts/117/`, each PNG under 40 KB: `climate-hexbin`, `correlation-heatmap`, `state-day-temperature`. Upload to Drive folder `issue-117` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/117-visual-diagnostics.md`.

  Peer-review checks, frozen with the spec: recompute the row count and the distinct five-digit `FIPS` count; confirm the climate SQL uses the #107 parse and does not select geometry or limitation text; confirm Unknown tick and pathogen counties are null on the binary features rather than zero; confirm a state-day under 11 counties is suppressed and is not labeled with a county name; confirm no `EXPERIMENTS` insert. The write-up names three spot-check counties chosen without reference to the estimates: the smallest `FIPS` with a published floor; the smallest `FIPS` with no county-linked human record; the smallest `FIPS` outside contiguous tick scope. Their climate day counts may be stated in the write-up. They do not appear on a chart.

  ```text
  uv sync --locked --extra dev --extra snowflake
  uv run python scripts/check_ml_agent_context.py
  MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_117_visual_diagnostics.py
  uv run python scripts/verify.py
  ```

## Amendment v1.2 — hex comparison scale, before execution

Usefulness rule (a)(1) does not compare the hex center with the 2°C histogram rectangle. Hex size 0.12 on the unit square is about 5°C wide, so that comparison would pass because the hex is wider than the histogram bin. The histogram remains the baseline chart. The joint-versus-margin test uses the hex grid's own axial margins. No live diagnostic query had been run.

## Amendment v1.1 — disclosure, before execution

Matthew Caraway’s ruling on 2026-10-25: GitHub issue comments, pull-request bodies, and `docs/eda` results write-ups may name counties and may include county-level numbers, including counts under 11. `EDA.METRICS_LONG`, `EDA.CORRELATIONS`, `EDA.MISSINGNESS`, `EDA.FINDINGS`, and the PNG charts still omit a count from 1 to 10. County names do not go into chart titles, axis labels, or Drive files. `EDA.FINDINGS` statements stay aggregate because the lab writer rejects a five-digit county id in prose.

The ML Lead’s #114 artifact handoff is not part of this estimand. `REGISTRY.ARTIFACTS` for run `114-cross-domain-20261026T0822Z` receives three insert-only chart rows using the Drive ids, byte sizes, and SHA-256 values the ML Lead supplied. This story does not upload or edit those Drive files.
