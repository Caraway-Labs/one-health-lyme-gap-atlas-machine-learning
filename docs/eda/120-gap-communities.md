# 120: Which community types sit inside the established-tick gap?

- Issue: [#120](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/120);
  parent epic [#118](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/118);
  program epic [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
  Question: which community types inside the established-tick gap are alike
  enough to share one outreach description?
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`. Release `governed-2026-10-15-january-climate-prod`.
- Cohort: established aggregate tick status and no published human floor. Live cohort 810.
  Double-gap subset 228. Reference counts are 810 and 228.

## Method and assumptions

Spec [120-gap-communities/v1](120-analysis-spec.md), frozen before the fit.
K-prototypes with the Huang mixed distance. Numeric fields are z-scored.
Categorical blanks stay categories. #109 defines statuses. #114 defines the
percentile unit rule. #110 defines the stability checks this spec adapts.
#121 defines the cohort predicates and is not a feature source.
Seeds 1202026, 1202027, and 1202028. Cluster membership is not disease risk.

## Material findings and limits

National extract 3144 counties, published floor 651, no county-linked human record 2493. Established-tick gap 810 (reference 810). Double gap inside it 228 (reference 228). Double-gap counties outside the cohort: 0. Cohort rows excluded for a missing numeric: 0. Gamma 0.5000. Selected k 2. Reported k 2. The most people type is 1. The most rural type is 2.

| k | Converged | Seed ARI | Silhouette | Bootstrap low | Bootstrap high | Min size |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 2 | yes | 0.9705 | 0.4954 | 0.7986 | 0.9901 | 363 |
| 3 | yes | 0.9651 | 0.4873 | 0.7231 | 0.9593 | 184 |
| 4 | yes | 0.8490 | 0.3899 | 0.3897 | 0.9155 | 143 |
| 5 | no | not estimable | not estimable | not estimable | not estimable | 77 |
| 6 | yes | 0.6343 | 0.3214 | 0.3973 | 0.7289 | 66 |

Pre-clustering frequencies inside the clustering cohort. A bin can be small; the chart omits counts from 1 to 10.

| Feature | Bin | Counties |
| --- | --- | ---: |
| population | under_10k | 79 |
| population | 10k_to_25k | 246 |
| population | 25k_to_50k | 207 |
| population | 50k_to_100k | 121 |
| population | 100k_to_250k | 94 |
| population | 250k_to_500k | 33 |
| population | 500k_to_1m | 21 |
| population | 1m_or_more | 9 |
| svi_percentile | le_0.1 | 75 |
| svi_percentile | 0.1_to_0.2 | 66 |
| svi_percentile | 0.2_to_0.3 | 52 |
| svi_percentile | 0.3_to_0.4 | 74 |
| svi_percentile | 0.4_to_0.5 | 65 |
| svi_percentile | 0.5_to_0.6 | 82 |
| svi_percentile | 0.6_to_0.7 | 81 |
| svi_percentile | 0.7_to_0.8 | 95 |
| svi_percentile | 0.8_to_0.9 | 117 |
| svi_percentile | gt_0.9 | 103 |
| uninsured_percentile | le_0.1 | 80 |
| uninsured_percentile | 0.1_to_0.2 | 78 |
| uninsured_percentile | 0.2_to_0.3 | 88 |
| uninsured_percentile | 0.3_to_0.4 | 81 |
| uninsured_percentile | 0.4_to_0.5 | 99 |
| uninsured_percentile | 0.5_to_0.6 | 79 |
| uninsured_percentile | 0.6_to_0.7 | 82 |
| uninsured_percentile | 0.7_to_0.8 | 96 |
| uninsured_percentile | 0.8_to_0.9 | 80 |
| uninsured_percentile | gt_0.9 | 47 |
| rucc | 1 | 109 |
| rucc | 2 | 131 |
| rucc | 3 | 96 |
| rucc | 4 | 66 |
| rucc | 5 | 22 |
| rucc | 6 | 124 |
| rucc | 7 | 59 |
| rucc | 8 | 112 |
| rucc | 9 | 91 |

Type 1: 447 counties (55.2% of the cohort) and 57.32 million people.
Median county population 36.9 thousand.
Median social-vulnerability percentile 0.79.
Median uninsured percentile 0.70.
Median rural-urban code 4.0. The most common code is medium metropolitan (code 2).
Most common blacklegged-tick status: Established.
Most common western-blacklegged-tick status: No records.
Most common pathogen status: No records.
Double-gap counties in this type: 70.
Nearest other prototype is 5.5072 on the mixed distance. Distinguishable: yes.
Counties closest to the prototype, not a ranking of disease: Campbell County, TN (47013; population 39397; vulnerability 0.71; uninsured 0.63; rural-urban code 2; wider gap only); Hoke County, NC (37093; population 52612; vulnerability 0.89; uninsured 0.69; rural-urban code 2; wider gap only); Burke County, GA (13033; population 24337; vulnerability 0.75; uninsured 0.65; rural-urban code 2; wider gap only).

Type 2: 363 counties (44.8% of the cohort) and 25.90 million people.
Median county population 27.4 thousand.
Median social-vulnerability percentile 0.28.
Median uninsured percentile 0.24.
Median rural-urban code 6.0. The most common code is large metropolitan (code 1). The most-rural call uses that median, so type 2 is the rural type even though many of its counties are large metropolitan.
Most common blacklegged-tick status: Established.
Most common western-blacklegged-tick status: No records.
Most common pathogen status: No records.
Double-gap counties in this type: 158.
Nearest other prototype is 5.5072 on the mixed distance. Distinguishable: yes.
Counties closest to the prototype, not a ranking of disease: Isle of Wight County, VA (51093; population 38898; vulnerability 0.22; uninsured 0.28; rural-urban code 1; wider gap only); Brown County, OH (39015; population 43715; vulnerability 0.37; uninsured 0.32; rural-urban code 1; wider gap only); Madison County, OH (39097; population 43961; vulnerability 0.20; uninsured 0.35; rural-urban code 1; wider gap only).

Double-gap counties assigned to a reported cluster: 228 of 228.

A published human count elsewhere on the atlas is a lower bound, not incidence.
No records and Unknown are not negatives. Missing is not zero.
Vintages differ across 2022, 2023, and 2025. No production score is published.

## Decision

Method keep. Product advance.
No revise or stop reason fired.
The product call does not authorize model promotion, a public map, or a PROD write.

## Reproduction and retained evidence

- Code revision/run/config/data references: fit commit `6ddbaf6260c656f221785876d02019090df37b8d` (the narrative commit on this branch follows it), run `120-gap-communities-20261026T1355Z`, spec `120-gap-communities/v1`.
- Entry points: `sql/validation/120_gap_communities.sql`, `scripts/eda_120_gap_communities.py`,
  `src/lyme_gap_atlas_ml/gap_communities.py`.
- Commands: `uv sync --locked --extra dev --extra snowflake`;
  `uv run python scripts/check_ml_agent_context.py`;
  `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_120_gap_communities.py`;
  `uv run python scripts/verify.py`.
- Lab row counts: REGISTRY.RUNS=1, EDA.METRICS_LONG=80, EDA.FINDINGS=3, EDA.GAP_COMMUNITY_ASSIGNMENTS_120=810, EXPERIMENTS.EXPERIMENTS=5, EXPERIMENTS.MODEL_METRICS=21, REGISTRY.QUERIES=3.
  SELECT grant recorded: true.
- Charts, folder [issue-120](https://drive.google.com/drive/folders/1H0Kv16kUBRRoJ_j7oTR379DWxaoNCdIq):
  [cohort-distributions.png](https://drive.google.com/file/d/1LHUpyPNxrOm4u8hEB8QvKA8EgOdctEKH/view)
  (9549 bytes; palette-quantized copy of the 26213-byte render,
  sha256 40d965c8d06ef13f432d16b3a53970cfc8b47f004657fa0f57ceb576c6a30adc;
  registered sha256 ba5f4dd07f2ac6fdff599a06490ddcab94cca27d53619fcd2eb929eb2fd1ac4a),
  [cluster-sizes.png](https://drive.google.com/file/d/1ZIRm87elf0wdxV627Ic3I1WLCUOfTsn2/view)
  (5760 bytes, sha256 fad476118d99132f945c20a6130cc02fd3216c2cd143d64039d8ebd9181c6ea5),
  [numeric-medians.png](https://drive.google.com/file/d/13BQQU5bSk40oLUX6XPXW-VujH-6V47W7/view)
  (7479 bytes, sha256 4864a783641981702d5c1a10d76498ee2fce696a222809af13e9c37de21ce350).
  Drive file sizes match the registered bytes. `REGISTRY.ARTIFACTS` has 3 rows for this run.
- Transient artifacts intentionally not committed: county assignment rows
  (ML Lab table only), chart PNGs under ignored `artifacts/charts/120/`,
  and any local query cache.
