# 117: Which visuals show patterns that tables and choropleths miss?

- Issue: [ML #117](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/117).
- Parent: [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
- Spec: [117-visual-diagnostics/v1](117-analysis-spec.md), amendment v1.2 before execution.
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`, and county means plus state-day means from `CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V`. Pinned release `governed-2026-10-15-january-climate-prod`.
- Cohort: 3144 counties. Published floor 651. No county-linked record 2493.

## Method and assumptions

The hexbin, the clustered Spearman heatmap, and the state-by-day temperature heatmap are the three displays. Feature contribution is the predeclared not-estimable chart. Baselines and thresholds are in the spec. No value was imputed as zero. Seed 1172026 is unused.

## Material findings and limits

1. Question

Which visual summaries reveal defensible Atlas county, space, or time patterns that standard tables and choropleths miss?

2. Method (and why; link the spec)

Spec [117-visual-diagnostics/v1](docs/eda/117-analysis-spec.md), frozen before the fit, with amendment v1.2 before any diagnostic query. The hexbin uses the #107 climate parse and a 20-day county mean. Spearman reuses `cross_domain.spearman_arrays`. The heatmap clusters the #114 feature list with average linkage on 1 minus absolute Spearman and does not refit those intervals. The time view is a state-by-day January temperature mean because a labeled county-by-day image would be a county series on a chart. Feature contribution is not estimated: no approved held-out model exists. No 3D surface and no interpolated map.

3. Key findings with numbers

Hexbin: estimable=True, useful=False, n=3109, overflow_n=0, Spearman=0.5589, Pearson=0.5061, joint_mode_differs=False, coefficient_gap=False, panel_shift=False. Reason: estimable.
Temperature days with at least 20 eligible values: 3109. Precipitation days with at least 20 eligible values: 3109.
Heatmap: estimable=True, useful=True, block=tick_established, human_published, pathogen_present. Leaf order: tick_reported, svi_percentile, uninsured_percentile, log_population, rucc_2023, tick_established, human_published, pathogen_present.
State-by-day temperature: estimable=True, useful=True, distinct days=31, wide days=31, national range=16.4265, coldest states=ID, ME, MN, ND, SD, VT, WI, WY. Reason: estimable.
Feature contribution: not estimable. No approved fitted model with a valid held-out evaluation is in scope. 114-cross-domain/v1 PCA is an in-sample variance split, not held-out feature contribution. The stored tier review batch is not used.
No climate-shape follow-up for issues 112, 113, or 114. The hexbin is not a UI candidate. The named correlation block is a feature-reduction note for a later issue 114 design. This run does not refit PCA. It is not an issue 112 or 113 input. An aggregate correlation view is a UI candidate. Issue 112, which is not authorized, is the only place a within-January temperature path would be followed up, as a climate series rather than a human case panel. State means are not an issue 113 neighbor model. A state-by-day aggregate with no county names is a UI candidate. Feature contribution stops until a later story has an approved held-out evaluation. PCA loadings are not importance. No UI work is in this story.

County-mean January average temperature on the #107 decimal parse: n=3109, mean -1.412, median -2.159. County-mean January precipitation: n=3109, mean 1.459, median 1.171. #114 Spearman of SVI and log population is 0.1334 (interval 0.0155 to 0.2555). #114 Spearman of log population and RUCC is -0.7596. #114 three-feature two-component share is 0.8847 against the 13 October target 0.8850. #109 headlines on this pin remain 3144 counties, 651 published floors, and 2493 counties with no county-linked record. #116 state-cluster intervals are cited there and are not refit. No 13 October hexbin or county-by-time figure is in the repository.

4. Caveats

Counts are surveillance signals. A published human floor is a lower bound (CDC floor 5), not incidence or risk. No records and Unknown are not negatives. Missing is not zero. Human surveillance is calendar 2023. Tick and pathogen statuses are cumulative through 2025-12-31. Context fields are 2022 or 2023. Climate is January 2025 only. Those vintages are not one time base. Historical CDC objects were not read. Issue 112 was not run. State means are not a neighbor model, so they are not an issue 113 result. No p-value is reported. County names are not drawn on charts.

5. Disposition: keep / revise / stop, plus go/no-go and a plain recommendation

Disposition: keep.

Go, for analyst citation of the displays whose usefulness flag is true. Do not promote a model and do not treat a chart as disease risk. No climate-shape follow-up for issues 112, 113, or 114. The hexbin is not a UI candidate. The named correlation block is a feature-reduction note for a later issue 114 design. This run does not refit PCA. It is not an issue 112 or 113 input. An aggregate correlation view is a UI candidate. Issue 112, which is not authorized, is the only place a within-January temperature path would be followed up, as a climate series rather than a human case panel. State means are not an issue 113 neighbor model. A state-by-day aggregate with no county names is a UI candidate. Feature contribution stops until a later story has an approved held-out evaluation. PCA loadings are not importance. No UI work is in this story.

6. Artifacts

run_id: 117-visual-diagnostics-20261026T0954Z
Snowflake row counts: REGISTRY.RUNS=1, EDA.METRICS_LONG=1561, EDA.CORRELATIONS=30, EDA.MISSINGNESS=10, EDA.FINDINGS=5, REGISTRY.QUERIES=5, EXPERIMENTS.EXPERIMENTS=0
No new table was created, so SELECT was not granted to OH_LYME_PROD_READ.
REGISTRY.ARTIFACTS for run 114-cross-domain-20261026T0822Z has 3 chart rows registered from the ML Lead's Drive ids. Those Drive files were not changed.
REGISTRY.ARTIFACTS for run 117-visual-diagnostics-20261026T0954Z has 3 chart rows. Drive size matched local bytes on the first upload of each file.
Drive folder: https://drive.google.com/drive/folders/1x9Kum3fN0X9ipkSOSs8_tEKgcOswUkI1
climate-hexbin.png: https://drive.google.com/file/d/1oXA0TjWcmCz0FgMojew8cUqByekEv8nK/view?usp=drivesdk (5562 bytes, sha256 67a3b77c755bec947bbf332da99db718ed5d0300689aa0c507874d579256f877)
correlation-heatmap.png: https://drive.google.com/file/d/1IPfP4sj1GRApnrCPBcxQnRcl4bGMfBBK/view?usp=drivesdk (6819 bytes, sha256 f5c69ded603b523069eef17c6e3c7a73892639859ceaa3c83fc20450fd242999)
state-day-temperature.png: https://drive.google.com/file/d/1tKWHaozotyieQvdy7V_WRnWLWyF5-V8G/view?usp=drivesdk (5566 bytes, sha256 9bbd582c05424fa44044a9d3700a8e3af5dde8281fc2b1aaf04588050108a831)
Doc: docs/eda/117-visual-diagnostics.md
Spec: docs/eda/117-analysis-spec.md

7. Reproducibility

Commit: 61bcdf6ad3e333225d4b75501473c8a1b953a034
Release: governed-2026-10-15-january-climate-prod
Seed: 1172026, recorded and unused. Linkage and hex rounding are deterministic.
Commands:
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_117_visual_diagnostics.py
uv run python scripts/verify.py

County-level climate means stayed in memory. They were not written to git or Drive.


Spot checks chosen by smallest FIPS, not by the chart:

- published_floor: Baldwin County, AL, FIPS 01003, human published_count_floor, tick Established, pathogen No records, eligible January average-temperature days 31, precipitation days 31.
- no_county_record: Autauga County, AL, FIPS 01001, human no_county_linked_record, tick Established, pathogen No records, eligible January average-temperature days 31, precipitation days 31.
- outside_tick_scope: Aleutians East Borough, AK, FIPS 02013, human no_county_linked_record, tick Unknown, pathogen Unknown, eligible January average-temperature days none, precipitation days none.

## Decision

**KEEP** for quoting the panel as a display that beats a table or a one-month map. This is not permission to train a model or build a UI.

## Reproduction and retained evidence

- Code revision/run: `61bcdf6ad3e333225d4b75501473c8a1b953a034`. Run `117-visual-diagnostics-20261026T0954Z`. Spec `117-visual-diagnostics/v1`.
- Entry points: `sql/validation/117_visual_diagnostics.sql`, `scripts/eda_117_visual_diagnostics.py`, `src/lyme_gap_atlas_ml/visual_diagnostics.py`.
- Commands: `uv run python scripts/check_ml_agent_context.py`, then `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_117_visual_diagnostics.py`, then `uv run python scripts/verify.py`.
- Lab row counts: `REGISTRY.RUNS` 1, `EDA.METRICS_LONG` 1561, `EDA.CORRELATIONS` 30, `EDA.MISSINGNESS` 10, `EDA.FINDINGS` 5, `REGISTRY.QUERIES` 5, `EXPERIMENTS.EXPERIMENTS` 0.
- Transient artifacts not committed: county rows, chart PNGs under `artifacts/charts/117/`, and `outputs/117-run-id.txt`.
