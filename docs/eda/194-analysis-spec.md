# ML #194 regime beyond tick geography: registered specification v1

- **Spec/version and owning issue:** `194-regime-vs-tick-geography/v1`, [ML #194](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/194), program epic [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway's standing directive on 2026-10-25, sequenced by the orchestrator on 2026-10-26 as the first follow-up to #188, authorizes this supervised experiment. This run does not authorize a Tier 1 change, a tier-policy change, a PROD write, an API, a pipeline, a UI, or a public score.
- **Question / decision / allowed interpretation:** After tick geography is already in the model, does the #123 publication-free state regime still add leave-state-out signal for a published county floor? The method decision is keep, revise, or stop. The product decision is advance, investigate, or stop. The outcome is a reporting label. It is not incidence, not a disease rate, and not a production score. `No records` and `Unknown` are not negatives. A missing floor is not zero. Case counts are lower bounds (CDC floor 5). The model predicts whether a published floor exists. Predictions stay in the ML Lab. A pass means the out-of-fold regime id adds held-out separation after the tick-geography features listed below. It does not mean the regime is a reporting culture separate from state pathogen mix or state rural mix: those two shares sit inside the #123 publication-free profile and are not covariates in model A.
- **Estimand:** On the pinned release, leave-state-out predicted probability of `HUMAN_STATUS = published_count_floor` for each county. Model A is tick geography only. Model B is the same features plus one categorical regime id. The reported quantities are pooled out-of-fold ROC-AUC, average precision (PR-AUC), and Brier score for each model family and feature set; the state-cluster bootstrap interval on the B-minus-A lift; a second seed; a ten-bin calibration table; the per-state ROC-AUC lift where both classes exist; and the shuffled-regime control. #188 supplies the folds, the context features, the model classes, and the out-of-fold regime assignment. #123 supplies the publication-free profile and forbids the descriptive regime as a model feature. #188's primary-seed logistic numbers are the comparison: demographics-only ROC-AUC 0.8320, demographics plus regime 0.9164, lift 0.0844, interval 0.0375 to 0.1380. The tree comparison is 0.8308 to 0.9055, lift 0.0747, interval 0.0288 to 0.1273. #107 and #109 supply the expected counts: 3,144 counties, 651 with a published floor, 2,493 without.

## Unit, cohort, and pin

One county on `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. The resampling and holdout unit is the postal state, including the District of Columbia (51 states). This is one snapshot. It is not a change contrast and not a forecast. Human surveillance is calendar 2023. SVI, uninsured percentile, and population are 2022. The rural-urban code is 2023. Tick and pathogen statuses are cumulative through 2025-12-31. Those vintages are not one time base.

The context check on 2026-10-26, before this spec was frozen, returned `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. User `OH_LYME_ML_AGENT_SVC`, role `OH_LYME_ML_AGENT`, database `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`, schema `SCRATCH`, warehouse `OH_LYME_ML_LAB_XS_WH`.

Pin, read before this spec was frozen, from `PRESENTATION.CURRENT_RELEASE_V`: release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. The same read, aggregate only, returned 3,144 counties, 3,144 distinct FIPS, 51 states, 651 published floors, 2,493 counties with no county-linked record, two human-status levels, and zero nulls in SVI percentile, uninsured percentile, population, rural-urban code, tick status, and pathogen status. SVI and uninsured percentiles already sit on 0 to 1 (max 1.0). Population ranges from 50 to 9,936,690. Tick levels are `Established` 1,404, `Reported` 490, `No records` 1,215, and `Unknown` 35. Pathogen levels are `Present` 689, `No records` 2,420, and `Unknown` 35. If a later execution sees different counts, the write-up says so. The fit still stops when the gates below fail.

Objects and columns read:

| Object | Columns |
| --- | --- |
| `PRESENTATION.CURRENT_RELEASE_V` | `RELEASE_ID`, `SCHEMA_VERSION`, `METHODOLOGY_VERSION`, `SCOPE`, `BUNDLE_SHA256` |
| `PRESENTATION.CURRENT_COUNTY_ATLAS_V` | `STATE`, `FIPS`, `RELEASE_ID`, `POPULATION`, `SVI_PERCENTILE`, `UNINSURED_PERCENTILE`, `RUCC_2023`, `HUMAN_STATUS`, `TICK_STATUS`, `BURGDORFERI_STATUS` |

No other column is selected. County rows and predictions stay in memory and in the ML Lab predictions table. They are not written to git, to a chart, or to Drive.

## Tick-geography feature set (model A)

Rows are sorted by FIPS before each fit. Model A uses only the columns below, in this order. Nothing derived from `HUMAN_STATUS`, either case floor, the state's publication rate, the #123 descriptive group, the Tier 1 score, or a latent-class label enters model A or model B.

Numeric columns, county-weighted `StandardScaler` fit on the training fold only, then applied to the held-out state:

1. `svi_percentile`
2. `uninsured_percentile`
3. `log_population`, the natural log of `POPULATION`
4. `state_tick_established_share`, defined in the next section

Categorical columns are one-hot. A level that is absent from the training fold still keeps its column. Levels and order:

| Feature | Levels |
| --- | --- |
| `RUCC_2023` | integers 1 through 9 |
| `TICK_STATUS` | `Established`, `Reported`, `No records`, `Unknown` |
| `BURGDORFERI_STATUS` | `Present`, `No records`, `Unknown` |

SVI and uninsured percentiles use the #114 unit rule: if the maximum is greater than 1.5, divide that column by 100. Do not clip. On this pin both maxima are 1.0, so the rule does not rescale. A value outside 0 to 1 after that rule stops the fit.

The #188 context block is the first three numerics plus the rural-urban one-hot. County tick status and county pathogen status are the county geography. The state tick share is the only state-level tick feature in model A. State pathogen share and state rural share are not model A covariates. They remain inside the regime profile only.

## State tick share, including a held-out state

For every postal state S, including a state that the current fold holds out:

- Denominator: the count of counties in S on this pin.
- Numerator: the count of those counties with `TICK_STATUS = Established`.
- `Reported`, `No records`, and `Unknown` stay in the denominator and out of the numerator.
- The share is one number for the whole state. It is not leave-one-county-out. Every county in S receives that same share.
- Inputs are `STATE` and `TICK_STATUS` only. `HUMAN_STATUS`, `CASE_COUNT_FLOOR_2023`, `INCIDENCE_FLOOR_2023`, publication share, and the median published floor are not inputs. A held-out state's own floors are not used. The held-out state's own tick statuses are used, because tick status is geography and not the outcome.
- The share is computed once from the full state, before the fold loop. It does not change when the fold changes, and it does not change when published-floor labels are flipped.

A share of zero is a real share. It is not an imputed floor. Do not fill a tick status with `Established`.

## Regime encoding and out-of-fold assignment (model B)

Model B appends a one-hot of regime ids 1 and 2 to model A. The #123 descriptive regime is not a feature. Its matrix includes `published_share` and the median published floor.

The regime is the #188 out-of-fold assignment. Reuse `state_profiles`, `out_of_fold_regimes`, and the fold assignment in `src/lyme_gap_atlas_ml/floor_presence.py`, which calls `publication_free_raw` in `src/lyme_gap_atlas_ml/state_regimes.py`. Do not refit k. Do not use a full-sample regime that was fit with the held-out state present.

`publication_free_raw` columns, in order, are the established-tick share, the pathogen-present share, and the nonmetropolitan share (`RUCC_2023` in 4 through 9). The matrix does not include a floor, a publication share, or a median. The tick share inside that matrix is the same state tick share defined above.

For each held-out state S, in postal-code order, the #188 rule stands:

1. Build that three-column matrix for the other 50 states only.
2. Fit `StandardScaler` on those 50 rows only.
3. Fit Ward clustering with `AgglomerativeClustering(n_clusters=2, linkage="ward")` on the scaled rows. k=2 is the #123 publication-free cut.
4. Relabel the training groups to 1 and 2 by descending size, then by the first postal code in the group.
5. The centroid of a group is the mean of its scaled training rows.
6. Transform state S with the training scaler, using S's own three publication-free shares. Assign the nearest centroid. A tie goes to the smaller group id.
7. Training counties use their state's in-fold group id. Counties in S use S's assigned id. The fold model is fit only on the other states.

The regime id is constant inside a state within a fold. Training ids may differ from the id a state receives when that state is itself held out. Scoring uses the id from the fold that held the county's state out.

## Leakage tests

1. **Label invariance.** For each state, flip every county published-floor indicator in that state and rebuild state tick shares, county tick and pathogen codes, and the fold regime map. Every tick share, every county tick code, every county pathogen code, and every regime id must match the unflipped values. A mismatch means a feature used the held-out state's floors. Model B is then descriptive only, and its lift is not interpreted.
2. **Shuffled-regime control.** Build the real fold maps first. Let `r(S)` be the regime id assigned to S in the fold that holds S out. Permute the 51 postal states with Fisher-Yates, seed `1949001`. State S receives `r` of the state in its permuted position. That shuffled id replaces the regime id of S in every fold, for training rows and for the held-out rows, so the id stays constant inside the state. Do not refit Ward on the shuffled ids. Refit leave-state-out logistic regression at seed `1942026` for model A and for model B with the shuffled ids. Model A must match the unshuffled model A at that seed within 1e-6 on ROC-AUC, because the shuffle does not touch tick geography. The absolute pooled ROC-AUC lift of shuffled model B minus model A must be below 0.05. A larger value means a regime-shaped feature can manufacture a lift. The method decision is then revise.

The #188 shuffled-label refit is not repeated. The publication-free regime does not read the label, so shuffling labels cannot move the regime. The control that can invent a regime lift is the shuffled regime id.

## Folds, models, and seeds

The split is leave-one-state-out: 51 folds, one postal state held out each time. There is no random county split. The fold list and the regime maps are the #188 maps on this pin.

| Model | Frozen settings |
| --- | --- |
| L2 logistic regression | `LogisticRegression(C=1.0, l1_ratio=0.0, solver="lbfgs", max_iter=1000, random_state=seed)`. scikit-learn 1.9 treats `l1_ratio=0` as L2. No class weight. Class weights would move the Brier score. Report this family first. |
| Gradient-boosted trees | `HistGradientBoostingClassifier(max_iter=100, max_depth=3, learning_rate=0.1, min_samples_leaf=20, l2_regularization=1.0, early_stopping=False, random_state=seed)`. One robustness check. It does not replace the logistic pass rule. |

Seeds: primary `1942026`, second `1942027`. Logistic regression is deterministic given FIPS order; the second seed must match the first within 1e-6 on ROC-AUC, PR-AUC, and Brier for both feature sets. The tree model may move. An absolute ROC-AUC change above 0.02 for either feature set fails the stability line.

Excluded from the design matrix and from SQL: both case floors (`CASE_COUNT_FLOOR_2023`, `INCIDENCE_FLOOR_2023`), `EVIDENCE_COMPLETENESS`, the Tier 1 score, any latent-class label, the #121 axes, the #120 community type, land cover, the September review tier, state pathogen share as its own column, and state rural share as its own column. The descriptive #123 group id is not fit.

## Metrics, lift interval, calibration, and the pass rule

Pooled metrics use each county once, from the fold that held out its state. ROC-AUC, PR-AUC (average precision), and Brier score are the three metrics. The probability threshold 0.5 is not tuned and is not a reported operating point.

The regime lift is model B minus model A. For Brier, a negative lift is an improvement. The interval is a state-cluster bootstrap of the out-of-fold predictions, not a refit. Draw 2,000 resamples of the 51 states with replacement, seed `1942030`, the same draws for every family, seed, and metric. A draw with one outcome class is a failure. The percentile index is `(n-1)*p` at 0.025 and 0.975, and the interval is not estimable when failures exceed 5 percent or fewer than two draws are finite. That is the #116 interval rule used by #188.

**Pass rule for "regime adds signal beyond tick geography".** Judge the logistic family on the primary seed. All of the following are required:

- Label invariance holds.
- The shuffled-regime absolute ROC-AUC lift is below 0.05.
- The ROC-AUC lift interval is estimable and its lower endpoint is greater than 0.01.
- The PR-AUC lift interval is estimable and its lower endpoint is greater than 0.
- The Brier lift interval (model B minus model A) is estimable and its upper endpoint is less than 0.005.

The tree family is reported with the same three intervals. It is not part of this pass sentence. A tree interval whose upper ROC-AUC endpoint is below 0 contradicts the logistic pass and blocks product advance.

Calibration uses the primary seed, both families, both feature sets. Ten equal-count bins of predicted probability. Each bin reports n, the lowest and highest probability, the mean predicted probability, and the observed published-floor share. A bin with n below 11 is omitted from charts and suppressed in lab metrics.

Per-state lift uses the primary seed. For each state whose held-out counties contain both outcome classes, the lift is that state's ROC-AUC for model B minus its ROC-AUC for model A, separately for each family. A state with one class has a lift that is not estimable. The distribution summary, on states with at least 11 counties and an estimable lift, is the count of such states, the median lift, and the count whose lift is positive. States with fewer than 11 counties are included in the write-up and the pull-request body, with the small n noted. Lab aggregate metrics suppress a geographic denominator below 11. No county row is written to a file, to git, or to Drive. Charts do not print a county or a state name.

## Missingness and stop gates

Do not impute. A null SVI, uninsured percentile, population, rural-urban code, tick status, or pathogen status stops the fit. A non-positive or non-finite population stops the fit. A rural-urban code that is not an integer from 1 through 9 stops the fit. A human status other than `published_count_floor` or `no_county_linked_record` stops the fit. Tick and pathogen levels outside the sets above stop the fit. A duplicate or non-five-digit FIPS stops the fit. A county count other than 3,144, or a state count other than 51, stops the fit. A logistic fit that does not converge in 1,000 iterations stops the fit. A query still running at 10 minutes is cancelled.

Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Stop if the live release id, schema, methodology, scope, or bundle SHA differs from the pin. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, `CONFORMED_CDC_LYME_QTBI_XD4I`, `CDC_HISTORICAL_VALIDATED_SNAPSHOTS`, or any column other than the list above.

## Result disposition

**PLANNED.** After the fit, apply this rule without changing it. A disappeared lift is a valid result. Do not loosen the 0.01 bar, the shuffled-regime bar, or the feature list after seeing the metrics.

Method **stop** when a stop gate fails before a comparable pair of models exists. Method **keep** when every line below holds. Otherwise the method decision is **revise**.

- Label invariance holds for all 51 states, for tick shares and for regime ids.
- The shuffled-regime absolute ROC-AUC lift is below 0.05, and shuffled model A matches unshuffled model A within 1e-6 on ROC-AUC.
- Both families finish both seeds, and the pooled metrics are finite.
- Logistic metrics match across seeds within 1e-6.
- The tree model's absolute ROC-AUC change across seeds is at most 0.02 for model A and for model B.
- The primary-seed bootstrap intervals for the three lifts are estimable for both families.

**Product call.** **stop** when the method decision is stop. **stop** also when the method decision is keep and the logistic pass rule fails, including a lift whose interval does not clear the frozen bar. Say in the write-up whether the point lift is near zero, negative, or positive but below the bar. **advance** when the method decision is keep, the logistic pass rule holds, and the tree model's primary-seed ROC-AUC lift interval has a lower endpoint greater than 0. **investigate** otherwise, including a revise decision and a logistic pass whose tree interval does not stay positive.

Advance does not publish a score, change a tier, change the Tier 1 national model, or expose the prediction outside the ML Lab. It does not authorize stories #172, #173, or #127.

- **Reproduction / evidence:** SQL in `sql/validation/194_regime_tick_geography.sql` (same two statements as #188: release identity, then the county columns listed above, ordered by FIPS). Runner `scripts/eda_194_regime_tick_geography.py`. Fit logic `src/lyme_gap_atlas_ml/regime_tick_geography.py`, calling the #188 regime functions rather than a second clustering implementation. Lab writer `src/lyme_gap_atlas_ml/snowflake/regime_tick_predictions.py`. Predictions table `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.REGIME_VS_TICK_GEOGRAPHY_194` (county rows stay in the Lab). Insert-only, keyed by `run_id`. A run id that already has lab rows is not written again. The role cannot `DELETE`. The writer grants `SELECT` on that table to `OH_LYME_PROD_READ` and `OH_LYME_ML_LAB_READ` and records each grant. Run id pattern `194-regime-vs-tick-geography-<UTC yyyymmddThhmmZ>`. `REGISTRY.RUNS` stores issue number 194, the source release id, the two source objects, the primary seed, and the parameters (spec id, both seeds, bootstrap seed, shuffle seed, feature list). `finished_at` is set when the run row is written after a finished fit. `EDA.METRICS_LONG` suppresses `n < 11`. `EDA.FINDINGS`, `EXPERIMENTS.EXPERIMENTS`, `EXPERIMENTS.MODEL_METRICS`, and `REGISTRY.QUERIES` (every PROD query) are written in the same run. Charts under git-ignored `artifacts/charts/194/`, seaborn/matplotlib, about 64 dpi, each PNG under about 20 KB, no county or state names. Drive folder `issue-194` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/194-regime-vs-tick-geography.md`. Tests use made-up FIPS and state codes only.

  ```text
  uv sync --locked --extra dev --extra snowflake
  uv run python scripts/check_ml_agent_context.py
  MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_194_regime_tick_geography.py
  uv run python scripts/verify.py
  ```
