# 188: Does a state reporting regime explain a missing published floor?

- Issue: [#188](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/188); program epic [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.
- Release: `governed-2026-10-15-january-climate-prod`.
- Cohort: 3144 counties, 51 states, one snapshot. Published floor 651. No county-linked record 2493. Counts matched the expected 651 and 2493.

## Method and assumptions

Spec [188-floor-presence-regime/v1](188-analysis-spec.md), frozen before the fit.
The regime feature is the #123 publication-free profile, rebuilt inside each
leave-state-out fold so the held-out state's own county floors are not an input.
The #123 descriptive groups are not fit. #121 axes and the #120 community type
are not features.

## Material findings and limits

1. Question

How well do county demographics alone separate a published human floor from its absence, and how much does the state reporting regime add once the held-out state's own floors are kept out of that feature?

2. Method (and why; link the spec)

Spec [188-floor-presence-regime/v1](docs/eda/188-analysis-spec.md), frozen before the fit. Leave-one-state-out on 51 states. Baseline: SVI percentile, uninsured percentile, rural-urban category, and log population. Challenger: baseline plus the #123 publication-free regime, Ward k=2, refit on the other states and assigned to the held-out state by the nearest training centroid. Logistic regression uses L2 with C=1.0. Trees use a depth-3 gradient booster with L2 regularization 1.0. Seeds 1882026 and 1882027. The lift interval resamples states 2000 times with seed 1882030. A real lift needs a ROC-AUC interval whose lower end is above 0.01, a PR-AUC interval above 0, and a Brier interval whose upper end is below 0.005, after the leakage tests pass.

3. Key findings with numbers

On the primary seed, logistic ROC-AUC is 0.8320 for demographics alone and 0.9164 with the leakage-safe regime (lift 0.0844, interval 0.0375 to 0.1380). The tree model moves from 0.8308 to 0.9055 (lift 0.0747, interval 0.0288 to 0.1273). Both families clear the frozen lift bar. The regime adds separation beyond the county profile. That is a reason to keep the feature in a later design discussion. It is not a score to publish.

| Family | Seed | Base AUC | Chal AUC | Base PR | Chal PR | Base Brier | Chal Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| logistic | 1882026 | 0.8320 | 0.9164 | 0.5519 | 0.6811 | 0.1232 | 0.0921 |
| logistic | 1882027 | 0.8320 | 0.9164 | 0.5519 | 0.6811 | 0.1232 | 0.0921 |
| gradient_boosting | 1882026 | 0.8308 | 0.9055 | 0.5517 | 0.6433 | 0.1232 | 0.0993 |
| gradient_boosting | 1882027 | 0.8308 | 0.9055 | 0.5517 | 0.6433 | 0.1232 | 0.0993 |

Logistic primary lifts, challenger minus baseline: ROC-AUC 0.0375 to 0.1380, PR-AUC 0.0441 to 0.2714, Brier -0.0585 to -0.0043.
Tree primary lifts: ROC-AUC 0.0288 to 0.1273, PR-AUC 0.0104 to 0.2263, Brier -0.0493 to 0.0015.

Label invariance: True. Shuffled-label logistic ROC-AUC lift, seed 1889001: 0.0003.
SVI rescaled by 100: False. Uninsured percentile rescaled by 100: False. Cohort matches 651 and 2493: True.

Permutation importance is the drop in pooled ROC-AUC after shuffling one column, primary seed, 30 draws, seed 1882031.

| Family | Feature set | Feature | Mean AUC drop |
| --- | --- | --- | ---: |
| logistic | baseline | svi_percentile | 0.0157 |
| logistic | baseline | uninsured_percentile | 0.1193 |
| logistic | baseline | log_population | 0.2320 |
| logistic | baseline | rucc | 0.0196 |
| logistic | challenger | svi_percentile | 0.0046 |
| logistic | challenger | uninsured_percentile | 0.0022 |
| logistic | challenger | log_population | 0.0942 |
| logistic | challenger | rucc | 0.0035 |
| logistic | challenger | regime | 0.2209 |
| gradient_boosting | baseline | svi_percentile | 0.0300 |
| gradient_boosting | baseline | uninsured_percentile | 0.1222 |
| gradient_boosting | baseline | log_population | 0.2175 |
| gradient_boosting | baseline | rucc | 0.0159 |
| gradient_boosting | challenger | svi_percentile | 0.0087 |
| gradient_boosting | challenger | uninsured_percentile | 0.0034 |
| gradient_boosting | challenger | log_population | 0.0764 |
| gradient_boosting | challenger | rucc | 0.0027 |
| gradient_boosting | challenger | regime | 0.2122 |

Calibration uses ten equal-count bins of predicted probability, primary seed. The share is the share with a published floor.

| Family | Feature set | Bin | n | Mean predicted | Observed share |
| --- | --- | ---: | ---: | ---: | ---: |
| logistic | baseline | 1 | 315 | 0.0082 | 0.0127 |
| logistic | baseline | 2 | 315 | 0.0212 | 0.0127 |
| logistic | baseline | 3 | 315 | 0.0382 | 0.0476 |
| logistic | baseline | 4 | 315 | 0.0611 | 0.0730 |
| logistic | baseline | 5 | 314 | 0.0952 | 0.1019 |
| logistic | baseline | 6 | 314 | 0.1451 | 0.1656 |
| logistic | baseline | 7 | 314 | 0.2163 | 0.2038 |
| logistic | baseline | 8 | 314 | 0.3220 | 0.3471 |
| logistic | baseline | 9 | 314 | 0.4703 | 0.4522 |
| logistic | baseline | 10 | 314 | 0.7097 | 0.6561 |
| logistic | challenger | 1 | 315 | 0.0060 | 0.0095 |
| logistic | challenger | 2 | 315 | 0.0120 | 0.0095 |
| logistic | challenger | 3 | 315 | 0.0184 | 0.0032 |
| logistic | challenger | 4 | 315 | 0.0269 | 0.0095 |
| logistic | challenger | 5 | 314 | 0.0395 | 0.0096 |
| logistic | challenger | 6 | 314 | 0.0726 | 0.0191 |
| logistic | challenger | 7 | 314 | 0.2191 | 0.2357 |
| logistic | challenger | 8 | 314 | 0.4472 | 0.4427 |
| logistic | challenger | 9 | 314 | 0.6351 | 0.5892 |
| logistic | challenger | 10 | 314 | 0.8287 | 0.7452 |

Tree calibration bins are stored in `EDA.METRICS_LONG` for this run.

Per-state errors use probability 0.5 on the primary seed. States with fewer than 11 counties are listed and marked small n. This write-up may show those counts. Lab aggregate tables suppress them.

| State | Counties | Published | Note | Logit base err | Logit chal err | Tree base err | Tree chal err | Logit base Brier | Logit chal Brier |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AK | 30 | 0 |  | 0 | 0 | 0 | 0 | 0.0066 | 0.0018 |
| AL | 67 | 1 |  | 2 | 1 | 2 | 1 | 0.0352 | 0.0122 |
| AR | 75 | 0 |  | 0 | 0 | 1 | 0 | 0.0243 | 0.0031 |
| AZ | 15 | 1 |  | 2 | 2 | 2 | 2 | 0.0945 | 0.0662 |
| CA | 58 | 6 |  | 22 | 39 | 20 | 40 | 0.2544 | 0.4489 |
| CO | 64 | 0 |  | 7 | 0 | 5 | 1 | 0.0780 | 0.0164 |
| CT | 9 | 9 | small n | 1 | 0 | 2 | 0 | 0.1135 | 0.0349 |
| DC | 1 | 1 | small n | 0 | 0 | 0 | 0 | 0.0294 | 0.0238 |
| DE | 3 | 3 | small n | 1 | 0 | 2 | 0 | 0.1659 | 0.0436 |
| FL | 67 | 16 |  | 18 | 21 | 17 | 23 | 0.1386 | 0.1992 |
| GA | 159 | 0 |  | 2 | 0 | 2 | 0 | 0.0142 | 0.0030 |
| HI | 5 | 0 | small n | 3 | 0 | 3 | 0 | 0.3555 | 0.0490 |
| IA | 99 | 8 |  | 15 | 8 | 13 | 8 | 0.1314 | 0.0532 |
| ID | 44 | 0 |  | 1 | 0 | 0 | 0 | 0.0312 | 0.0074 |
| IL | 102 | 13 |  | 16 | 55 | 28 | 54 | 0.1328 | 0.2891 |
| IN | 92 | 10 |  | 17 | 59 | 20 | 63 | 0.1371 | 0.3510 |
| KS | 105 | 0 |  | 1 | 0 | 2 | 0 | 0.0253 | 0.0043 |
| KY | 120 | 2 |  | 11 | 2 | 17 | 2 | 0.0894 | 0.0184 |
| LA | 64 | 0 |  | 1 | 0 | 2 | 0 | 0.0387 | 0.0006 |
| MA | 14 | 14 |  | 2 | 2 | 2 | 2 | 0.1116 | 0.0619 |
| MD | 24 | 24 |  | 11 | 4 | 8 | 5 | 0.2574 | 0.1307 |
| ME | 16 | 16 |  | 14 | 3 | 14 | 2 | 0.4980 | 0.1617 |
| MI | 83 | 44 |  | 31 | 30 | 35 | 34 | 0.2488 | 0.2126 |
| MN | 87 | 52 |  | 33 | 23 | 32 | 26 | 0.2528 | 0.1925 |
| MO | 115 | 0 |  | 3 | 0 | 4 | 1 | 0.0363 | 0.0075 |
| MS | 82 | 0 |  | 0 | 0 | 0 | 0 | 0.0054 | 0.0015 |
| MT | 56 | 0 |  | 4 | 0 | 3 | 0 | 0.0384 | 0.0058 |
| NC | 100 | 14 |  | 13 | 14 | 12 | 14 | 0.1040 | 0.1322 |
| ND | 53 | 0 |  | 3 | 0 | 4 | 0 | 0.0468 | 0.0054 |
| NE | 93 | 0 |  | 2 | 0 | 2 | 0 | 0.0273 | 0.0034 |
| NH | 10 | 10 | small n | 6 | 1 | 6 | 1 | 0.3179 | 0.1209 |
| NJ | 21 | 21 |  | 10 | 1 | 10 | 5 | 0.2890 | 0.0895 |
| NM | 33 | 0 |  | 1 | 0 | 0 | 0 | 0.0307 | 0.0041 |
| NV | 17 | 1 |  | 0 | 1 | 0 | 1 | 0.0338 | 0.0315 |
| NY | 62 | 62 |  | 24 | 9 | 16 | 9 | 0.2535 | 0.1374 |
| OH | 88 | 40 |  | 43 | 45 | 41 | 50 | 0.2879 | 0.2848 |
| OK | 77 | 0 |  | 0 | 0 | 0 | 0 | 0.0046 | 0.0018 |
| OR | 36 | 3 |  | 9 | 3 | 8 | 3 | 0.1299 | 0.0705 |
| PA | 67 | 67 |  | 35 | 14 | 30 | 14 | 0.3376 | 0.1550 |
| RI | 5 | 5 | small n | 2 | 0 | 0 | 0 | 0.1849 | 0.1156 |
| SC | 46 | 2 |  | 2 | 2 | 2 | 2 | 0.0392 | 0.0326 |
| SD | 66 | 0 |  | 1 | 0 | 0 | 0 | 0.0184 | 0.0018 |
| TN | 95 | 2 |  | 2 | 2 | 4 | 2 | 0.0339 | 0.0183 |
| TX | 254 | 0 |  | 5 | 0 | 8 | 4 | 0.0141 | 0.0072 |
| UT | 29 | 1 |  | 3 | 1 | 0 | 0 | 0.0825 | 0.0323 |
| VA | 133 | 65 |  | 56 | 37 | 60 | 40 | 0.3063 | 0.1876 |
| VT | 14 | 13 |  | 5 | 1 | 1 | 1 | 0.2310 | 0.1312 |
| WA | 39 | 0 |  | 9 | 0 | 11 | 0 | 0.1863 | 0.0069 |
| WI | 72 | 71 |  | 44 | 21 | 48 | 34 | 0.4104 | 0.2053 |
| WV | 55 | 54 |  | 52 | 41 | 50 | 34 | 0.6564 | 0.3730 |
| WY | 23 | 0 |  | 0 | 0 | 0 | 0 | 0.0133 | 0.0032 |

#123 publication-free groups were the profile allowed for a later county model. This is that model, with the regime rebuilt out of fold. The #123 descriptive groups stay out because they use the publication share. #121 county contrasts are not features. #120 community types are not features. #107 counted 19 states and 1,437 counties with no published county floor. A regime built from the state's own floors would look stronger than this leakage-safe feature.

4. Caveats

Counts are surveillance signals and lower bounds. The published floor starts at the CDC floor of 5. It is not a disease rate and not causation. No records and Unknown are not negatives. A missing floor is not zero. Predictions are not a risk score, not a production score, and not for a public page.
The regime still uses the state's tick-documentation share, pathogen-documentation share, and rural mix. County rural-urban code is already in the baseline, so some of the regime is a state rural summary. Human surveillance is calendar 2023. SVI, uninsured share, and population are 2022. Tick and pathogen status are cumulative through 2025-12-31. The state bootstrap does not cover dependence that crosses a state line.
Demographics move together, so permutation importance splits credit among correlated columns. The 0.5 error count is not a tuned operating point.

5. Disposition

Method: keep. Product: advance.
Leakage checks passed: True. Logistic real lift: True. Tree real lift: True.
Rule failures: none.

6. Artifacts

run_id: 188-floor-presence-regime-20261026T1522Z

Snowflake row counts: EDA.FINDINGS=2, EDA.METRICS_LONG=775, EXPERIMENTS.EXPERIMENTS=4, EXPERIMENTS.FLOOR_PRESENCE_PREDICTIONS_188=12576, EXPERIMENTS.MODEL_METRICS=36, REGISTRY.ARTIFACTS=1, REGISTRY.QUERIES=3, REGISTRY.RUNS=1.

SELECT grant on EXPERIMENTS.FLOOR_PRESENCE_PREDICTIONS_188 to OH_LYME_PROD_READ: pass.

The fit row indexes are integer arrays. This run_id was already written when that fix was in the committed code, and the Lab rows above were not inserted again.

Drive folder: https://drive.google.com/drive/folders/1neCph92p9zHU0lrrFGNzHEbLZfnCC7WG

`calibration-logistic.png` size-matched and registered. Drive file `1R-C5a3Q8atukaS5XVX-siJyY1aqxgZ1k`, https://drive.google.com/file/d/1R-C5a3Q8atukaS5XVX-siJyY1aqxgZ1k/view?usp=drivesdk, bytes 9225, sha256 `f673f8f21e6ef6e4bc5d73517526310e37b373e04da14a99123c8a955f105c76`.

Missing after two size mismatches, both Drive copies trashed:

- `lso-auc.png`, local bytes 5263, sha256 `0e2954029fabeeae81323d406cc29937d56e4dac42b55f93ec6676b35c709972`. Drive sizes were 5512 and 5512.
- `regime-lift.png`, local bytes 5325, sha256 `64dc42ded777b694205dae61965fb1d166fe1418e07f0b054903db9828e5bdad`. Drive sizes were 4967 and 4967.
- `permutation-importance.png`, local bytes 4960, sha256 `34abfb763cbff558d03fa764fba8752e56e8008e2c93bcf3825c89f4a3a555e4`. Drive sizes were 4961 and 4961.

The ML Lead can upload those three and register them when the Drive byte size and sha256 match the local files.

Doc: docs/eda/188-floor-presence-regime.md

Spec: docs/eda/188-analysis-spec.md

7. Reproducibility

Commit: c1b693e9c8fb0c6b2944a5e8c1f7bbbf63d0d226
Release: governed-2026-10-15-january-climate-prod
Seeds: logistic and trees 1882026 and 1882027; bootstrap 1882030; permutation 1882031; shuffled labels 1889001.
Counties in the fit: 3144. Expected counties 3144. scikit-learn 1.9.1.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_188_floor_presence.py
uv run python scripts/verify.py
```

## Decision

KEEP for the method. ADVANCE for product value. This is not a release, a tier change, or a production score.

## Reproduction and retained evidence

- Fit commit `c1b693e9c8fb0c6b2944a5e8c1f7bbbf63d0d226`, run `188-floor-presence-regime-20261026T1522Z`, release `governed-2026-10-15-january-climate-prod`.
- Entry points: `sql/validation/188_floor_presence.sql`,
  `scripts/eda_188_floor_presence.py`, `src/lyme_gap_atlas_ml/floor_presence.py`.
- Commands: see the reproducibility section above.
- Transient artifacts not committed: chart PNGs under ignored `artifacts/charts/188/`.
  No county extract.
