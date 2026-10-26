# 113: Where do neighboring counties diverge beyond expected measurement and coverage variability?

- Issue: [ML #113](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/113), part of [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`,
  `CURRENT_SOURCE_METADATA_V`, and `CURRENT_MEASURE_METADATA_V`.
  Pinned release `governed-2026-10-15-january-climate-prod`.
- Cohort: 3144 counties. Published floors: 651.
  No county-linked human record: 2493.

## Method and assumptions

Spec [113-spatial-neighbor-outliers/v1](113-analysis-spec.md), frozen before the contrast. Neighbor weights are not on the allow-list, so Moran's I and LISA were not estimated. The within-state robust z reuses the #106 size bands for the published incidence floor only.

## Material findings and limits

Atlas counties: 3144. Published floors: 651. No county-linked record: 2493.
Published incidence floor: n=651, median 80.88, MAD 68.84. The national scaled-MAD counts match #107 (high 37, low 0).
States with no published county floor match #107 (19 states, 1437 counties).
Peer bands: state_native 8 states and 455 published counties, shrunk 4 states and 77 published counties, below_band 20 states and 119 published counties.
Within-state high divergence: 25. Low divergence, case floor above 5: 0. Low z on a case floor of 5 (floor heaps, not divergence flags): 0. Case floors below 5: 0. States whose scale is not estimable: 0.
Between-state share of squares: 0.3405. One-sided permutation tail: 0.0005. Holm 0.0005. BH 0.0005. Draws 2000, seed 1132026.
Adjacency sources on the allow-list: 0. Lab adjacency edges: 0. Neighbor residuals, Moran's I, and LISA: not estimable.
#106 reported 113 state-relative context flags (Jaccard with its national screen 0.025). Those flags are log population, SVI, uninsured percentile, and rural-urban code. They are not incidence-floor neighbor outliers and were not refit. #122 is the established-tick class screen and is not a weights source.

## Decision

**Method: stop** for neighbor contrasts, Moran's I, and LISA on this release. **Method: keep** for the within-state published-incidence contrast. **Product: investigate.** The neighbor screen needs a governed adjacency table of undirected FIPS pairs (`FIPS_A`, `FIPS_B`, `FIPS_A < FIPS_B`, `RELEASE_ID`) and no geometry text. This run does not create that table. Keep, where it applies, is permission to show state-peer review candidates beside the #106 context flags. It is not a public score and not a change to the Tier 1 model.

## Reproduction and retained evidence

- Code revision at the contrast: `431083487ba14affb4ff87f797217bd63138cb0e`.
- Entry points: `sql/validation/113_spatial_neighbors.sql`,
  `scripts/eda_113_spatial_neighbors.py`,
  `src/lyme_gap_atlas_ml/spatial_neighbors.py`.
- Commands: `uv run python scripts/check_ml_agent_context.py`, then
  `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_113_spatial_neighbors.py`, then `uv run python scripts/verify.py`.
- Transient artifacts intentionally not committed: PNG files under
  `artifacts/charts/113/` and in-memory county rows.
  No county extract was committed.

## 1. Question

Where do neighboring counties diverge beyond expected measurement and coverage variability?

## 2. Method

Spec [113-spatial-neighbor-outliers/v1](docs/eda/113-analysis-spec.md), frozen before the contrast. The allow-listed catalog has no adjacency, centroid, latitude, longitude, or neighbor column. `EDA.COUNTY_ADJACENCY_107` has 0 rows. Geometry text was not read. Neighbor residuals, Moran's I, and LISA are implemented for a supplied FIPS-pair list and tested on fake edges. They were not run on live counties. The live contrast is the within-state robust z of the published incidence floor, using the #106 size bands and `shrunk_mad`. A case floor of 5 with a low z is a CDC floor heap, not a divergence flag. Missing floors stay missing. Eta-squared uses 2,000 permutations of published incidence values, seed 1132026, with Holm and BH on that one-test family. #106's 113 state-relative flags are the context-feature screen and were not refit. #107's national incidence screen is the comparison for the scaled-MAD counts.

## 3. Key findings

Atlas counties: 3144. Published floors: 651. No county-linked record: 2493.
Published incidence floor: n=651, median 80.88, MAD 68.84. The national scaled-MAD counts match #107 (high 37, low 0).
States with no published county floor match #107 (19 states, 1437 counties).
Peer bands: state_native 8 states and 455 published counties, shrunk 4 states and 77 published counties, below_band 20 states and 119 published counties.
Within-state high divergence: 25. Low divergence, case floor above 5: 0. Low z on a case floor of 5 (floor heaps, not divergence flags): 0. Case floors below 5: 0. States whose scale is not estimable: 0.
Between-state share of squares: 0.3405. One-sided permutation tail: 0.0005. Holm 0.0005. BH 0.0005. Draws 2000, seed 1132026.
Adjacency sources on the allow-list: 0. Lab adjacency edges: 0. Neighbor residuals, Moran's I, and LISA: not estimable.
#106 reported 113 state-relative context flags (Jaccard with its national screen 0.025). Those flags are log population, SVI, uninsured percentile, and rural-urban code. They are not incidence-floor neighbor outliers and were not refit. #122 is the established-tick class screen and is not a weights source.

16 states have at least 11 published floors, so the state-median chart was drawn.

High within-state divergence. 8 of 25 shown.

| County | State | FIPS | Peer | Peer n | Incidence floor | State median | Robust z | Case floor |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Highland County | VA | 51091 | state_native | 65 | 534 | 24.83 | 21.40 | 12 |
| Floyd County | VA | 51063 | state_native | 65 | 386.3 | 24.83 | 15.19 | 60 |
| Bath County | VA | 51017 | state_native | 65 | 335.2 | 24.83 | 13.04 | 14 |
| Grayson County | VA | 51077 | state_native | 65 | 280 | 24.83 | 10.72 | 43 |
| Rappahannock County | VA | 51157 | state_native | 65 | 269.5 | 24.83 | 10.28 | 20 |
| Dickinson County | MI | 26043 | state_native | 44 | 231.3 | 21.65 | 9.95 | 60 |
| Carroll County | VA | 51035 | state_native | 65 | 236.9 | 24.83 | 8.91 | 69 |
| Harrison County | OH | 39067 | state_native | 40 | 185.8 | 22.08 | 6.70 | 27 |

Low within-state divergence: none.

Within-state high flags that are also in the #107 national right-tail list: Cameron County, PA, Jefferson County, PA, Knox County, ME.

## 4. Caveats

Human floors are calendar 2023 surveillance lower bounds (CDC floor 5). They are not incidence, risk, or causation. A missing floor is not zero. No records and Unknown are not negatives. The within-state z compares a county with other published counties in the same state, including counties that do not share a border. It is not a neighbor outlier. The permutation exchanges published floors among counties that publish. It does not cover dependence that crosses a state line. Population is not a second denominator: the incidence floor is already per 100,000. #106 owns the population screen. Alaska, Hawaii, and the District of Columbia stay in the state contrast. Without an edge list they are not classified as graph islands.

## 5. Disposition

**Method: stop** for neighbor contrasts, Moran's I, and LISA on this release. **Method: keep** for the within-state published-incidence contrast. **Product: investigate.** The neighbor screen needs a governed adjacency table of undirected FIPS pairs (`FIPS_A`, `FIPS_B`, `FIPS_A < FIPS_B`, `RELEASE_ID`) and no geometry text. This run does not create that table. Keep, where it applies, is permission to show state-peer review candidates beside the #106 context flags. It is not a public score and not a change to the Tier 1 model.

## 6. Artifacts

- Run id: `113-spatial-neighbors-20261026T1104Z`
- Snowflake, ML Lab only:
- `REGISTRY.RUNS` 1
- `EDA.METRICS_LONG` 39
- `EDA.FINDINGS` 2
- `REGISTRY.QUERIES` 7
- `REGISTRY.ARTIFACTS` 1
- No new lab table was created, so no new SELECT grant was issued.
- Drive folder: https://drive.google.com/drive/folders/1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM
- state-median-incidence.png 1KOBvU7cQG57UPQj79mGk-0VsTVFituON https://drive.google.com/file/d/1KOBvU7cQG57UPQj79mGk-0VsTVFituON/view?usp=drivesdk
- Doc: `docs/eda/113-spatial-neighbor-outliers.md`

## 7. Reproducibility

- Commit at the contrast: `431083487ba14affb4ff87f797217bd63138cb0e`
- Release: `governed-2026-10-15-january-climate-prod`
- Seed: `1132026`
- State permutation draws: 2000
- Commands:

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn \
python scripts/eda_113_spatial_neighbors.py
uv run python scripts/verify.py
```
