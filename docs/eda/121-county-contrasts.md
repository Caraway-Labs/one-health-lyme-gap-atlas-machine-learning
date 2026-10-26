# 121: Which contrasts separate counties?

- Issue: [#121](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/121); parent epic [#118](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/118);
  program epic [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.
  Release `governed-2026-10-15-january-climate-prod`.
- Cohort: 3144 counties, one snapshot.
  Published human floor 651.
  No county-linked human record 2493.

## Method and assumptions

Spec [121-county-contrasts/v1](121-analysis-spec.md), frozen before the axes were interpreted.
The fit is multiple correspondence analysis with the Greenacre inertia adjustment.
Bin edges, the rare-category rule, the seed, and the one-edge stability rule
are in the spec. #109 defines the statuses.
#114 defines the documentation reading and the SVI unit rule.
#123 state groups are not features here.

## Material findings and limits

Category frequencies before the MCA bins, levels with a positive count:

| Variable | Level | Counties |
| --- | --- | ---: |
| rucc | 1 | 443 |
| rucc | 2 | 385 |
| rucc | 3 | 358 |
| rucc | 4 | 201 |
| rucc | 5 | 76 |
| rucc | 6 | 379 |
| rucc | 7 | 247 |
| rucc | 8 | 466 |
| rucc | 9 | 589 |
| human_status | no_county_linked_record | 2493 |
| human_status | published_count_floor | 651 |
| scapularis_status | Established | 1307 |
| scapularis_status | No records | 1327 |
| scapularis_status | Reported | 475 |
| scapularis_status | Unknown | 35 |
| pacificus_status | Established | 97 |
| pacificus_status | No records | 2997 |
| pacificus_status | Reported | 15 |
| pacificus_status | Unknown | 35 |
| burgdorferi_status | No records | 2420 |
| burgdorferi_status | Present | 689 |
| burgdorferi_status | Unknown | 35 |
| tick_status | Established | 1404 |
| tick_status | No records | 1215 |
| tick_status | Reported | 490 |
| tick_status | Unknown | 35 |
| population | under_10k | 735 |
| population | 10k_to_25k | 805 |
| population | 25k_to_50k | 608 |
| population | 50k_to_100k | 390 |
| population | 100k_to_250k | 327 |
| population | 250k_to_500k | 137 |
| population | 500k_to_1m | 95 |
| population | 1m_or_more | 47 |
| svi_percentile | through_0.1 | 315 |
| svi_percentile | through_0.2 | 314 |
| svi_percentile | through_0.3 | 315 |
| svi_percentile | through_0.4 | 314 |
| svi_percentile | through_0.5 | 314 |
| svi_percentile | through_0.6 | 314 |
| svi_percentile | through_0.7 | 315 |
| svi_percentile | through_0.8 | 314 |
| svi_percentile | through_0.9 | 314 |
| svi_percentile | through_1.0 | 315 |

1. Question

Which two or three contrasts explain most of the categorical difference among counties,
and where do the aligned counties and the double-gap counties sit on that map?
Is the picture stable if one population bin edge moves?

2. Method (and why; link the spec)

Multiple correspondence analysis on seven categorical variables:
social-vulnerability quartile, population band, rural-urban code, human status,
blacklegged-tick status, western-blacklegged-tick status, and pathogen status.
Status definitions are the #109 levels. The attributes are surveillance documentation,
the #114 reading, not incidence. #123 state reporting groups are not inputs.
Spec [121-county-contrasts/v1](docs/eda/121-analysis-spec.md), frozen before any axis was named.
Headline inertia is the Greenacre adjustment. Rare categories stay in the fit.
The sensitivity moves only the population edge at 50 thousand to 100 thousand.
Axes are an exploratory exhibit, not features for another model,
and the map is not a risk surface.

3. Key findings with numbers

Greenacre-adjusted shares: axis 1 0.4406, axis 2 0.2494, axis 3 0.0403.

Axis 1 contrasts unknown pathogen status and unknown western-blacklegged-tick status with a published human floor. Unknown blacklegged-tick status has the same axis-1 contribution, 0.2932, and the same 35 counties, so axis 1 is one unknown-status block. Axis 2 contrasts a published human floor and a published pathogen record with no blacklegged-tick record. Axis 3 contrasts counties under 10 thousand people with counties from 10 thousand to under 50 thousand people.

The five epic situation counts match the October references.

- Aligned reference: 443 counties, matches the reference 443. Centroid on axes 1 and 2: (-0.3748, 1.0102).
- Double gap: 228 counties, matches the reference 228. Centroid on axes 1 and 2: (-0.1994, 0.4375).
- Wider established-tick gap: 810 counties, matches the reference 810. Centroid on axes 1 and 2: (-0.1133, 0.1179).
- Published floor, no pathogen record: 207 counties, matches the reference 207. Centroid on axes 1 and 2: (-0.2516, 0.5076).
- No human, tick, or pathogen documentation: 1189 counties, matches the reference 1189. Centroid on axes 1 and 2: (0.0832, -0.4708).

Counties outside those five situations: 495.
The double-gap counties are inside the wider gap,
so those two centroids are not two disjoint clouds.
Aligned versus double-gap separation ratio: 2.3958.

Sensitivity: Spearman axis 1 0.9973, axis 2 0.9913, axis 3 0.9816; Procrustes similarity 0.9996 on 22 shared categories; the stability gate passes. Rare leaders on axis 1 or axis 2: none.

4. Caveats

Counts are surveillance signals and lower bounds where a human floor is published.
`No records` and `Unknown` are not negatives. A missing floor is not zero.
Counties in one state share reporting rules, so there is no county-independent interval.
The human year, the 2022 context layer, and the tick and pathogen window through 2025
are not one time base. A rare category can still pull an axis;
that case is a revise rule, not a hidden drop.
The hex map suppresses cells below 11 and does not draw county points.

5. Disposition

Method: keep. Product: advance.
keep is the method call for the MCA exhibit.
advance is the product call.
Neither publishes a score or sends these axes into another model.

6. Artifacts

- run_id `121-county-contrasts-20261026T1251Z`
- Snowflake: `REGISTRY.RUNS`, `EDA.METRICS_LONG`, `EDA.FINDINGS`,
  `EDA.COUNTY_MCA_COORDINATES_121`, `EXPERIMENTS.EXPERIMENTS`,
  `EXPERIMENTS.MODEL_METRICS`, `REGISTRY.QUERIES`, `REGISTRY.ARTIFACTS`
- Coordinates stay in `EDA.COUNTY_MCA_COORDINATES_121` only.
  They are not in git or Drive.
  `SELECT` on that table is granted to `OH_LYME_PROD_READ`.
- Drive folder: https://drive.google.com/drive/folders/1z4w6DbAhcYff7n03Czfp3CX-J2kZvlKu
- `greenacre-scree.png` size-matched and registered.
  Drive file `1o-PvzQa_6vMEJSggUKxt-Igog1XZL74M`,
  https://drive.google.com/file/d/1o-PvzQa_6vMEJSggUKxt-Igog1XZL74M/view?usp=drivesdk,
  bytes 6319, sha256 `b3714690188968278de9094c74bbb736d40a880240d739a19d85910265604022`.
- Missing after two size mismatches, both Drive copies trashed:
  `category-pulls.png`, local bytes 20955,
  sha256 `84125b06a3d1578f8895f7cf0befd073c4bdd2255b09241bf3d76d50d3348573`.
- Missing after two size mismatches, both Drive copies trashed:
  `axis-map.png`, local bytes 16847,
  sha256 `b3a7f294841389c5df7c23685554830bb48d1b0fdcf600543d10d835cd08c873`.
- Doc: `docs/eda/121-county-contrasts.md`
- #123 chart registration for run `123-state-reporting-regimes-20261026T1159Z`:
  three `REGISTRY.ARTIFACTS` rows (`descriptive-dendrogram.png`,
  `publication-free-dendrogram.png`, `group-contingency.png`).
  This story did not upload or edit those Drive files.

7. Reproducibility

- Commit: `5536a7e1c07dc45245ea68538af07079f1231f33`
- Release: `governed-2026-10-15-january-climate-prod`
- Bundle: `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`
- Seed: `1212026`, recorded and not consumed by the singular-value decomposition
- SVI scaled by 100: False

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_121_county_mca.py
uv run python scripts/verify.py
```


## Decision

Method **keep**. Product **advance**.
The axes stay an exploratory exhibit.
They are not a production score and not a risk surface.

## Reproduction and retained evidence

- Run `121-county-contrasts-20261026T1251Z`. Commit `5536a7e1c07dc45245ea68538af07079f1231f33`. Seed `1212026`.
- Lab row counts: `REGISTRY.RUNS` 1, `EDA.METRICS_LONG` 165, `EDA.FINDINGS` 4, `EDA.COUNTY_MCA_COORDINATES_121` 3144, `EXPERIMENTS.EXPERIMENTS` 2, `EXPERIMENTS.MODEL_METRICS` 8, `REGISTRY.QUERIES` 3, `REGISTRY.ARTIFACTS` 1.
- Entry points: `sql/validation/121_county_mca.sql`,
  `scripts/eda_121_county_mca.py`, `src/lyme_gap_atlas_ml/county_mca.py`.
- Commands:

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_121_county_mca.py
uv run python scripts/verify.py
```

- Transient artifacts not committed: county coordinate rows, hex-cell arrays,
  and PNGs under `artifacts/charts/121/`.
  Coordinates that were persisted stay in `EDA.COUNTY_MCA_COORDINATES_121` only.
