# 123: Which state reporting regimes resemble each other?

- Issue: [#123](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/123); parent epic [#118](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/118); program epic [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`. Release `governed-2026-10-15-january-climate-prod`.
- Cohort: 3,144 counties rolled to 51 state rows, including the District of Columbia. One snapshot.

## Method and assumptions

Spec [123-state-reporting-regimes/v1](docs/eda/123-analysis-spec.md), frozen before the fit. The publication-free profile may be used as a categorical county-model feature. The descriptive profile stays a briefing result.

## Material findings and limits

1. Question

Which states resemble each other in publication, tick documentation, and pathogen documentation? Which descriptive group contains the high-publication Northeast states, and which contains states with no published county floor? After publication rate is removed, which states still look alike on tick coverage, pathogen coverage, and rural mix? Which profile may a later county model use?

High-publication Census Northeast states, defined before the fit as a published-floor share of at least 0.5, are CT, MA, ME, NH, NJ, NY, PA, RI, VT. The descriptive group with the most of them is group 4.

The descriptive group with the most states that have no published county floor is group 1. Every such state stays in the partition, and its stored median is missing:

| State | Counties | Descriptive group | Stored median |
| --- | ---: | ---: | --- |
| AK | 30 | 1 | missing |
| AR | 75 | 1 | missing |
| CO | 64 | 1 | missing |
| GA | 159 | 1 | missing |
| HI | 5 | 1 | missing |
| ID | 44 | 1 | missing |
| KS | 105 | 1 | missing |
| LA | 64 | 1 | missing |
| MO | 115 | 1 | missing |
| MS | 82 | 1 | missing |
| MT | 56 | 1 | missing |
| ND | 53 | 1 | missing |
| NE | 93 | 1 | missing |
| NM | 33 | 1 | missing |
| OK | 77 | 1 | missing |
| SD | 66 | 1 | missing |
| TX | 254 | 1 | missing |
| WA | 39 | 1 | missing |
| WY | 23 | 1 | missing |

The publication-free profile may be used as a categorical county-model feature. The descriptive profile stays a briefing result.

2. Method (and why; link the spec)

Spec [123-state-reporting-regimes/v1](docs/eda/123-analysis-spec.md), frozen before the fit. The 51 state rows are clustered with Ward linkage and Euclidean distance after `StandardScaler`, the same linkage class, scaler, silhouette, and adjusted Rand index #110 uses. The #116 `resample_interval` supplies the 2,000-draw bootstrap. The cut is the admissible k in 2 through 6 with the highest silhouette, with leave-one-state-out and the bootstrap as the stability evidence. Average linkage, complete linkage, and a descriptive fit that drops the median columns are recorded and do not choose the cut.

A state with no published floor keeps a missing median. The descriptive distance uses an observation indicator plus a median coordinate that is 0 only because that indicator is 0. The stored median is never filled with zero. The publication-free profile is the established-tick share, the pathogen-present share, and the nonmetropolitan share (`RUCC_2023` 4 through 9, the #116 split). It does not include the publication share or the published floor.

#109 supplies the status definitions: a published floor is `published_count_floor`, an established tick is `Established`, and a pathogen record is `Present`. `No records` and `Unknown` stay in the denominator. #107 supplies the comparison of 19 states and 1,437 counties with no published county floor.

3. Key findings with numbers

descriptive: k=6, cut_stable=True, silhouette=0.5815, leave-one-state-out median=1.0000 (minimum 0.9194, failures 0), bootstrap 0.6864 to 1.0000 (estimable True, failures 0), average-linkage adjusted Rand 0.9337, complete-linkage adjusted Rand 0.9815, share-only adjusted Rand 0.4969, tree adjusted Rand 1.0000.

publication_free: k=2, cut_stable=True, silhouette=0.4965, leave-one-state-out median=1.0000 (minimum 0.8432, failures 0), bootstrap 0.5171 to 1.0000 (estimable True, failures 0), average-linkage adjusted Rand 0.9215, complete-linkage adjusted Rand 0.5171, share-only adjusted Rand not applicable, tree adjusted Rand 1.0000.

Cross-profile adjusted Rand index: 0.3930. Zero-published states: 19 (#107 comparison 19). Counties in those states: 1437 (#107 comparison 1437). Comparison matched: True.

k grid. Admissible means leave-one-state-out median at least 0.70 and bootstrap lower endpoint at least 0.40.

| Profile | k | Silhouette | LOSO median | Bootstrap low | Bootstrap high | Admissible | Chosen |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| descriptive | 2 | 0.4656 | 1.0000 | 0.0601 | 0.8462 | False | False |
| descriptive | 3 | 0.5307 | 1.0000 | 0.4709 | 0.8968 | True | False |
| descriptive | 4 | 0.5707 | 1.0000 | 0.6922 | 1.0000 | True | False |
| descriptive | 5 | 0.5798 | 1.0000 | 0.7784 | 1.0000 | True | False |
| descriptive | 6 | 0.5815 | 1.0000 | 0.6864 | 1.0000 | True | True |
| publication_free | 2 | 0.4965 | 1.0000 | 0.5171 | 1.0000 | True | True |
| publication_free | 3 | 0.3895 | 0.5047 | 0.3597 | 1.0000 | False | False |
| publication_free | 4 | 0.4038 | 1.0000 | 0.4176 | 0.9619 | True | False |
| publication_free | 5 | 0.4164 | 1.0000 | 0.4330 | 0.9713 | True | False |
| publication_free | 6 | 0.4415 | 1.0000 | 0.4427 | 0.9452 | True | False |

Contingency of state counts, descriptive rows by publication-free columns. This write-up shows every count.

| Descriptive group | Publication-free 1 | Publication-free 2 |
| --- | ---: | ---: |
| 1 | 19 | 0 |
| 2 | 11 | 0 |
| 3 | 1 | 7 |
| 4 | 0 | 5 |
| 5 | 0 | 4 |
| 6 | 0 | 4 |

Descriptive groups

Group 1: AK, AR, CO, GA, HI, ID, KS, LA, MO, MS, MT, ND, NE, NM, OK, SD, TX, WA, WY. Medians among member states with at least 11 counties: published share 0.0000, established-tick share 0.0854, pathogen-present share 0.0000, rural nonmetro share 0.7698, published floor rate per 100,000 suppressed.

Group 2: AL, AZ, FL, IA, KY, NC, NV, OR, SC, TN, UT. Medians among member states with at least 11 counties: published share 0.0588, established-tick share 0.5000, pathogen-present share 0.0278, rural nonmetro share 0.5500, published floor rate per 100,000 2.23.

Group 3: CA, IL, IN, MD, MI, MN, OH, VA. Numeric summary suppressed because fewer than 11 member states have at least 11 counties.

Group 4: ME, NH, NY, PA, VT. Numeric summary suppressed because fewer than 11 member states have at least 11 counties.

Group 5: CT, DC, DE, NJ. Numeric summary suppressed because fewer than 11 member states have at least 11 counties.

Group 6: MA, RI, WI, WV. Numeric summary suppressed because fewer than 11 member states have at least 11 counties.

Publication-free groups

Group 1: AK, AL, AR, AZ, CO, FL, GA, HI, IA, ID, KS, KY, LA, MO, MS, MT, NC, ND, NE, NM, NV, OK, OR, SC, SD, TN, TX, UT, VA, WA, WY. Medians among member states with at least 11 counties: published share 0.0000, established-tick share 0.2261, pathogen-present share 0.0000, rural nonmetro share 0.6927, published floor rate per 100,000 2.48.

Group 2: CA, CT, DC, DE, IL, IN, MA, MD, ME, MI, MN, NH, NJ, NY, OH, PA, RI, VT, WI, WV. Medians among member states with at least 11 counties: published share 0.9818, established-tick share 0.9483, pathogen-present share 0.5568, rural nonmetro share 0.5341, published floor rate per 100,000 66.11.

State table. Shares are county shares. The median is the published floor rate per 100,000. Missing means the state published no county floor.

| State | Counties | Published share | Established tick share | Pathogen present share | Median published floor | Rural nonmetro share | Descriptive group | Publication-free group |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AK | 30 | 0.0000 | 0.0000 | 0.0000 | missing | 0.9000 | 1 | 1 |
| AL | 67 | 0.0149 | 0.5373 | 0.0000 | 2.14 | 0.5373 | 2 | 1 |
| AR | 75 | 0.0000 | 0.4133 | 0.0000 | missing | 0.7733 | 1 | 1 |
| AZ | 15 | 0.0667 | 0.0667 | 0.0000 | 0.48 | 0.4667 | 2 | 1 |
| CA | 58 | 0.1034 | 0.9483 | 0.5000 | 0.48 | 0.3621 | 3 | 2 |
| CO | 64 | 0.0000 | 0.0000 | 0.0000 | missing | 0.7344 | 1 | 1 |
| CT | 9 | 1.0000 | 1.0000 | 1.0000 | 86.04 | 0.2222 | 5 | 2 |
| DC | 1 | 1.0000 | 1.0000 | 1.0000 | 16.11 | 0.0000 | 5 | 2 |
| DE | 3 | 1.0000 | 1.0000 | 1.0000 | 32.41 | 0.3333 | 5 | 2 |
| FL | 67 | 0.2388 | 0.8209 | 0.0000 | 2.23 | 0.3284 | 2 | 1 |
| GA | 159 | 0.0000 | 0.2453 | 0.0126 | missing | 0.5346 | 1 | 1 |
| HI | 5 | 0.0000 | 0.0000 | 0.0000 | missing | 0.4000 | 1 | 1 |
| IA | 99 | 0.0808 | 0.5152 | 0.1717 | 11.25 | 0.7778 | 2 | 1 |
| ID | 44 | 0.0000 | 0.0000 | 0.0000 | missing | 0.6818 | 1 | 1 |
| IL | 102 | 0.1275 | 0.6176 | 0.5000 | 5.33 | 0.6373 | 3 | 2 |
| IN | 92 | 0.1087 | 0.9783 | 0.9565 | 5.72 | 0.5217 | 3 | 2 |
| KS | 105 | 0.0000 | 0.0381 | 0.0000 | missing | 0.8095 | 1 | 1 |
| KY | 120 | 0.0167 | 0.4167 | 0.1250 | 6.57 | 0.6750 | 2 | 1 |
| LA | 64 | 0.0000 | 0.2969 | 0.0156 | missing | 0.4219 | 1 | 1 |
| MA | 14 | 1.0000 | 1.0000 | 0.4286 | 185.19 | 0.2143 | 6 | 2 |
| MD | 24 | 1.0000 | 0.9167 | 0.4167 | 56.04 | 0.2917 | 3 | 2 |
| ME | 16 | 1.0000 | 1.0000 | 0.9375 | 223.75 | 0.6875 | 4 | 2 |
| MI | 83 | 0.5301 | 0.6747 | 0.4819 | 21.65 | 0.6386 | 3 | 2 |
| MN | 87 | 0.5977 | 0.7586 | 0.3908 | 66.11 | 0.6897 | 3 | 2 |
| MO | 115 | 0.0000 | 0.2000 | 0.0000 | missing | 0.6957 | 1 | 1 |
| MS | 82 | 0.0000 | 0.4878 | 0.0000 | missing | 0.7561 | 1 | 1 |
| MT | 56 | 0.0000 | 0.0000 | 0.0000 | missing | 0.8214 | 1 | 1 |
| NC | 100 | 0.1400 | 0.6300 | 0.1800 | 8.58 | 0.5500 | 2 | 1 |
| ND | 53 | 0.0000 | 0.1321 | 0.0377 | missing | 0.8491 | 1 | 1 |
| NE | 93 | 0.0000 | 0.0323 | 0.0108 | missing | 0.8817 | 1 | 1 |
| NH | 10 | 1.0000 | 1.0000 | 1.0000 | 126.32 | 0.7000 | 4 | 2 |
| NJ | 21 | 1.0000 | 1.0000 | 0.9524 | 63.06 | 0.0000 | 5 | 2 |
| NM | 33 | 0.0000 | 0.0000 | 0.0000 | missing | 0.7879 | 1 | 1 |
| NV | 17 | 0.0588 | 0.0000 | 0.0000 | 0.26 | 0.7059 | 2 | 1 |
| NY | 62 | 1.0000 | 1.0000 | 0.9516 | 191.06 | 0.4032 | 4 | 2 |
| OH | 88 | 0.4545 | 0.8636 | 0.5568 | 22.08 | 0.5341 | 3 | 2 |
| OK | 77 | 0.0000 | 0.3636 | 0.0000 | missing | 0.7662 | 1 | 1 |
| OR | 36 | 0.0833 | 0.5000 | 0.0278 | 1.74 | 0.5833 | 2 | 1 |
| PA | 67 | 1.0000 | 1.0000 | 1.0000 | 165.01 | 0.5075 | 4 | 2 |
| RI | 5 | 1.0000 | 1.0000 | 0.2000 | 282.29 | 0.0000 | 6 | 2 |
| SC | 46 | 0.0435 | 0.5000 | 0.0652 | 2.73 | 0.4348 | 2 | 1 |
| SD | 66 | 0.0000 | 0.0606 | 0.0152 | missing | 0.8788 | 1 | 1 |
| TN | 95 | 0.0211 | 0.3053 | 0.0632 | 2.77 | 0.5368 | 2 | 1 |
| TX | 254 | 0.0000 | 0.1102 | 0.0000 | missing | 0.6614 | 1 | 1 |
| UT | 29 | 0.0345 | 0.2069 | 0.0000 | 0.76 | 0.6897 | 2 | 1 |
| VA | 133 | 0.4887 | 0.5263 | 0.3534 | 24.83 | 0.3985 | 3 | 1 |
| VT | 14 | 0.9286 | 1.0000 | 0.9286 | 226.84 | 0.7857 | 4 | 2 |
| WA | 39 | 0.0000 | 0.4359 | 0.0769 | missing | 0.5128 | 1 | 1 |
| WI | 72 | 0.9861 | 0.8472 | 0.5694 | 197.76 | 0.6250 | 6 | 2 |
| WV | 55 | 0.9818 | 0.8727 | 0.4727 | 220.95 | 0.6364 | 6 | 2 |
| WY | 23 | 0.0000 | 0.0000 | 0.0000 | missing | 0.9130 | 1 | 1 |

4. Caveats

Counts are surveillance signals and lower bounds. The published floor starts at the CDC floor of 5. It is not incidence, risk, or causation. `No records` and `Unknown` are not negatives. A missing floor is not zero. A group is a partition of reporting regimes, not a risk tier. No production score is published.

Human surveillance is calendar 2023. Tick and pathogen status are cumulative through 2025-12-31. The rural-urban code is 2023. Those windows are not one time base. The bootstrap resamples states and does not cover dependence that crosses a state line.

States with fewer than 11 counties (CT, DC, DE, HI, NH, RI) stay in both groups. The dendrogram labels them with postal codes and does not print share values. The lab assignment table, other git files, and Drive charts suppress their shares, median, rural share, county count, and zero-published flag. This write-up shows the full state rows.

Descriptive median contrast: True. A false contrast means the observed medians did not vary, so the median coordinate adds no distance and the indicator still marks states with no median.

5. Disposition

Method: keep. Product: advance.

The publication-free profile may be used as a categorical county-model feature. The descriptive profile stays a briefing result.

Rule failures: none.

6. Artifacts

run_id: 123-state-reporting-regimes-20261026T1159Z

Snowflake row counts: REGISTRY.RUNS=1, EDA.METRICS_LONG=75, EDA.FINDINGS=2, REGISTRY.QUERIES=3, EXPERIMENTS.EXPERIMENTS=2, EXPERIMENTS.MODEL_METRICS=23, EDA.STATE_REGIME_GROUPS_123=51, REGISTRY.ARTIFACTS=0.

SELECT grant on EDA.STATE_REGIME_GROUPS_123 to OH_LYME_PROD_READ: pass.

Drive folder: https://drive.google.com/drive/folders/1CZWYYIEm0WDFf0PuO744dMcOxF4WWqrR. Charts missing after the uploaded file size did not match the local bytes; the mismatched file was trashed. ML Lead can complete them: descriptive-dendrogram.png bytes=23619 sha256=41c149cae469f3aa0dd9e299a56a3728de35e9950cf8f08cc1e54e1a03870012; publication-free-dendrogram.png bytes=22782 sha256=c694778fabf0554ee1993df38e0c7751627cc049fa26aba29bee64ee964f4565; group-contingency.png bytes=15890 sha256=0e9418f89f33a69b78ba391884829ddcd29c962da4b79a36f740ee90941e7b8b.

Doc: docs/eda/123-state-reporting-regimes.md

Spec: docs/eda/123-analysis-spec.md

7. Reproducibility

Commit: 00b0184c4fe7620ab1b06b8405d9683411001ded
Release: governed-2026-10-15-january-climate-prod
Bundle SHA-256: 53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d
Seeds: descriptive bootstrap 1232026, publication-free bootstrap 1232027. Ward has no seed.
State count in the fit: 51. scikit-learn version is recorded on the run.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_123_state_regimes.py
uv run python scripts/verify.py
```

## Decision

KEEP for the clustering method. ADVANCE for product value. This is not a release, a tier change, or a production score.

## Reproduction and retained evidence

- Fit commit `00b0184c4fe7620ab1b06b8405d9683411001ded`, run `123-state-reporting-regimes-20261026T1159Z`, release `governed-2026-10-15-january-climate-prod`.
- Entry points: `sql/validation/123_state_regimes.sql`, `scripts/eda_123_state_regimes.py`, `src/lyme_gap_atlas_ml/state_regimes.py`.
- Commands: see the reproducibility section above.
- Transient artifacts not committed: chart PNGs under ignored `artifacts/charts/123/`. No county extract.
