# 194: Does the state regime add signal beyond tick geography?

- Issue: [#194](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/194); program epic [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.
- Release: `governed-2026-10-15-january-climate-prod`.
- Cohort: 3144 counties, 51 states, one snapshot. Published floor 651. No county-linked record 2493. Counts matched the expected 651 and 2493.

## Method and assumptions

Spec [194-regime-vs-tick-geography/v1](194-analysis-spec.md), frozen before the fit.
Model A is state tick-established share, county tick status, county pathogen
status, and the #188 context features. Model B adds the #188 out-of-fold
publication-free regime. A held-out state's tick share uses that state's tick
statuses and does not use its floors. The descriptive #123 groups are not fit.

## Material findings and limits

1. Question

Does the publication-free state regime still separate a published county floor
from its absence after tick geography is already in the model?

2. Method (and why; link the spec)

Spec [194-regime-vs-tick-geography/v1](docs/eda/194-analysis-spec.md), frozen before the fit.
Leave-one-state-out on 51 states, the same folds and out-of-fold regime
assignment as #188. Model A: state tick-established share, county tick status,
county pathogen status, SVI percentile, uninsured percentile, rural-urban code,
and log population. Model B adds the regime id. Logistic regression is L2 with
C=1.0. Trees are a depth-3 gradient booster. Seeds 1942026 and
1942027. The lift interval resamples states 2000 times
with seed 1942030. The shuffled-regime control uses seed 1949001.
A pass needs a ROC-AUC interval whose lower end is above 0.01, a PR-AUC interval
above 0, and a Brier interval whose upper end is below 0.005, after the leakage
tests pass.

3. Key findings with numbers

On the primary seed, logistic ROC-AUC is 0.9163 for tick geography and 0.9212 with the regime (lift 0.0049, interval -0.0105 to 0.0231). The tree model moves from 0.9035 to 0.9071 (lift 0.0036, interval -0.0077 to 0.0156). The regime lift disappears once tick geography is in the model. The #188 gain over demographics is consistent with the regime restating tick geography. That is a reason to stop treating the regime as extra signal.

| Family | Seed | Tick AUC | Regime AUC | Tick PR | Regime PR | Tick Brier | Regime Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| logistic | 1942026 | 0.9163 | 0.9212 | 0.6297 | 0.6285 | 0.0949 | 0.0941 |
| gradient_boosting | 1942026 | 0.9035 | 0.9071 | 0.6793 | 0.6860 | 0.1183 | 0.1203 |
| logistic | 1942027 | 0.9163 | 0.9212 | 0.6297 | 0.6285 | 0.0949 | 0.0941 |
| gradient_boosting | 1942027 | 0.9035 | 0.9071 | 0.6793 | 0.6860 | 0.1183 | 0.1203 |

Logistic primary lifts, regime minus tick geography: ROC-AUC -0.0105 to 0.0231, PR-AUC -0.0203 to 0.0200, Brier -0.0070 to 0.0040.
Tree primary lifts: ROC-AUC -0.0077 to 0.0156, PR-AUC -0.0173 to 0.0251, Brier -0.0059 to 0.0119.

Label invariance: True. Shuffled-regime logistic ROC-AUC lift, seed 1949001: 0.0085. Shuffled model A ROC-AUC gap: 0.000000. SVI rescaled by 100: False. Uninsured percentile rescaled by 100: False. Cohort matches 651 and 2493: True.

Per-state ROC-AUC lift, primary seed, states with at least 11 counties and both outcome classes. logistic: 21 states, median lift 0.0000, positive lifts 6. gradient_boosting: 21 states, median lift 0.0000, positive lifts 7.

#188 logistic ROC-AUC moved from 0.8320 to 0.9164 (lift 0.0844, interval 0.0375 to 0.1380) when the regime was added to demographics only. The tree comparison was 0.8308 to 0.9055 (lift 0.0747, interval 0.0288 to 0.1273). This story's model A already contains the state tick share that #188 folded into the regime.

Per-state ROC-AUC on the primary seed. A blank AUC means the state has one outcome class. States with fewer than 11 counties are listed and marked small n. This write-up may show those counts. Lab aggregate tables suppress them.

| State | Counties | Published | Note | Logit tick AUC | Logit regime AUC | Logit lift | Tree lift |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| AK | 30 | 0 |  |  |  |  |  |
| AL | 67 | 1 |  | 1.0000 | 1.0000 | 0.0000 | -0.0000 |
| AR | 75 | 0 |  |  |  |  |  |
| AZ | 15 | 1 |  | 0.7857 | 0.7857 | 0.0000 | 0.0000 |
| CA | 58 | 6 |  | 0.9167 | 0.9167 | 0.0000 | 0.0000 |
| CO | 64 | 0 |  |  |  |  |  |
| CT | 9 | 9 | small n |  |  |  |  |
| DC | 1 | 1 | small n |  |  |  |  |
| DE | 3 | 3 | small n |  |  |  |  |
| FL | 67 | 16 |  | 0.8346 | 0.8346 | 0.0000 | 0.0000 |
| GA | 159 | 0 |  |  |  |  |  |
| HI | 5 | 0 | small n |  |  |  |  |
| IA | 99 | 8 |  | 0.9423 | 0.9409 | -0.0014 | -0.0055 |
| ID | 44 | 0 |  |  |  |  |  |
| IL | 102 | 13 |  | 0.9421 | 0.9464 | 0.0043 | -0.0082 |
| IN | 92 | 10 |  | 0.6805 | 0.6817 | 0.0012 | 0.0207 |
| KS | 105 | 0 |  |  |  |  |  |
| KY | 120 | 2 |  | 0.9576 | 0.9576 | 0.0000 | -0.0042 |
| LA | 64 | 0 |  |  |  |  |  |
| MA | 14 | 14 |  |  |  |  |  |
| MD | 24 | 24 |  |  |  |  |  |
| ME | 16 | 16 |  |  |  |  |  |
| MI | 83 | 44 |  | 0.8421 | 0.8380 | -0.0041 | 0.0032 |
| MN | 87 | 52 |  | 0.8901 | 0.8907 | 0.0005 | 0.0052 |
| MO | 115 | 0 |  |  |  |  |  |
| MS | 82 | 0 |  |  |  |  |  |
| MT | 56 | 0 |  |  |  |  |  |
| NC | 100 | 14 |  | 0.8397 | 0.8397 | 0.0000 | -0.0129 |
| ND | 53 | 0 |  |  |  |  |  |
| NE | 93 | 0 |  |  |  |  |  |
| NH | 10 | 10 | small n |  |  |  |  |
| NJ | 21 | 21 |  |  |  |  |  |
| NM | 33 | 0 |  |  |  |  |  |
| NV | 17 | 1 |  | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| NY | 62 | 62 |  |  |  |  |  |
| OH | 88 | 40 |  | 0.7104 | 0.7203 | 0.0099 | 0.0833 |
| OK | 77 | 0 |  |  |  |  |  |
| OR | 36 | 3 |  | 0.8182 | 0.8283 | 0.0101 | -0.0101 |
| PA | 67 | 67 |  |  |  |  |  |
| RI | 5 | 5 | small n |  |  |  |  |
| SC | 46 | 2 |  | 0.9886 | 0.9886 | 0.0000 | 0.0000 |
| SD | 66 | 0 |  |  |  |  |  |
| TN | 95 | 2 |  | 0.9624 | 0.9624 | 0.0000 | 0.0054 |
| TX | 254 | 0 |  |  |  |  |  |
| UT | 29 | 1 |  | 0.9643 | 0.9643 | 0.0000 | 0.0000 |
| VA | 133 | 65 |  | 0.7511 | 0.7600 | 0.0088 | 0.0052 |
| VT | 14 | 13 |  | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| WA | 39 | 0 |  |  |  |  |  |
| WI | 72 | 71 |  | 0.8592 | 0.8592 | 0.0000 | -0.0704 |
| WV | 55 | 54 |  | 0.8704 | 0.8519 | -0.0185 | 0.0185 |
| WY | 23 | 0 |  |  |  |  |  |

4. Caveats

Counts are surveillance signals and lower bounds. The published floor starts at
the CDC floor of 5. It is not a disease rate and not causation. No records and
Unknown are not negatives. A missing floor is not zero. Predictions are not a
risk score, not a production score, and not for a public page.
The regime still uses the state's tick-documentation share, pathogen-documentation
share, and rural mix. Model A already has the state tick share and the county
pathogen status, so a remaining lift can be state pathogen mix, state rural mix,
or the cluster label. It is not a separate reporting culture. Human surveillance
is calendar 2023. SVI, uninsured share, and population are 2022. Tick and pathogen
status are cumulative through 2025-12-31. The state bootstrap does not cover
dependence that crosses a state line.

5. Disposition

Method: keep. Product: stop. Leakage checks passed: True. Logistic pass rule: False. Tree ROC-AUC interval stays positive: False. Rule failures: none.

6. Artifacts

run_id: 194-regime-vs-tick-geography-20261026T2106Z

Snowflake row counts: EDA.FINDINGS=2, EDA.METRICS_LONG=192, EDA.REGIME_VS_TICK_GEOGRAPHY_194=12576, EXPERIMENTS.EXPERIMENTS=4, EXPERIMENTS.MODEL_METRICS=36, REGISTRY.ARTIFACTS=0, REGISTRY.QUERIES=3, REGISTRY.RUNS=1.

SELECT grants on EDA.REGIME_VS_TICK_GEOGRAPHY_194: OH_LYME_PROD_READ=pass,OH_LYME_ML_LAB_READ=pass.

Drive folder `issue-194`: https://drive.google.com/drive/folders/1YBfRG8fsEkuZPAI9PaVyJLoGNgemfpau

The AUC chart upload did not match. Drive stored `auc-comparison.png` as 4904 bytes (file id `1Q4iaAudZzlCR-VCVTrnna2I1LVqK-lGz`); the local file is 4913 bytes, sha256 `a444a359c76dd844b24041bb18262da4065cd5d057315339276909696317f6af`. The copy was not registered. Trashing it was refused because the file is shared. The other three charts were not uploaded. `REGISTRY.ARTIFACTS` has no row for this run.

Local charts, git-ignored `artifacts/charts/194/`:

- `auc-comparison.png` bytes 4913, sha256 `a444a359c76dd844b24041bb18262da4065cd5d057315339276909696317f6af`
- `regime-lift.png` bytes 6511, sha256 `383406d4a32bf257b853550ea67dae916630342922a44e90dfa23a08e0fc95bc`
- `calibration-logistic.png` bytes 11287, sha256 `dc027037fcebb6a350f21dc930df6bd621bba770e65a43b7056588129ff54e66`
- `state-lift-hist.png` bytes 8590, sha256 `b12b7e2321bd723d5cd9be730467c417ff7812d6c126bb84075f67913f6bb6de`

The state-lift chart omits the bin from 0 to 0.10 because that bin holds 6 states. Fifteen states sit in the bin from -0.10 to 0.

Doc: docs/eda/194-regime-vs-tick-geography.md

Spec: docs/eda/194-analysis-spec.md

7. Reproducibility

Commit: 8528b1ae9f6999547ac2e7e774fe41d4cbdf30ac
Release: governed-2026-10-15-january-climate-prod
Seeds: logistic and trees 1942026 and 1942027; bootstrap 1942030; shuffled regime 1949001.
Counties in the fit: 3144. Expected counties 3144. scikit-learn 1.9.1.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_194_regime_tick_geography.py
uv run python scripts/verify.py
```

## Decision

KEEP for the method. STOP for product value. This is not a release, a tier change, or a production score.

## Reproduction and retained evidence

- Fit commit `8528b1ae9f6999547ac2e7e774fe41d4cbdf30ac`, run `194-regime-vs-tick-geography-20261026T2106Z`, release `governed-2026-10-15-january-climate-prod`.
- Entry points: `sql/validation/194_regime_tick_geography.sql`,
  `scripts/eda_194_regime_tick_geography.py`,
  `src/lyme_gap_atlas_ml/regime_tick_geography.py`.
- Commands: see the reproducibility section above.
- Transient artifacts not committed: chart PNGs under ignored
  `artifacts/charts/194/`. No county extract.
