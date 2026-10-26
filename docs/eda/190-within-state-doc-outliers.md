# 190: Which counties are documented differently from their state peers?

- Issue: [#190](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/190); program epic [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.
- Release: `governed-2026-10-15-january-climate-prod`.
- Cohort: 3144 counties, 51 states, one snapshot. Published floor 651. No county-linked record 2493. Counts matched the expected 651 and 2493.

## Method and assumptions

Spec [190-within-state-doc-outliers/v1](190-analysis-spec.md), frozen before the fit.
The baseline is the #113 robust z, applied inside each state.
A documentation indicator is not flagged by that baseline.
The isolation forest and local outlier factor use the frozen fallback scale.
#120 types and #121 situation groups are comparisons, not features.

## Material findings and limits

1. Question

Which counties' documentation differs most from their own state's counties, and does an isolation forest add a stable review list beyond the within-state robust z from #113?

2. Method (and why; link the spec)

Spec [190-within-state-doc-outliers/v1](docs/eda/190-analysis-spec.md), frozen before the fit. States with fewer than 11 counties are counted and not scored. Within-state standardization uses the state median and the #113 scale `MAD_SCALE` 1.482602218505602. The baseline omits a column whose MAD is 0. The forest and local outlier factor keep a varying column whose MAD is 0 by using the mean absolute deviation from the median, because a rare documentation status would otherwise be invisible. Baseline flag: absolute z above 3.5, then at most max(1, floor(0.05 * n)) counties per state. Isolation forest: 100 trees, contamination 0.05, bootstrap samples, seeds 1902026 and 1902027. Local outlier factor: contamination 0.05, brute neighbors, no seed. Bootstrap: 20 within-state subsamples of 80 percent, seed 1902030. State-cluster interval: 400 draws, seed 1902030. Permutation: 200 within-state shuffles of the documentation columns, seed 1902040, refitting the primary forest. No ROC-AUC or other label score is computed. There are no ground-truth labels.

3. Key findings with numbers

Scored counties 3111 in 45 states. Complete rows 3144. States below 11 counties: 6 states, 33 counties, not scored. States where a documentation column entered the baseline: 4.
Primary forest flag rate 0.0444 (state-cluster interval 0.0430 to 0.0458). Seed Jaccard 0.7143. Seed score Spearman 0.9740. Bootstrap median Jaccard: robust z 0.7500, forest 0.6667, local outlier factor 0.6667.
Permutation median Jaccard, forest 0.1795, robust z 1.0000. Size Spearman: robust z -0.0302, forest 0.0397, local outlier factor 0.0397. Stable useful flags 42. Jaccard of those flags with the baseline 0.0504. Situation concentration: False.

The forest flag rate sits on the frozen cap. Contamination is 0.05 and each scored state keeps at most floor(0.05 times its complete county count), so a national rate of 0.0444 and a state-cluster interval of 0.0430 to 0.0458 is that cap. Forest and local outlier factor show the same flag count in every scored state for the same reason. Their county sets only partly overlap (Jaccard 0.2661). The baseline permutation Jaccard of 1.0000 is the MAD fact in the method: shuffling the documentation columns does not move a score that cannot see those columns. The forest Jaccard of 0.1795 is the documentation check, and it passes the frozen 0.50 bar. Robust z keep is a stable context screen (bootstrap Jaccard 0.7500, size Spearman -0.0302, documentation column on the baseline in 4 states). It is not a documentation detector. The forest is revise because seed Jaccard 0.7143 is below 0.80 and bootstrap Jaccard 0.6667 is below 0.70. The two seeds did change scores (Spearman 0.9740). Forty-two counties meet the stable-useful county rule, and that set overlaps the baseline flags at Jaccard 0.0504. Product is investigate because the forest method is revise. Situation predicates overlap, and double_gap sits inside wider_gap, so those shares are not a partition. No label metric was computed.

| Band | Method | Scored counties | Flags |
| --- | --- | --- | --- |
| 11_39 | robust_z | 311 | 8 |
| 11_39 | isolation_forest | 311 | 13 |
| 11_39 | local_outlier_factor | 311 | 13 |
| 40_99 | robust_z | 1712 | 44 |
| 40_99 | isolation_forest | 1712 | 74 |
| 40_99 | local_outlier_factor | 1712 | 74 |
| 100_plus | robust_z | 1088 | 31 |
| 100_plus | isolation_forest | 1088 | 51 |
| 100_plus | local_outlier_factor | 1088 | 51 |

| Left | Right | Spearman | Jaccard | Matched Jaccard |
| --- | --- | --- | --- | --- |
| if | z | 0.6478 | 0.1571 | 0.1646 |
| if | lof | 0.7204 | 0.2661 | 0.2377 |
| z | lof | 0.6019 | 0.1218 | 0.0573 |

| Situation | Scored counties | Primary forest flags |
| --- | --- | --- |
| aligned | 419 | 13 |
| double_gap | 228 | 11 |
| wider_gap | 810 | 34 |
| human_ahead | 203 | 23 |
| undocumented | 1189 | 25 |
| other | 490 | 43 |

| #120 cluster | Cohort counties in the scored set | Primary forest flags |
| --- | --- | --- |
| 1 | 447 | 19 |
| 2 | 363 | 15 |

Example primary-forest flags, highest score first. A stable useful flag also meets the seed, bootstrap, and permutation rules.

| County | State | Score | Baseline flag | Other seed | Stable useful | Dominant |
| --- | --- | --- | --- | --- | --- | --- |
| Liberty County | GA | 0.1306 | no | yes | no | tie |
| McIntosh County | GA | 0.1280 | no | yes | no | tie |
| Wyandotte County | KS | 0.1276 | yes | yes | yes | scapularis_established |
| Adams County | IN | 0.1206 | no | yes | no | tie |
| West Feliciana Parish | LA | 0.1160 | no | yes | no | tie |
| Queens County | NY | 0.1058 | yes | yes | no | tie |
| Johnson County | KS | 0.1033 | yes | yes | yes | scapularis_established |
| Clark County | NV | 0.1026 | no | yes | yes | floor_present |

| State | Counties | Scored | Robust z | Forest | LOF |
| --- | --- | --- | --- | --- | --- |
| AK | 30 | 30 | 1 | 1 | 1 |
| AL | 67 | 67 | 0 | 3 | 3 |
| AR | 75 | 75 | 1 | 3 | 3 |
| AZ | 15 | 15 | 1 | 1 | 1 |
| CA | 58 | 58 | 2 | 2 | 2 |
| CO | 64 | 64 | 0 | 3 | 3 |
| CT | 9 | not scored | 0 | 0 | 0 |
| DC | 1 | not scored | 0 | 0 | 0 |
| DE | 3 | not scored | 0 | 0 | 0 |
| FL | 67 | 67 | 3 | 3 | 3 |
| GA | 159 | 159 | 2 | 7 | 7 |
| HI | 5 | not scored | 0 | 0 | 0 |
| IA | 99 | 99 | 4 | 4 | 4 |
| ID | 44 | 44 | 0 | 2 | 2 |
| IL | 102 | 102 | 5 | 5 | 5 |
| IN | 92 | 92 | 1 | 4 | 4 |
| KS | 105 | 105 | 5 | 5 | 5 |
| KY | 120 | 120 | 3 | 6 | 6 |
| LA | 64 | 64 | 3 | 3 | 3 |
| MA | 14 | 14 | 1 | 1 | 1 |
| MD | 24 | 24 | 1 | 1 | 1 |
| ME | 16 | 16 | 0 | 1 | 1 |
| MI | 83 | 83 | 1 | 4 | 4 |
| MN | 87 | 87 | 4 | 4 | 4 |
| MO | 115 | 115 | 2 | 5 | 5 |
| MS | 82 | 82 | 4 | 4 | 4 |
| MT | 56 | 56 | 1 | 2 | 2 |
| NC | 100 | 100 | 1 | 5 | 5 |
| ND | 53 | 53 | 2 | 2 | 2 |
| NE | 93 | 93 | 2 | 4 | 4 |
| NH | 10 | not scored | 0 | 0 | 0 |
| NJ | 21 | 21 | 0 | 1 | 1 |
| NM | 33 | 33 | 1 | 1 | 1 |
| NV | 17 | 17 | 1 | 1 | 1 |
| NY | 62 | 62 | 3 | 3 | 3 |
| OH | 88 | 88 | 4 | 4 | 4 |
| OK | 77 | 77 | 0 | 3 | 3 |
| OR | 36 | 36 | 0 | 1 | 1 |
| PA | 67 | 67 | 1 | 3 | 3 |
| RI | 5 | not scored | 0 | 0 | 0 |
| SC | 46 | 46 | 1 | 2 | 2 |
| SD | 66 | 66 | 1 | 3 | 3 |
| TN | 95 | 95 | 3 | 4 | 4 |
| TX | 254 | 254 | 12 | 12 | 12 |
| UT | 29 | 29 | 0 | 1 | 1 |
| VA | 133 | 133 | 1 | 6 | 6 |
| VT | 14 | 14 | 1 | 1 | 1 |
| WA | 39 | 39 | 0 | 1 | 1 |
| WI | 72 | 72 | 3 | 3 | 3 |
| WV | 55 | 55 | 0 | 2 | 2 |
| WY | 23 | 23 | 1 | 1 | 1 |

4. Caveats

A flag means documented differently from state peers. It is not a data error and it is not a statement about disease burden. Published floors are surveillance signals and lower bounds where the CDC floor is 5. `No records` and `Unknown` are not negatives. A missing floor is not zero. No ground truth exists, so this is a data-review signal, not a validated detector. #188 showed that state-level composition can masquerade as a county signal. The permutation check is the guard, and a pass would still not be validation. The #113 baseline cannot flag a documentation indicator: an uneven 0/1 column has MAD 0, and an even split has absolute z 1/MAD_SCALE, about 0.67, below 3.5. SVI rescaled by 100: False. Uninsured percentile rescaled by 100: False.

5. Disposition

Method, isolation forest: revise. Method, robust z: keep. Method, local outlier factor: revise. Product: investigate.

6. Artifacts

Run id `190-within-state-doc-outliers-20261026T1736Z`. Grant SELECT for OH_LYME_PROD_READ: pass.
Lab row counts: `REGISTRY.RUNS` 1, `EDA.METRICS_LONG` 49, `EDA.FINDINGS` 2, `REGISTRY.QUERIES` 3, `EXPERIMENTS.EXPERIMENTS` 3, `EXPERIMENTS.MODEL_METRICS` 9, `EDA.COUNTY_DOC_FLAGS_190` 3144, `REGISTRY.ARTIFACTS` 3.
Drive folder [issue-190](https://drive.google.com/drive/folders/1swXov_1cfBRrgoypncdMRTGaTUZGEb5n).
Registered charts: [band-flag-share.png](https://drive.google.com/file/d/1u6XSCRj164leAIC59VRjOyTsZd_CdR0P/view) (3116 bytes), [method-agreement.png](https://drive.google.com/file/d/1iiEJPj7XUxiMJ9VxtNnTZ86-EPuzi99k/view) (2811 bytes), [stability.png](https://drive.google.com/file/d/1Oc9sEavBObvnOvGGgohRnTZnB6dZ_kPH/view) (3033 bytes).
`permutation-check.png` is missing from Drive after two uploads whose bytes did not match the local file. Local size 3316. SHA-256 `89dc71c3a9300371a9a05e643c5f92184244842a185a40ec6d22b5b1c0835ea1`. The mismatched Drive copies were trashed and the chart was not registered.
Write-up: `docs/eda/190-within-state-doc-outliers.md`.

7. Reproducibility

Commit `b23a7a3ca63988dbc9b855a359051c7c0f012ffb`. Release `governed-2026-10-15-january-climate-prod`. Seeds 1902026, 1902027, cluster and bootstrap 1902030, permutation 1902040.
Command: `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_190_doc_outliers.py`.
Gate: `uv run python scripts/verify.py`.

## Decision

Method revise. Product investigate. This is not a release and not a change to the Tier 1 model.

## Reproduction and retained evidence

- Code revision/run: commit `b23a7a3ca63988dbc9b855a359051c7c0f012ffb`, run `190-within-state-doc-outliers-20261026T1736Z`, spec `190-within-state-doc-outliers/v1`.
- Entry points: `sql/validation/190_doc_outliers.sql`, `src/lyme_gap_atlas_ml/doc_outliers.py`, `scripts/eda_190_doc_outliers.py`.
- Command: `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_190_doc_outliers.py`.
- Gate: `uv run python scripts/verify.py`.
- Transient artifacts not committed: `artifacts/charts/190/` and `outputs/`.
