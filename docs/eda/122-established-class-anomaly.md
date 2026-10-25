# 122: Which established-tick counties are unusual for their class?

- Issue: [ML #122](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/122), part of [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Spec: [122-established-class-anomaly/v1.1](122-analysis-spec.md).
- Data: `ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`. Pinned release `governed-2026-10-15-january-climate-prod`.
- Cohort: counties with aggregate tick status Established. Expected class size 1404. Observed class size 1404. Fit rows 1404.

## Method and assumptions

Spec [122-established-class-anomaly/v1.1](122-analysis-spec.md), frozen before the fit. Class rule: `TICK_STATUS = Established`. Features kept: log_population, svi_percentile, uninsured_percentile, rucc_2023. Dropped constant features: none. Percentile columns divided by 100: none. Population enters as a natural log. The robust z-score flags a county whose largest absolute z exceeds 3.5. The robust-covariance distance uses MinCovDet with support fraction 0.8 and the chi-square 0.975 cutoff. The isolation forest uses 200 trees, seeds 1222026 and 1222027, and contamination 0.02, 0.05, and 0.10. The primary screen is seed 1222026 at contamination 0.05. The forest adds a distinct set only when the seed Jaccard is at least 0.90 and both matched-count Jaccards are below 0.80. The dominant feature is the largest absolute robust z, labeled joint below 2.5 and tie when the top two match. Intervals are state-cluster bootstrap percentiles, 400 draws, seed 1222026.

## Material findings and limits

Epic #22 section 4.1 recorded 3144 counties, 651 with a published 2023 human floor, and 2493 with no county-linked human record. It did not record an isolation-forest flag count, so there is no October 13 flag rate to match. The same section names the 228-county established-tick / pathogen-documented / no-human-floor gap. Section 5.1 names that gap and the 810-county established-tick / no-human-floor list. This class has 1404 counties and 1404 complete feature rows. The double-gap predicate on published columns is 228, matching the epic reference 228.

Robust z flags 3 counties. Robust distance flags 81 (distance fit succeeded). Primary forest flags 71 (0.051, state-cluster interval 0.036 to 0.069). The other seed at the same contamination flags 71. Contamination 0.02 and 0.10 on the primary seed flag 29 and 141. The second seed flags 29 and 141 at those settings. Seed Jaccard is 0.821. Matched-count Jaccard versus robust z is 0.200 and versus robust distance is 0.209. The forest does not add a distinct review set beyond the robust baselines.

Primary flags inside the double-gap predicate: 11 (0.155 of primary flags), state-cluster interval 0.042 to 0.277. Primary flags inside the wider gap: 52. Robust-z flags inside the double-gap predicate: 0. Robust-distance flags inside it: 19.

Share of flagged counties whose largest absolute robust z is each feature (joint means no feature reaches 2.5; tie means the top two match): robust_z: log_population 3 (1.000); mahalanobis: joint 67 (0.827), log_population 14 (0.173); if_primary: joint 53 (0.746), log_population 18 (0.254).

Within-class median population is 44,198. Modeled feature medians: log_population 10.696, rucc_2023 4.000, svi_percentile 0.467, uninsured_percentile 0.350. These are class location summaries, not a comparison that changes the flag rule.

Primary forest review list. Showing 25 of 71, highest primary score first.

| County | State | FIPS | Population | SVI percentile | Uninsured percentile | RUCC | Human status | Pathogen status | Dominant feature | Max abs z | Distance squared | Forest score | Robust z flag | Distance flag | Double gap | Wider gap |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| Harris County | TX | 48201 | 4,726,177 | 0.920 | 0.971 | 1 | no county-linked human record | no pathogen record | log_population | 3.55 | 24.18 | 0.099 | yes | yes | no | yes |
| Keweenaw County | MI | 26083 | 2,088 | 0.008 | 0.422 | 9 | no county-linked human record | no pathogen record | joint | 2.32 | 9.88 | 0.073 | no | no | no | yes |
| Real County | TX | 48385 | 2,830 | 0.783 | 0.958 | 9 | no county-linked human record | no pathogen record | joint | 2.09 | 8.86 | 0.064 | no | no | no | yes |
| Sherman County | OR | 41055 | 1,900 | 0.338 | 0.042 | 9 | no county-linked human record | no pathogen record | joint | 2.39 | 11.39 | 0.057 | no | yes | no | yes |
| Menominee County | WI | 55078 | 4,279 | 0.574 | 0.983 | 9 | published count floor | pathogen present | joint | 1.98 | 8.64 | 0.057 | no | no | no | no |
| Los Angeles County | CA | 06037 | 9,936,690 | 0.863 | 0.550 | 1 | published count floor | pathogen present | log_population | 4.12 | 27.51 | 0.054 | yes | yes | no | no |
| Wolfe County | KY | 21237 | 6,573 | 0.776 | 0.001 | 9 | no county-linked human record | no pathogen record | joint | 1.69 | 14.92 | 0.053 | no | yes | no | yes |
| Cook County | IL | 17031 | 5,225,367 | 0.796 | 0.550 | 1 | published count floor | pathogen present | log_population | 3.63 | 19.64 | 0.050 | yes | yes | no | no |
| Lee County | KY | 21129 | 7,338 | 0.849 | 0.019 | 9 | no county-linked human record | no pathogen record | joint | 1.69 | 16.11 | 0.048 | no | yes | no | yes |
| Miami-Dade County | FL | 12086 | 2,688,237 | 0.881 | 0.865 | 1 | published count floor | no pathogen record | log_population | 3.12 | 16.49 | 0.048 | no | yes | no | no |
| Bexar County | TX | 48029 | 2,014,059 | 0.919 | 0.890 | 1 | no county-linked human record | no pathogen record | log_population | 2.90 | 14.29 | 0.044 | no | yes | no | yes |
| Bronx County | NY | 36005 | 1,443,229 | 0.997 | 0.434 | 1 | published count floor | pathogen present | log_population | 2.65 | 10.22 | 0.043 | no | no | no | no |
| Kings County | NY | 36047 | 2,679,620 | 0.887 | 0.298 | 1 | published count floor | no pathogen record | log_population | 3.12 | 14.00 | 0.042 | no | yes | no | no |
| Dewey County | OK | 40043 | 4,504 | 0.335 | 0.876 | 9 | no county-linked human record | no pathogen record | joint | 1.74 | 9.60 | 0.041 | no | no | no | yes |
| Henderson County | IL | 17071 | 6,374 | 0.039 | 0.003 | 9 | no county-linked human record | pathogen present | joint | 1.69 | 6.30 | 0.041 | no | no | yes | yes |
| Holmes County | OH | 39075 | 44,273 | 0.392 | 0.999 | 9 | published count floor | pathogen present | joint | 2.03 | 18.29 | 0.038 | no | yes | no | no |
| Putnam County | IL | 17155 | 5,628 | 0.005 | 0.019 | 8 | no county-linked human record | pathogen present | joint | 1.57 | 6.13 | 0.038 | no | no | yes | yes |
| Philadelphia County | PA | 42101 | 1,593,208 | 0.947 | 0.403 | 1 | published count floor | pathogen present | log_population | 2.73 | 10.29 | 0.032 | no | no | no | no |
| Cameron County | PA | 42023 | 4,536 | 0.473 | 0.029 | 9 | published count floor | pathogen present | joint | 1.73 | 8.80 | 0.031 | no | no | no | no |
| Red Lake County | MN | 27125 | 3,912 | 0.089 | 0.012 | 8 | no county-linked human record | no pathogen record | joint | 1.84 | 7.29 | 0.031 | no | no | no | yes |
| Lake of the Woods County | MN | 27077 | 3,786 | 0.042 | 0.124 | 9 | no county-linked human record | no pathogen record | joint | 1.87 | 6.44 | 0.031 | no | no | no | yes |
| Craig County | VA | 51045 | 4,898 | 0.059 | 0.014 | 2 | no county-linked human record | no pathogen record | joint | 1.67 | 23.98 | 0.030 | no | yes | no | yes |
| Tunica County | MS | 28143 | 9,787 | 0.960 | 0.800 | 1 | no county-linked human record | no pathogen record | joint | 1.41 | 28.90 | 0.029 | no | yes | no | yes |
| Wyandotte County | KS | 20209 | 167,989 | 0.939 | 0.925 | 1 | no county-linked human record | no pathogen record | joint | 1.80 | 7.54 | 0.027 | no | no | no | yes |
| Tyrrell County | NC | 37177 | 3,389 | 0.854 | 0.763 | 9 | no county-linked human record | no pathogen record | joint | 1.95 | 7.06 | 0.025 | no | no | no | yes |

Robust z flags the forest does not: none.

Robust distance flags the forest does not.

| County | State | FIPS | Population | SVI percentile | Uninsured percentile | RUCC | Human status | Pathogen status | Dominant feature | Max abs z | Distance squared | Forest score | Robust z flag | Distance flag | Double gap | Wider gap |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| Ohio County | IN | 18115 | 5,974 | 0.173 | 0.340 | 1 | no county-linked human record | pathogen present | joint | 1.52 | 26.28 | -0.004 | no | yes | yes | yes |
| Stark County | IL | 17175 | 5,395 | 0.058 | 0.237 | 2 | no county-linked human record | pathogen present | joint | 1.60 | 21.72 | -0.000 | no | yes | yes | yes |
| Camden County | NC | 37029 | 10,547 | 0.252 | 0.047 | 1 | no county-linked human record | no pathogen record | joint | 1.09 | 21.11 | -0.011 | no | yes | no | yes |
| Gates County | NC | 37073 | 10,509 | 0.405 | 0.412 | 1 | no county-linked human record | pathogen present | joint | 1.09 | 20.07 | -0.030 | no | yes | yes | yes |
| Hale County | AL | 01065 | 14,742 | 0.883 | 0.374 | 2 | no county-linked human record | no pathogen record | joint | 1.17 | 19.64 | -0.035 | no | yes | no | yes |
| Wirt County | WV | 54105 | 5,202 | 0.255 | 0.047 | 3 | published count floor | no pathogen record | joint | 1.63 | 19.28 | -0.003 | no | yes | no | no |
| Jasper County | GA | 13159 | 14,882 | 0.549 | 0.769 | 1 | no county-linked human record | no pathogen record | joint | 1.31 | 19.17 | -0.012 | no | yes | no | yes |
| Pendleton County | KY | 21191 | 14,638 | 0.522 | 0.277 | 1 | no county-linked human record | pathogen present | joint | 1.01 | 18.23 | -0.052 | no | yes | yes | yes |
| Somerset County | MD | 24039 | 24,672 | 0.879 | 0.061 | 3 | published count floor | pathogen present | joint | 1.16 | 18.11 | -0.014 | no | yes | no | no |
| Skamania County | WA | 53059 | 12,118 | 0.234 | 0.180 | 1 | no county-linked human record | no pathogen record | joint | 1.01 | 18.05 | -0.043 | no | yes | no | yes |
| Bibb County | AL | 01007 | 22,251 | 0.845 | 0.499 | 1 | no county-linked human record | no pathogen record | joint | 1.06 | 17.68 | -0.026 | no | yes | no | yes |
| Holmes County | MS | 28051 | 16,848 | 0.992 | 0.754 | 2 | no county-linked human record | no pathogen record | joint | 1.47 | 17.51 | -0.013 | no | yes | no | yes |
| Henry County | KY | 21103 | 15,731 | 0.585 | 0.514 | 1 | no county-linked human record | no pathogen record | joint | 1.01 | 17.04 | -0.044 | no | yes | no | yes |
| Newton County | IN | 18111 | 13,829 | 0.323 | 0.266 | 1 | no county-linked human record | pathogen present | joint | 1.01 | 16.71 | -0.049 | no | yes | yes | yes |
| Brown County | IN | 18013 | 15,513 | 0.171 | 0.434 | 1 | no county-linked human record | pathogen present | joint | 1.01 | 15.93 | -0.035 | no | yes | yes | yes |

Data-quality exclusions before the fit: 0. No class row was dropped for a null feature, a nonpositive population, or a rural-urban code outside 1 through 9.

Counties in a state share reporting rules, so the bootstrap resamples states. The interval is a resampling range. Population, vulnerability, insurance, and the rural-urban code are not the same vintage as tick status. A missing human floor is not zero. `No records` and `Unknown` are not negatives. A published human count is a lower bound. MinCovDet status: succeeded. The score is not a map label and not an input to the Tier 1 model.

## Decision

revise. Revise before anyone uses the list. A data-quality exclusion, a double-gap count that does not match 228, a failed distance fit, or an unstable forest seed is enough to hold the screen. Do not build a model on this fit. A code-only slice, if a later review column is authorized, is log population and the rural-urban code. A protected slice is the social-vulnerability percentile and the uninsured percentile. That pair can explain why a county was flagged. It is not an outreach rank.

## Reproduction and retained evidence

Fit commit `d266e44dc3e7ed8f1ea8606f3c5f1daf3a0526fd`. Release `governed-2026-10-15-january-climate-prod`. Seeds 1222026 and 1222027. Run id `122-established-class-anomaly-20261025T2310Z`. Later commits on this branch fix import order and this write-up. They do not change the fitted numbers.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_122_class_anomaly.py
uv run python scripts/verify.py
```

Run id `122-established-class-anomaly-20261025T2310Z`. Lab row counts: `REGISTRY.RUNS` 1, `EDA.METRICS_LONG` 88, `EDA.FINDINGS` 3, `REGISTRY.QUERIES` 4, `EXPERIMENTS.EXPERIMENTS` 8, `EXPERIMENTS.MODEL_METRICS` 19, `EDA.COUNTY_ANOMALY_SCORES_122` 1404. Drive charts: [feature-distributions.png](https://drive.google.com/file/d/16B6a9zLsWwWztP4K5YXJ7ub1tHe-GK5z/view), [score-by-region.png](https://drive.google.com/file/d/1vIs93DXXj_CCvI4iwk7zuldCt-f2VAR3/view), [flag-rate-stability.png](https://drive.google.com/file/d/10mhcvU6Z8Bf5tGb0e5N9dTxidHRUn4o8/view), [feature-driver-shares.png](https://drive.google.com/file/d/1UK3syZ80-kHme799jz_t8eZ6Ni4nbisb/view). Missing charts: none. EDA record: `docs/eda/122-established-class-anomaly.md`. Spec: `docs/eda/122-analysis-spec.md`. Folder: [issue-122](https://drive.google.com/drive/folders/113MOS2KB6HfwR-L3BAZl73J_AFQxp0HE).

County scores, including names, stay in `EDA.COUNTY_ANOMALY_SCORES_122`.
Charts and Drive files are aggregate figures and do not name counties.
A full county extract was not committed.
