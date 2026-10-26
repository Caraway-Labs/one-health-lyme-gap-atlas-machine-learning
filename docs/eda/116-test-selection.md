# 116: Which county comparisons support a statistical difference?

- Issue: [ML #116](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/116), part of [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
  Spec: [116-test-selection/v1.2](116-analysis-spec.md).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.
  Pinned release `governed-2026-10-15-january-climate-prod`.
- Cohort: rows read 3144. Published floor 651. No county-linked record 2493. Other human status 0.

## Method and assumptions

Spec [116-test-selection/v1.2](116-analysis-spec.md), frozen before the read.
The descriptive unit is the county. The resampling unit is the state.
Welch t, paired t, Mann-Whitney, Wilcoxon signed-rank, ANOVA,
Kruskal-Wallis, chi-square, Fisher exact, Pearson, and regression are rejected.
Spearman is the chosen rank coefficient. Share differences use a state-cluster interval.
Holm adjusts the four state-resample tail shares. Benjamini-Hochberg is not used.
Q3, climate versus tick or pathogen documentation, is the predeclared no-go.
No model was fit. Seeds 1162026, 1162027, and 6501.

| Method | Decision | Why |
| --- | --- | --- |
| Welch t | rejected | Binary floor; counties are not independent |
| Paired t | rejected | One county row; no paired period |
| Mann-Whitney | rejected | Ranks restate the share; independence fails |
| Wilcoxon signed-rank | rejected | No paired county periods |
| ANOVA / Welch ANOVA | rejected | Rural codes are ordered; code cells are unequal |
| Kruskal-Wallis | rejected | Nine-code table stays descriptive |
| Chi-square | rejected | Numerator of V only; counties are not independent |
| Fisher exact | rejected | National tables are not small; dependence remains |
| Spearman | chosen | H3 and H4, with a state-cluster interval |
| Pearson | rejected | Wrong scale; the correlation sweep is issue 114 |
| Regression | rejected | No sampling model for reporting or dependence |
| Climate stratum test | not_estimable | January daily climate is not an atlas stratum |

## Material findings and limits

Epic #22 section 4.1 recorded 651 published floors and 2493 counties with no county-linked record, out of 3144.
This release has 651 and 2493.
Vulnerability rescaled by 100: no. Maximum: 1.0000.

Q1 eligible counties 3144 (metro 1186, nonmetro 1958). Null rural-urban codes among known human statuses: 0.
Metro minus nonmetro published-floor share: estimate 0.1779, state-cluster 0.1269 to 0.2313, county-resample width ratio 1.6693, tail share 0.0000, Holm-adjusted tail share 0.0000.

Q2 eligible counties 3144 (lower vulnerability 1572, higher 1572). Null vulnerability among known human statuses: 0.
Lower minus higher vulnerability published-floor share: estimate 0.1559, state-cluster 0.0830 to 0.2273, county-resample width ratio 2.5817, tail share 0.0000, Holm-adjusted tail share 0.0000.

The Holm family is complete. Metro minus nonmetro published-floor share: estimate 0.1779, state-cluster 0.1269 to 0.2313, county-resample width ratio 1.6693, tail share 0.0000, Holm-adjusted tail share 0.0000. Lower minus higher vulnerability published-floor share: estimate 0.1559, state-cluster 0.0830 to 0.2273, county-resample width ratio 2.5817, tail share 0.0000, Holm-adjusted tail share 0.0000. Spearman, vulnerability percentile and published floor: estimate -0.1971, state-cluster -0.3067 to -0.0721, county-resample width ratio 3.8029, tail share 0.0020, Holm-adjusted tail share 0.0020. Spearman, rural-urban code and published floor: estimate -0.2455, state-cluster -0.3266 to -0.1661, county-resample width ratio 2.4868, tail share 0.0000, Holm-adjusted tail share 0.0000.

October 13 targets: tick x pathogen V 0.5607, human x tick V 0.4780, human x pathogen V 0.5705, interval 0.4650 to 0.6524.
Helper eligible n: 3109. Helper V: 0.5607. Established-plus-Reported collapse V: 0.4258. The issue 65 reference collapse was 0.4258.

| Association | This release | State-cluster interval | Width ratio | Epic display |
| --- | --- | --- | --- | --- |
| tick_pathogen | 0.5607 (n 3109) | 0.4650 to 0.6524 | 4.1382 | 0.5607 |
| human_tick | 0.4780 (n 3109) | 0.3785 to 0.5810 | 3.9429 | 0.4780 |
| human_pathogen | 0.5705 (n 3109) | 0.4354 to 0.7130 | 4.0757 | 0.5705 |

The exhaustive write-up's V near 0.81 keeps Unknown as its own level.
Epic item 4's 0.5607 drops Unknown and out-of-scope counties.
Those are different tables, not a failed replay of one table.

Rural-urban published-floor shares, beside the 13 October counts.
A 1-10 cell may be named here. It is omitted from lab aggregates and charts.

| Code | Counties | Published | October counties | October published |
| --- | ---: | ---: | ---: | ---: |
| rucc_1 | 443 | 168 | 443 | 168 |
| rucc_2 | 385 | 103 | 385 | 103 |
| rucc_3 | 358 | 106 | 358 | 106 |
| rucc_4 | 201 | 58 | 201 | 58 |
| rucc_5 | 76 | 8 | 76 | 8 |
| rucc_6 | 379 | 66 | 379 | 66 |
| rucc_7 | 247 | 34 | 247 | 34 |
| rucc_8 | 466 | 70 | 466 | 70 |
| rucc_9 | 589 | 38 | 589 | 38 |

Vulnerability bins, excluding a value of exactly 1 (1 counties, 0 published):

| Bin | Counties | Published | October counties | October published |
| --- | ---: | ---: | ---: | ---: |
| 0.00-0.20 | 629 | 169 | 629 | 169 |
| 0.20-0.40 | 629 | 187 | 629 | 187 |
| 0.40-0.60 | 628 | 166 | 628 | 166 |
| 0.60-0.80 | 629 | 89 | 629 | 89 |
| 0.80-1.00 | 628 | 40 | 628 | 40 |

A sensitivity move of at least 0.02, or a sign change, is material.
Material rows: q1_without_Northeast, q2_without_Northeast, q1_without_Midwest, q2_without_Midwest, q1_without_South, q2_without_South, q2_without_West.

| Sensitivity | Estimate | Absolute move | Sign change |
| --- | ---: | ---: | --- |
| q1_without_Northeast | 0.1399 | 0.0380 | no |
| q2_without_Northeast | 0.1217 | 0.0342 | no |
| q1_without_Midwest | 0.1530 | 0.0250 | no |
| q2_without_Midwest | 0.2321 | 0.0763 | no |
| q1_without_South | 0.2711 | 0.0931 | no |
| q2_without_South | 0.0539 | 0.1019 | no |
| q1_without_West | 0.1867 | 0.0088 | no |
| q2_without_West | 0.1795 | 0.0237 | no |
| q1_states_at_least_15 | 0.1698 | 0.0081 | no |
| q2_states_at_least_15 | 0.1451 | 0.0108 | no |

Q3 remains not estimable. No climate query was issued.

Peer-review spot checks use the smallest FIPS under each frozen rule.
`No records` is a documentation state. A null vulnerability value is missing, not zero.

| Rule | County | State | FIPS | Human status | Tick | Pathogen | RUCC | SVI |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| published_floor_rucc_1 | Pima County | AZ | 04019 | published_count_floor | No records | No records | 1 | 0.888 |
| no_county_record_rucc_9 | Choctaw County | AL | 01023 | no_county_linked_record | Established | No records | 9 | 0.655 |
| null_svi | none |  |  |  |  |  |  |  |

## Decision

**REVISE**, mapped from the frozen rule.
The October 13 four-decimal displays match. Both share-difference state-cluster intervals exclude zero. Leaving out a Census region moves a share difference by at least 0.02, so the national magnitude is not stable across regions. No sensitivity changes sign. The climate comparison remains a no-go.

Describe the direction with the state-cluster interval. Do not treat the national magnitude as a figure that holds inside every region. It is not permission to train a model, publish a score, or claim causation.

## Reproduction and retained evidence

- Code revision: `deec41bf1088d9893df2759d5b0ee2a1dce7811d`. Run `116-test-selection-20261026T0051Z`. Release `governed-2026-10-15-january-climate-prod`.
- Entry points: `sql/validation/116_test_selection.sql`,
  `scripts/eda_116_test_selection.py`, `src/lyme_gap_atlas_ml/test_selection.py`.
- Commands: `uv run python scripts/check_ml_agent_context.py`,
  then `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python`
  `scripts/eda_116_test_selection.py`, then `uv run python scripts/verify.py`.
- Lab row counts: `REGISTRY.RUNS` 1, `EDA.METRICS_LONG` 67, `EDA.CORRELATIONS` 6, `EDA.FINDINGS` 4, `REGISTRY.QUERIES` 3, `REGISTRY.ARTIFACTS` 3.
- Drive:
- issue-116 folder: https://drive.google.com/drive/folders/12kWeR0nLu6qalybPg6NiM_ytOBdWAXJ0
- decision-matrix.png (26541 bytes): https://drive.google.com/file/d/1OXPG1drLuk0oHcbgkvA_37EyWLcFeXLo/view?usp=drivesdk
- bootstrap-intervals.png (14901 bytes): https://drive.google.com/file/d/1RMveVB60ie-9NNSQi5ribENLmZBc6OyL/view?usp=drivesdk
- group-shares.png (15896 bytes): https://drive.google.com/file/d/1TAFSNsWxywOJcVSZxLYigvivLEaLOQCj/view?usp=drivesdk
- Transient artifacts not committed: in-memory county rows,
  PNG files under `artifacts/charts/116/`, and the local comment draft.

The shared lab writers do not grant SELECT. This story creates no new table.
Role administration is outside the Snowflake integration guide,
so `OH_LYME_PROD_READ` still cannot count a new lab table until an owner grants it.
