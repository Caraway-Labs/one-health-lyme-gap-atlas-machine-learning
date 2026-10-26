# 107: What is typical, how variable, and are the tier boundaries interpretable?

- Issue: [ML #107](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/107), part of [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_TIER1_COUNTY_REVIEW_V`, `CURRENT_RELEASE_V`, `CURRENT_SOURCE_METADATA_V`, climate county-day values, and an NLCD county count. Pinned atlas release `governed-2026-10-15-january-climate-prod`. Tier batch release `governed-2026-09-18-unknown-coverage`.
- Cohort: 3144 counties, 3144 distinct FIPS. Published human floors: 651. No county-linked human record: 2493.

## Method and assumptions

Spec [107-county-distributions/v1](107-analysis-spec.md), frozen before execution. The finite county set is the denominator. People are the weight in the population-weighted summaries. Seed `1072026` is unused. Outlier flags are not deletions.

## Material findings and limits

Atlas counties: 3144. Published floors: 651 (October 13 reference 651). No county-linked record: 2493 (reference 2493).

Published case floor: n=651, mean 134.4, population-weighted mean 263.5, median 49, mode 5, modal bin [100, 250), IQR 133.5, variance 6.168e+04, SD 248.4, skewness 5.339. IQR flags low/high 0/63. MAD flags low/high 0/87 (estimable: yes).
Published incidence floor per 100,000: n=651, mean 139.2, population-weighted mean 55.12, median 80.88, mode not estimable, modal bin [200, 500), IQR 184.4, variance 2.796e+04, SD 167.2, skewness 2.735. IQR flags low/high 0/30. MAD flags low/high 0/37 (estimable: yes).
Population: n=3144, mean 1.053e+05, population-weighted mean 1.163e+06, median 2.578e+04, mode not estimable, modal bin [10000, 25000), IQR 5.724e+04, variance 1.114e+11, SD 3.338e+05, skewness 13.18. IQR flags low/high 0/440. MAD flags low/high 0/516 (estimable: yes).
SVI percentile: n=3144, mean 0.5, population-weighted mean 0.5836, median 0.5, mode 0.3312, modal bin [0, 0.1), IQR 0.4999, variance 0.08341, SD 0.2888, skewness 2.386e-05. IQR flags low/high 0/0. MAD flags low/high 0/0 (estimable: yes).

Published case floors equal to 5: 46. Incidence histogram peaks: 2. SVI rescaled from a 0–100 column: no. Uninsured rescaled: no.

States with no published county floor: 19 (1437 counties, 1437 null floors). Null floors in states that publish at least one floor: 1056.

Right-tail review candidates on the published incidence floor (scaled MAD above 3.5). These are surveillance review candidates, not disease findings.
- Dukes County, MA: incidence floor 1640, robust z 15.28.
- Nantucket County, MA: incidence floor 1315, robust z 12.09.
- Cameron County, PA: incidence floor 815.7, robust z 7.20.
- Jefferson County, PA: incidence floor 735.5, robust z 6.41.
- Washington County, RI: incidence floor 733.9, robust z 6.40.
- Tucker County, WV: incidence floor 726.2, robust z 6.32.
- Knox County, ME: incidence floor 687.5, robust z 5.94.
- Webster County, WV: incidence floor 669.7, robust z 5.77.

Stored tiers: HIGH 315 (reference 315), MEDIUM 628 (reference 628), LOW 2201 (reference 2201). SUFFICIENT 651 (reference 651). INSUFFICIENT 2493 (reference 2493). INSUFFICIENT is not reported as LOW.
Percentile column rescaled from a 0–1 fraction: no. Stored tier versus the 70/90 rule: 0 disagreements.
Absolute scores implied by this batch: HIGH raw score min/median/max 1.647/1.855/2.54; MEDIUM raw score min/median/max 0.9701/1.21/1.647; LOW raw score min/median/max 0.4431/0.6341/0.9696.
Sufficiency by stored tier: INSUFFICIENT/LOW 2201, INSUFFICIENT/MEDIUM 292, SUFFICIENT/HIGH 315, SUFFICIENT/MEDIUM 336.
Human-evidence labels on the tier view: no_county_linked_record, published_count_floor. Rows whose sufficiency or human-evidence label does not match the current atlas human status: 0.
HIGH share by Census region is in `EDA.METRICS_LONG` (`high_share`). A 1–10 cell is suppressed there.

Eligible climate county-day values on the corrected run: 385,516 (96,379 days for each of four measures). Decimal and integer payloads were parsed from VALUE inside Snowflake. The native-double-only climate metrics on `107-county-distributions-20261026T0404Z` are not this estimand. The exact day-level mode is not estimable from the aggregate. Modal bins are the `histogram_count` metrics.
Daily precipitation, mm, including zero days: n=96379, mean 1.459, median 0, IQR 0.222, variance 26.98, SD 5.194, skewness 6.649. IQR flags low/high 0/20482. MAD is not estimable because the median absolute deviation is 0.
Daily average temperature, degrees Celsius: n=96379, mean -1.412, median -1.292, IQR 10.34, variance 60.82, SD 7.798, skewness -0.142. IQR flags low/high 682/234. MAD flags low/high 32/0 (estimable: yes).
Daily maximum temperature: n=96379, mean 4.209, median 3.813, IQR 12.11, variance 72.49, SD 8.514, skewness -0.024. IQR flags low/high 329/23. MAD flags low/high 0/0.
Daily minimum temperature: n=96379, mean -7.034, median -6.472, IQR 9.445, variance 57.64, SD 7.592, skewness -0.235. IQR flags low/high 1130/586. MAD flags low/high 169/23 (estimable: yes).
County-mean precipitation: n=3109, mean 1.459, population-weighted mean 1.332, median 1.171, IQR 1.701, SD 1.212, skewness 0.985. IQR flags low/high 0/46. MAD high flags are suppressed (1–10).
County-mean average temperature: n=3109, mean -1.412, population-weighted mean 1.590, median -2.159, IQR 8.960, SD 5.920, skewness 0.297. IQR low flags 0. IQR high flags are suppressed (1–10). MAD flags low/high 0/0.
County-mean maximum temperature: n=3109, mean 4.209, population-weighted mean 6.943, median 3.316, IQR 10.14, SD 6.361, skewness 0.306. IQR flags low/high 0/0. MAD flags low/high 0/0.
County-mean minimum temperature: n=3109, mean -7.034, population-weighted mean -3.763, median -7.498, IQR 7.868, SD 5.627, skewness 0.255. IQR low flags 0. IQR high and MAD high flags are suppressed (1–10).

NLCD counties on this release: 2. That is not a national land-cover distribution.

## Decision

**KEEP.** The October 15 atlas still has 3,144 counties, 651 published floors, and 2,493 counties with no county-linked record. The September tier batch still stores HIGH 315, MEDIUM 628, LOW 2,201, SUFFICIENT 651, and INSUFFICIENT 2,493.

Show the stored HIGH, MEDIUM, and LOW labels as a relative review order on this September score batch, and always show SUFFICIENT or INSUFFICIENT beside the tier. Do not read LOW as a low disease burden, and do not read a high published floor as a confirmed outbreak. The published numbers are 2023 surveillance floors, they start at 5, and a county with no county-linked record is unpublished, not a zero. The tier view is an older batch than the October 15 atlas, so the product should not describe it as a score on the current atlas.

## Reproduction and retained evidence

- Code revision/run: `bb1daa719fe25acf087cdd618d84a64024cea9af`. Atlas rows were inserted at `35215fab1c2fe86af08dcdb8103ea37c0f4b3d54`. Decimal climate parsing is `b763e369558b224fbcfdee6a7d21a98814d20080`. Run `107-county-distributions-20261026T0404Z`. Corrected climate run `107-climate-decimal-20261026T0529Z`. Spec `107-county-distributions/v1`.
- Entry points: `sql/validation/107_county_distributions.sql`, `scripts/eda_107_distributions.py`, `src/lyme_gap_atlas_ml/county_distributions.py`.
- Commands: `uv run python scripts/check_ml_agent_context.py`, then `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_107_distributions.py`, then `uv run python scripts/verify.py`.
- Atlas lab row counts: `REGISTRY.RUNS` 1, `EDA.METRICS_LONG` 3287, `EDA.COLUMN_PROFILES` 8, `EDA.FINDINGS` 3, `REGISTRY.QUERIES` 8, `EDA.COUNTY_ADJACENCY_107` 0, `REGISTRY.ARTIFACTS` 4. Climate metrics and the three extra column profiles on this run used `VALUE_NATIVE_DOUBLE` only and are not the climate estimand.
- Corrected climate lab row counts: `EDA.METRICS_LONG` 372, `EDA.COLUMN_PROFILES` 4, `EDA.FINDINGS` 1, `REGISTRY.QUERIES` 2.
- Adjacency: skipped: the spatial join did not finish inside the warehouse limit.
- Drive folder: https://drive.google.com/drive/folders/15jPUUby1jUNeSMVEc4T3g2f-rku5TGK-. `floor-ecdf.png` https://drive.google.com/file/d/1wzMMTjJd7V2DKlrXLw_C5ELGf3E5KVR6/view (3910 bytes). `incidence-by-rucc.png` https://drive.google.com/file/d/1X_1ZSHX5u6Sjc5dtg3UsJDmiNZGwHXyM/view (9276 bytes). `incidence-histogram.png` https://drive.google.com/file/d/14jDMuWb19TwNJaqmJqMmYIdagc3R0u2I/view (3389 bytes). `tavg-histogram.png` https://drive.google.com/file/d/1vSV_YVn3dAA4JMGAcn8hGoFCHj-Ojd_D/view (3498 bytes). Each Drive file size matches the local PNG. `floor-ecdf.png`, `incidence-histogram.png`, and `tavg-histogram.png` are 64-color copies of the same figures.
- Transient artifacts intentionally not committed: PNG files under `artifacts/charts/107/`, `outputs/107-run-id.txt`, and in-memory county rows. No county extract was committed.

## 1. Question

What is typical and what is unusual in each county signal, how variable is it, and are the HIGH / MEDIUM / LOW tier boundaries interpretable?

## 2. Method

Spec [107-county-distributions/v1](docs/eda/107-analysis-spec.md), frozen before the distribution queries. Exact statistics use the raw values. Histogram bins use the fixed edges in the spec. Climate day summaries are aggregated in Snowflake. County-mean climate is summarized from those county averages. Unweighted summaries give each county one weight. Population-weighted summaries give each person one weight. The county set is the governed release, not a sample, so there is no standard error and no hypothesis test. Seed 1072026 is recorded and unused. IQR fences and scaled-MAD flags are review candidates. INSUFFICIENT evidence is counted on its own and is not called LOW.

## 3. Key findings

Atlas counties: 3144. Published floors: 651 (October 13 reference 651). No county-linked record: 2493 (reference 2493).

Published case floor: n=651, mean 134.4, population-weighted mean 263.5, median 49, mode 5, modal bin [100, 250), IQR 133.5, variance 6.168e+04, SD 248.4, skewness 5.339. IQR flags low/high 0/63. MAD flags low/high 0/87 (estimable: yes).
Published incidence floor per 100,000: n=651, mean 139.2, population-weighted mean 55.12, median 80.88, mode not estimable, modal bin [200, 500), IQR 184.4, variance 2.796e+04, SD 167.2, skewness 2.735. IQR flags low/high 0/30. MAD flags low/high 0/37 (estimable: yes).
Population: n=3144, mean 1.053e+05, population-weighted mean 1.163e+06, median 2.578e+04, mode not estimable, modal bin [10000, 25000), IQR 5.724e+04, variance 1.114e+11, SD 3.338e+05, skewness 13.18. IQR flags low/high 0/440. MAD flags low/high 0/516 (estimable: yes).
SVI percentile: n=3144, mean 0.5, population-weighted mean 0.5836, median 0.5, mode 0.3312, modal bin [0, 0.1), IQR 0.4999, variance 0.08341, SD 0.2888, skewness 2.386e-05. IQR flags low/high 0/0. MAD flags low/high 0/0 (estimable: yes).

Published case floors equal to 5: 46. Incidence histogram peaks: 2. SVI rescaled from a 0–100 column: no. Uninsured rescaled: no.

States with no published county floor: 19 (1437 counties, 1437 null floors). Null floors in states that publish at least one floor: 1056.

Right-tail review candidates on the published incidence floor (scaled MAD above 3.5). These are surveillance review candidates, not disease findings.
- Dukes County, MA: incidence floor 1640, robust z 15.28.
- Nantucket County, MA: incidence floor 1315, robust z 12.09.
- Cameron County, PA: incidence floor 815.7, robust z 7.20.
- Jefferson County, PA: incidence floor 735.5, robust z 6.41.
- Washington County, RI: incidence floor 733.9, robust z 6.40.
- Tucker County, WV: incidence floor 726.2, robust z 6.32.
- Knox County, ME: incidence floor 687.5, robust z 5.94.
- Webster County, WV: incidence floor 669.7, robust z 5.77.

Stored tiers: HIGH 315 (reference 315), MEDIUM 628 (reference 628), LOW 2201 (reference 2201). SUFFICIENT 651 (reference 651). INSUFFICIENT 2493 (reference 2493). INSUFFICIENT is not reported as LOW.
Percentile column rescaled from a 0–1 fraction: no. Stored tier versus the 70/90 rule: 0 disagreements.
Absolute scores implied by this batch: HIGH raw score min/median/max 1.647/1.855/2.54; MEDIUM raw score min/median/max 0.9701/1.21/1.647; LOW raw score min/median/max 0.4431/0.6341/0.9696.
Sufficiency by stored tier: INSUFFICIENT/LOW 2201, INSUFFICIENT/MEDIUM 292, SUFFICIENT/HIGH 315, SUFFICIENT/MEDIUM 336.
Human-evidence labels on the tier view: no_county_linked_record, published_count_floor. Rows whose sufficiency or human-evidence label does not match the current atlas human status: 0.
HIGH share by Census region is in `EDA.METRICS_LONG` (`high_share`). A 1–10 cell is suppressed there.

Eligible climate county-day values on the corrected run: 385,516 (96,379 days for each of four measures). Decimal and integer payloads were parsed from VALUE inside Snowflake. The native-double-only climate metrics on `107-county-distributions-20261026T0404Z` are not this estimand. The exact day-level mode is not estimable from the aggregate. Modal bins are the `histogram_count` metrics.
Daily precipitation, mm, including zero days: n=96379, mean 1.459, median 0, IQR 0.222, variance 26.98, SD 5.194, skewness 6.649. IQR flags low/high 0/20482. MAD is not estimable because the median absolute deviation is 0.
Daily average temperature, degrees Celsius: n=96379, mean -1.412, median -1.292, IQR 10.34, variance 60.82, SD 7.798, skewness -0.142. IQR flags low/high 682/234. MAD flags low/high 32/0 (estimable: yes).
Daily maximum temperature: n=96379, mean 4.209, median 3.813, IQR 12.11, variance 72.49, SD 8.514, skewness -0.024. IQR flags low/high 329/23. MAD flags low/high 0/0.
Daily minimum temperature: n=96379, mean -7.034, median -6.472, IQR 9.445, variance 57.64, SD 7.592, skewness -0.235. IQR flags low/high 1130/586. MAD flags low/high 169/23 (estimable: yes).
County-mean precipitation: n=3109, mean 1.459, population-weighted mean 1.332, median 1.171, IQR 1.701, SD 1.212, skewness 0.985. IQR flags low/high 0/46. MAD high flags are suppressed (1–10).
County-mean average temperature: n=3109, mean -1.412, population-weighted mean 1.590, median -2.159, IQR 8.960, SD 5.920, skewness 0.297. IQR low flags 0. IQR high flags are suppressed (1–10). MAD flags low/high 0/0.
County-mean maximum temperature: n=3109, mean 4.209, population-weighted mean 6.943, median 3.316, IQR 10.14, SD 6.361, skewness 0.306. IQR flags low/high 0/0. MAD flags low/high 0/0.
County-mean minimum temperature: n=3109, mean -7.034, population-weighted mean -3.763, median -7.498, IQR 7.868, SD 5.627, skewness 0.255. IQR low flags 0. IQR high and MAD high flags are suppressed (1–10).

NLCD counties on this release: 2. That is not a national land-cover distribution.

## 4. Caveats

Human floors are calendar 2023 surveillance lower bounds (CDC floor 5). They are not incidence, risk, or causation. Population, SVI, and uninsured context are 2022. RUCC is 2023. Tick and pathogen statuses are cumulative through 2025-12-31. Climate, when read, is the stored county-day window, not a multi-year series. The tier view is release `governed-2026-09-18-unknown-coverage`, model `tier1-statistical-reference-v1`, policy `tier1-review-percentile-v1`. It is not a score computed on the October 15 atlas. Neighboring counties are dependent. Adjacency does not adjust these summaries. NLCD covers two counties and is not a national distribution. A missing human floor is not zero. No records and Unknown are not negatives.

## 5. Disposition

**KEEP.** The October 15 atlas still has 3,144 counties, 651 published floors, and 2,493 counties with no county-linked record. The September tier batch still stores HIGH 315, MEDIUM 628, LOW 2,201, SUFFICIENT 651, and INSUFFICIENT 2,493.

Show the stored HIGH, MEDIUM, and LOW labels as a relative review order on this September score batch, and always show SUFFICIENT or INSUFFICIENT beside the tier. Do not read LOW as a low disease burden, and do not read a high published floor as a confirmed outbreak. The published numbers are 2023 surveillance floors, they start at 5, and a county with no county-linked record is unpublished, not a zero. The tier view is an older batch than the October 15 atlas, so the product should not describe it as a score on the current atlas.

## 6. Artifacts

- Run id: `107-county-distributions-20261026T0404Z`
- Corrected climate run: `107-climate-decimal-20261026T0529Z`
- Snowflake, ML Lab only, atlas run:
- `REGISTRY.RUNS` 1
- `EDA.METRICS_LONG` 3287
- `EDA.COLUMN_PROFILES` 8
- `EDA.FINDINGS` 3
- `REGISTRY.QUERIES` 8
- `EDA.COUNTY_ADJACENCY_107` 0
- `REGISTRY.ARTIFACTS` 4
- Climate metrics and the three extra column profiles on the atlas run used `VALUE_NATIVE_DOUBLE` only and are not the climate estimand.
- Corrected climate run: `EDA.METRICS_LONG` 372, `EDA.COLUMN_PROFILES` 4, `EDA.FINDINGS` 1, `REGISTRY.QUERIES` 2
- Adjacency: skipped: the spatial join did not finish inside the warehouse limit
- Drive folder: https://drive.google.com/drive/folders/15jPUUby1jUNeSMVEc4T3g2f-rku5TGK-
- `floor-ecdf.png` https://drive.google.com/file/d/1wzMMTjJd7V2DKlrXLw_C5ELGf3E5KVR6/view (3910 bytes)
- `incidence-by-rucc.png` https://drive.google.com/file/d/1X_1ZSHX5u6Sjc5dtg3UsJDmiNZGwHXyM/view (9276 bytes)
- `incidence-histogram.png` https://drive.google.com/file/d/14jDMuWb19TwNJaqmJqMmYIdagc3R0u2I/view (3389 bytes)
- `tavg-histogram.png` https://drive.google.com/file/d/1vSV_YVn3dAA4JMGAcn8hGoFCHj-Ojd_D/view (3498 bytes)
- Doc: `docs/eda/107-county-distributions.md`

## 7. Reproducibility

- Commit: `bb1daa719fe25acf087cdd618d84a64024cea9af`
- Release: `governed-2026-10-15-january-climate-prod`
- Tier batch release: `governed-2026-09-18-unknown-coverage`
- Seed: `1072026`
- Commands:

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_107_distributions.py
uv run python scripts/verify.py
```
