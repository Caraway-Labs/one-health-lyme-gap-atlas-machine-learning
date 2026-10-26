# ML #188 published-floor presence: registered specification v1

- **Spec/version and owning issue:** `188-floor-presence-regime/v1`, [ML #188](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/188), program epic [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway's standing directive on 2026-10-25, relayed by the orchestrator on 2026-10-26, authorizes this supervised experiment. This run does not authorize a Tier 1 change, a PROD write, an API, a pipeline, a UI, or a public score.
- **Question / decision / allowed interpretation:** How well do county demographics alone separate counties with a published human floor from counties without one, and how much does a state reporting regime add once the held-out state's own county floors are kept out of that feature? The method decision is keep, revise, or stop. The product decision is advance, investigate, or stop. The outcome is a reporting label. It is not incidence, not a disease rate, and not a production score. `No records` and `Unknown` are not negatives. A missing floor is not zero. Predictions stay in the ML Lab.
- **Estimand:** On the pinned release, leave-state-out predicted probability of `HUMAN_STATUS = published_count_floor` for each county. Baseline features are the county's own SVI percentile, uninsured percentile, rural-urban category, and log population. The challenger adds one categorical regime id. The reported quantities are pooled out-of-fold ROC-AUC, average precision (PR-AUC), and Brier score for each model family and feature set; the state-cluster bootstrap interval on the challenger-minus-baseline lift; a second seed; a ten-bin calibration table; a per-state error table; and a permutation importance check. #123 supplies the publication-free regime definition and forbids the descriptive regime as a model feature. #121 axes, #120 community types, and the September review tier are not features. #107 and #109 supply the expected counts: 3,144 counties, 651 with a published floor, 2,493 without.

## Unit, cohort, and pin

One county on `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. The resampling and holdout unit is the postal state, including the District of Columbia (51 states). This is one snapshot. It is not a change contrast and not a forecast. Human surveillance is calendar 2023. SVI, uninsured percentile, and population are 2022. The rural-urban code is 2023. Tick and pathogen statuses, used only to rebuild the #123 publication-free regime, are cumulative through 2025-12-31. Those vintages are not one time base.

The context check for this story passed before this spec was frozen: `prod_select` pass, `scratch_write` pass, `prod_write_denied` pass, role `OH_LYME_ML_AGENT`, warehouse `OH_LYME_ML_LAB_XS_WH`, database `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`.

Pin, read before this spec was frozen, from `PRESENTATION.CURRENT_RELEASE_V`: release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. The same read, aggregate only, returned 3,144 counties, 3,144 distinct FIPS, 51 states, 651 published floors, 2,493 counties with no county-linked record, two human-status levels, and zero nulls in SVI percentile, uninsured percentile, population, rural-urban code, tick status, and pathogen status. SVI and uninsured percentiles already sit on 0 to 1 (max 1.0). Population ranges from 50 to 9,936,690. If a later execution sees different counts, the write-up says so. The fit still stops when the gates below fail.

Objects and columns read:

| Object | Columns |
| --- | --- |
| `PRESENTATION.CURRENT_RELEASE_V` | `RELEASE_ID`, `SCHEMA_VERSION`, `METHODOLOGY_VERSION`, `SCOPE`, `BUNDLE_SHA256` |
| `PRESENTATION.CURRENT_COUNTY_ATLAS_V` | `STATE`, `FIPS`, `RELEASE_ID`, `POPULATION`, `SVI_PERCENTILE`, `UNINSURED_PERCENTILE`, `RUCC_2023`, `HUMAN_STATUS`, `TICK_STATUS`, `BURGDORFERI_STATUS` |

No other column is selected. County rows and predictions stay in memory and in the ML Lab predictions table. They are not written to git, to a chart, or to Drive.

## Leakage rule (frozen before any fit)

The #123 descriptive regime is not a challenger feature. Its matrix includes `published_share` and the median published floor, so the held-out state's group is a function of that state's own county outcomes. Any model that uses the descriptive group id, a precomputed full-sample regime that was fit with those floors, the raw published floor, or the state's publication rate is descriptive only and is not fit.

The challenger feature is the #123 publication-free regime, rebuilt inside each leave-state-out fold. `publication_free_raw` in `state_regimes.py` is the only profile matrix. Its columns are the established-tick share, the pathogen-present share, and the nonmetropolitan share (`RUCC_2023` in 4 through 9). It does not include a floor, a publication share, or a median.

For each held-out state S, in postal-code order:

1. Build that three-column matrix for the other 50 states only.
2. Fit `StandardScaler` on those 50 rows only.
3. Fit Ward clustering with `AgglomerativeClustering(n_clusters=2, linkage="ward")` on the scaled rows. k=2 is the #123 publication-free cut. k is not searched again inside the fold.
4. Relabel the training groups to 1 and 2 by descending size, then by the first postal code in the group. That is the #123 relabel rule.
5. The centroid of a group is the mean of its scaled training rows.
6. Transform state S with the training scaler, using S's own three publication-free shares. Assign the nearest centroid. A tie goes to the smaller group id.
7. Training counties use their state's in-fold group id. Counties in S use S's assigned id. The fold model is fit only on the other states.

Tick status and pathogen status enter only through those three state shares. They are not separate county covariates. County rural-urban code remains in the baseline, so part of the regime is a state rural mix on top of the county's own code. That overlap is a caveat, not a reason to change the #123 profile.

### Leakage tests

1. **Label invariance.** For each state, flip every county published-floor indicator in that state, rebuild the profiles, and recompute the fold map. Every group id must match the unflipped map. A mismatch means the regime used the held-out state's floors. The challenger is then descriptive only, and its lift is not interpreted.
2. **Shuffled-label lift.** Permute the county outcome across counties with seed `1889001` (Fisher-Yates). Rebuild the regime with the same function and refit leave-state-out logistic regression at seed `1882026` for the baseline and the challenger. The absolute pooled ROC-AUC lift must be below 0.05. A larger value means the pipeline can manufacture a lift. The method decision is then revise.

## Features, models, folds, and seeds

Rows are sorted by FIPS before each fit. The split is leave-one-state-out: 51 folds, one postal state held out each time. There is no random county split.

SVI and uninsured percentiles use the #114 unit rule: if the maximum is greater than 1.5, divide that column by 100. Do not clip. On this pin both maxima are 1.0, so the rule does not rescale. A value outside 0 to 1 after that rule stops the fit. `log_population` is the natural log of `POPULATION`.

Inside each training fold, `StandardScaler` is fit on SVI, uninsured percentile, and log population. Rural-urban code is a one-hot of the integers 1 through 9, with a column kept even when a code is absent from the training fold. The challenger adds a one-hot of regime ids 1 and 2.

| Model | Frozen settings |
| --- | --- |
| L2 logistic regression | `LogisticRegression(C=1.0, l1_ratio=0.0, solver="lbfgs", max_iter=1000, random_state=seed)`. scikit-learn 1.9 treats `l1_ratio=0` as L2. No class weight. Class weights would move the Brier score. |
| Gradient-boosted trees | `HistGradientBoostingClassifier(max_iter=100, max_depth=3, learning_rate=0.1, min_samples_leaf=20, l2_regularization=1.0, early_stopping=False, random_state=seed)` |

Seeds: primary `1882026`, second `1882027`. Logistic regression is deterministic given FIPS order; the second seed must match the first within 1e-6 on ROC-AUC, PR-AUC, and Brier for both feature sets. The tree model may move. An absolute ROC-AUC change above 0.02 for either feature set fails the stability line.

Excluded from the design matrix and from SQL: both case floors (`CASE_COUNT_FLOOR_2023`, `INCIDENCE_FLOOR_2023`), `EVIDENCE_COMPLETENESS`, the Tier 1 score, any latent-class label, the #121 axes, the #120 community type, land cover, and the September review tier. The descriptive #123 group id is not fit.

## Metrics, bootstrap, calibration, importance, and what counts as a real lift

Pooled metrics use each county once, from the fold that held out its state. ROC-AUC, PR-AUC (average precision), and Brier score are the three metrics. The probability threshold 0.5 is used only for the per-state error count. It is not tuned.

The regime lift is challenger minus baseline. For Brier, a negative lift is an improvement. The interval is a state-cluster bootstrap of the out-of-fold predictions, not a refit. Draw 2,000 resamples of the 51 states with replacement, seed `1882030`, the same draws for every family, seed, and metric. A draw with one outcome class is a failure. The percentile index is `(n-1)*p` at 0.025 and 0.975, and the interval is not estimable when failures exceed 5 percent or fewer than two draws are finite. That is the #116 interval rule.

A **real lift** for a family, judged on the primary seed, requires all of the following:

- Both leakage tests pass.
- The ROC-AUC lift interval is estimable and its lower endpoint is greater than 0.01.
- The PR-AUC lift interval is estimable and its lower endpoint is greater than 0.
- The Brier lift interval (challenger minus baseline) is estimable and its upper endpoint is less than 0.005.

Calibration uses the primary seed. Ten equal-count bins of predicted probability. Each bin reports n, the lowest and highest probability, the mean predicted probability, and the observed published-floor share. A bin with n below 11 is omitted from charts and suppressed in lab metrics.

Permutation importance uses the primary-seed fold models without refitting. Thirty shuffles, seed `1882031`. Shuffle one raw column across counties, transform the held-out rows with the training scaler, and re-score. Importance is the unpermuted pooled ROC-AUC minus the mean permuted ROC-AUC. Columns: SVI, uninsured percentile, log population, rural-urban code, and, on the challenger only, the regime id. The regime id is constant inside a state, so the shuffle is across counties and can break that constant. That is intentional.

The per-state table aggregates counties. It reports county n, published n, Brier, mean predicted probability, and the count of counties whose probability is on the wrong side of 0.5, for both families and both feature sets, primary seed. States with fewer than 11 counties are included in the write-up and the issue comment, with the small n noted. Lab aggregate metrics suppress a geographic denominator below 11. No county row is written to a file, to git, or to Drive.

## Missingness and stop gates

Do not impute. A null SVI, uninsured percentile, population, rural-urban code, tick status, or pathogen status stops the fit. A non-positive or non-finite population stops the fit. A rural-urban code that is not an integer from 1 through 9 stops the fit. A human status other than `published_count_floor` or `no_county_linked_record` stops the fit. Tick and pathogen levels outside the #123 sets stop the fit. A duplicate or non-five-digit FIPS stops the fit. A county count other than 3,144, or a state count other than 51, stops the fit. A logistic fit that does not converge in 1,000 iterations stops the fit. A query still running at 10 minutes is cancelled.

Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Stop if the live release id, schema, methodology, scope, or bundle SHA differs from the pin. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or any column other than the list above.

## Result disposition

**PLANNED.** After the fit, apply this rule without changing it.

Method **stop** when a stop gate fails before a comparable pair of models exists. Method **keep** when every line below holds. Otherwise the method decision is **revise**.

- Label invariance holds for all 51 states.
- The shuffled-label absolute ROC-AUC lift is below 0.05.
- Both families finish both seeds, and the pooled metrics are finite.
- Logistic metrics match across seeds within 1e-6.
- The tree model's absolute ROC-AUC change across seeds is at most 0.02 for the baseline and for the challenger.
- The primary-seed bootstrap intervals for the three lifts are estimable for both families.

**Product call.** **stop** when the method decision is stop, and also when the method decision is keep and neither family has a real lift. **advance** when the method decision is keep and both families have a real lift. **investigate** otherwise, including a revise decision and a keep decision with exactly one real lift.

Advance does not publish a score, change a tier, or expose the prediction outside the ML Lab.

- **Reproduction / evidence:** SQL in `sql/validation/188_floor_presence.sql`. Runner `scripts/eda_188_floor_presence.py`. Fit logic `src/lyme_gap_atlas_ml/floor_presence.py`. Regime matrix reused from `src/lyme_gap_atlas_ml/state_regimes.py` (`publication_free_raw`). Lab writer `src/lyme_gap_atlas_ml/snowflake/floor_presence_predictions.py`. Run id pattern `188-floor-presence-regime-<UTC yyyymmddThhmmZ>`. Charts under git-ignored `artifacts/charts/188/`, each PNG kept under about 20 KB. Drive folder `issue-188` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/188-floor-presence-regime.md`. Writes are insert-only. A run id that already has lab rows is not written again. The role cannot `DELETE`. The writer attempts `GRANT SELECT` on the new lab table to `OH_LYME_PROD_READ` and records whether the grant succeeded.

  ```text
  uv sync --locked --extra dev --extra snowflake
  uv run python scripts/check_ml_agent_context.py
  MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_188_floor_presence.py
  uv run python scripts/verify.py
  ```
