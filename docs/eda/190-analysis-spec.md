# ML #190 within-state documentation outliers: registered specification v1

- **Spec/version and owning issue:** `190-within-state-doc-outliers/v1`, [ML #190](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/190), parent [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway authorized this story through the standing directive sequenced by the orchestrator. This run does not change the Tier 1 model, the PROD batch, the tier policy, or the API contract. Nothing is exposed in a UI or an API.
- **Question / decision / allowed interpretation:** Which counties' documentation pattern differs most from their own state's counties, and is that flag stable across seeds and resamples? Does an isolation forest agree with, or add anything to, the within-state robust z from [#113](113-spatial-neighbor-outliers.md)? Are the flags explained by state size or by a state's own documentation mix? How do the flags relate to the [#120](120-gap-communities.md) community types and the [#121](121-county-contrasts.md) situation groups? The decision is keep, revise, or stop for the method, and advance, investigate, or stop for product value. A flag means documented differently from state peers. It is not a data error, not a validated detector, and not disease burden. Counts are surveillance signals and lower bounds where a floor is published (CDC floor 5). They are not incidence or causation. `No records` and `Unknown` are not negatives. A missing floor is not zero. No ground-truth labels exist.
- **Estimand:** On the pinned release, for each county in a state with at least 11 counties and a complete feature row, three within-state scores and their capped flags: the #113 robust-z baseline, an isolation forest, and a local outlier factor. Report flagged counts and shares by state and by state-size band, rank correlation and flagged-set overlap among the three methods, seed and bootstrap stability, the permutation check, and aggregate agreement with #120 types and #121 situation groups. Uncertainty for the primary forest flag rate is a state-cluster bootstrap percentile interval. County names and county-level numbers may appear in the lab flags table, the results write-up, the pull-request body, and the issue comment. Charts, other Drive files, and lab aggregate tables stay aggregate and suppress a cell whose denominator is below 11.

- **Unit / cohort / geography / time:** One county on the pinned atlas release, including the District of Columbia, Connecticut planning-region FIPS, Alaska, and Hawaii. The integrity gate is 3,144 rows, 3,144 distinct five-digit `FIPS`, 51 distinct `STATE` values, and one `RELEASE_ID`. Human surveillance is calendar 2023. Tick and pathogen statuses use the vintages on this release. Context vintages are the ones [#107](107-county-distributions.md) recorded. A state with fewer than 11 counties is not scored. Its counties are counted only in the aggregate band `below_11`.

- **Variables / source / version:** Execution reads `PRESENTATION.CURRENT_RELEASE_V` first and stops unless the pin is still release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. That identity was read on 2026-10-26 before this spec was frozen. Context check the same day: `prod_select` pass, `scratch_write` pass, `prod_write_denied` pass. Role `OH_LYME_ML_AGENT`, warehouse `OH_LYME_ML_LAB_XS_WH`, database `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`.

  County rows come from `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. Columns selected: `FIPS`, `COUNTY`, `STATE`, `RELEASE_ID`, `POPULATION`, `SVI_PERCENTILE`, `UNINSURED_PERCENTILE`, `RUCC_2023`, `HUMAN_STATUS`, `SCAPULARIS_STATUS`, `PACIFICUS_STATUS`, `BURGDORFERI_STATUS`, `TICK_STATUS`. `TICK_STATUS` is used only to rebuild the #121 situation labels and to recognize the #120 cohort. It is not a model column. No other atlas column is selected. Case floors, incidence floors, evidence completeness, geometry, payload, part text, and limitation text are not selected.

  [#120](120-gap-communities.md) community ids are read from `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.GAP_COMMUNITY_ASSIGNMENTS_120` for run `120-gap-communities-20261026T1355Z` (`FIPS`, `CLUSTER_ID` only). They are not features. [#121](121-county-contrasts.md) situation groups are recomputed from the status columns with the predicates in `county_mca._situation_flags`. The #121 axes are not read and not features. [#188](188-floor-presence-regime.md) is cited for the caveat that a state-level mix can look like a county signal. Its model is not refit.

- **Feature matrix, frozen before the fit:**

  | Column | Construction | Role |
  | --- | --- | --- |
  | `floor_present` | 1 when `HUMAN_STATUS` is `published_count_floor`, else 0 when it is `no_county_linked_record` | Documentation |
  | `scapularis_<level>` | One-hot of `SCAPULARIS_STATUS` | Documentation. Blacklegged tick |
  | `pacificus_<level>` | One-hot of `PACIFICUS_STATUS` | Documentation. Western blacklegged tick |
  | `burgdorferi_<level>` | One-hot of `BURGDORFERI_STATUS` | Documentation. Pathogen status |
  | `svi_percentile` | Numeric. If the column maximum is above 1.5, divide by 100 before the fit | Context |
  | `uninsured_percentile` | Same unit rule as SVI | Context |
  | `rucc_2023` | Integer 1 through 9, used as a number | Context |
  | `log_population` | Natural log of `POPULATION` | Context |

  Allowed species levels are `Established`, `Reported`, `No records`, and `Unknown`. Allowed pathogen levels are `Present`, `No records`, and `Unknown`. Any other human, species, or pathogen level stops the run. Levels are not collapsed. `No records` and `Unknown` stay separate.

  Excluded from the matrix: both case floors as numbers, evidence completeness, the Tier 1 score, any latent-class label, the September review tier, land cover, the #121 axes, and the #120 type.

- **Missingness rule:** Do not impute. Do not replace a gap with zero, Established, or Present. A county is incomplete, and not scored, when population is null or not positive, when either percentile is null, when the rural-urban code is null or not an integer from 1 through 9, or when any selected status is null. Incomplete counties still count toward the state size. A state is scored only when it has at least 11 counties and at least 11 complete rows. A duplicate `FIPS`, a `FIPS` that is not five digits, or a county count other than 3,144 stops the run.

- **Exploratory or confirmatory:** The release pin, the 3,144 / 51 gate, the feature list, the robust-z formula, the cap, the seeds, the bootstrap, the permutation, and the keep rule are confirmatory and frozen here. Annotated county examples in the write-up are illustrations. They are not a second screen. No threshold is changed after the live scores are seen.

- **Within-state standardization (robust, per state):** Import `MAD_SCALE` (`1.482602218505602`) and `Z_FLAG` (`3.5`) from `class_anomaly`, which is the same pair [#113](113-analysis-spec.md) uses. Do not retype a different constant. For each scored state, on its complete rows only:

  1. Location is the state median of that column.
  2. The #113 scale is `MAD_SCALE` times the median absolute deviation from that median. The robust z is `(value - median) / scale`.
  3. A column with a MAD of 0 is not estimable under #113. The baseline omits it. This is the #113 rule for a scale of 0, applied per state, without the #113 region shrink. The shrink uses other states, and this story's standardization is per state.
  4. Challenger matrix only: when the MAD is 0 and the column is not constant, the scale is `MAD_SCALE` times the mean absolute deviation from the state median. A constant column is omitted. The fallback exists because a documentation indicator with a minority of at most half the state has MAD 0, so the exact #113 scale cannot see it. The baseline does not use the fallback.
  5. The baseline score is the maximum absolute robust z across baseline columns. No estimable baseline column makes the score missing and the county unflagged by the baseline.
  6. States with fewer than 11 counties are not standardized and not scored.

- **Threshold and cap:** A county is eligible for the baseline flag when its baseline score is greater than `Z_FLAG` (3.5), on either tail. The cap is `max(1, floor(0.05 * n_complete))` counties per scored state. Among eligible counties, keep the highest scores, ties broken by `FIPS` ascending. If nobody exceeds 3.5, the state contributes zero baseline flags. The same cap is applied to each challenger after its own rule, so a large state cannot contribute more than about five percent of its complete counties. The cap is a maximum, not a target rate.

- **Challengers:** Fit inside each scored state on that state's challenger z matrix. Skip a state with fewer than two challenger columns.

  | Model | Settings |
  | --- | --- |
  | Isolation forest | scikit-learn `IsolationForest`, `n_estimators=100`, `contamination=0.05`, `bootstrap=True`, `max_samples="auto"`, `max_features=1.0`, `n_jobs=1`. Score is the negation of `decision_function` (larger means more unusual). The contamination rule marks outliers. The cap then keeps the highest scores among those marks. |
  | Local outlier factor | scikit-learn `LocalOutlierFactor`, `n_neighbors=min(20, n_complete - 1)`, `contamination=0.05`, `metric="euclidean"`, `algorithm="brute"`, `novelty=False`. Score is the negation of `negative_outlier_factor_`. The same cap keeps the highest scores among the contamination marks. LOF with `algorithm="brute"` does not use a seed. |

  No new dependency. The pinned environment already has scikit-learn.

- **Seeds:** Primary `1902026`. Second `1902027`. Both are passed as `random_state` to the isolation forest. A seed changes the result when the Spearman correlation of the two pooled score vectors, on counties scored by both, is below 0.999. On a standard-normal fixture with these settings the two seeds move the ranks (Spearman about 0.85) even when the capped flags match. The live run reports the live Spearman and does not search for a third seed. The state-cluster interval uses seed `1902030`. The within-state bootstrap uses seed `1902030`. The permutation uses seed `1902040`. Remaining nondeterminism: none beyond those generators and the floating-point order of the forest. `n_jobs` stays 1.

- **Bootstrap resampling:** Two procedures.

  1. **State-cluster interval.** Resample scored states with replacement, 400 draws, seed `1902030`. The statistic is the national primary-forest flag rate (flags divided by complete counties in the drawn states, weighted by their complete counts). Report the 2.5 and 97.5 percentiles. A draw with no complete counties is skipped. Fewer than 100 retained draws makes the interval not estimable. This interval resamples states. It is not a causal interval and not an AUC.
  2. **Within-state flag stability.** For each scored state, in state-code order, draw 20 subsamples of `floor(0.8 * n_complete)` counties without replacement, from `numpy.random.SeedSequence([1902030, state_index])`. Refit the baseline, the primary forest, and LOF. Compare each refit flag set with the original flags restricted to the subsample. If both sets are empty, skip the draw. If fewer than 10 draws remain, that state is omitted. The stability statistic is the unweighted median of the per-state median Jaccard.

- **Stability rule:** Seed Jaccard is the Jaccard of the two capped isolation-forest flag sets. The forest is seed-stable when that Jaccard is at least 0.80 and the score Spearman is below 0.999 (the seeds did change the scores). A method is bootstrap-stable when its median within-state Jaccard is at least 0.70. LOF has no seed Jaccard.

- **Permutation check:** 200 draws, seed `1902040`. Inside each scored state, shuffle the documentation columns jointly across complete counties. Context columns stay put. Refit the baseline scores and the capped baseline flags. Empty-versus-empty Jaccards are skipped. The documentation check passes when the median Jaccard with the original baseline flags is at most 0.50, meaning the shuffle moves who is flagged. It fails when the median is above 0.50: the flags stay put without the documentation pattern, so they are an artifact of the context columns or of a mix the baseline cannot see. Separately, for each method, compute the Spearman correlation of the state flag rate with the state county count, on scored states. The size check passes when the absolute correlation is below 0.50. Fewer than 11 scored states makes that correlation not estimable, and the size check does not pass. A method passes the permutation check only when the documentation check passes and its own size check passes. This is the guard named by [#188](188-floor-presence-regime.md): state-level composition can masquerade as a county signal.

- **What counts as a stable, useful flag:** All of the following.

  1. The county is complete and in a scored state.
  2. The primary forest flags it after the cap, and seed `1902027` flags it too.
  3. Its primary-forest bootstrap inclusion rate is at least 0.70. The rate is the share of retained subsamples that contain the county and flag it.
  4. On the challenger z matrix, the column with the largest absolute z is a documentation column (`floor_present` or a species or pathogen indicator). A tie at 1e-12 is not documentation.
  5. The forest passed the permutation check.

  If the permutation check fails, the stable-useful count is zero even when counties meet the other items. The write-up may name examples of primary-forest flags and must say whether they met this rule.

- **Agreement:** Spearman correlation of scores inside each scored state, then the complete-count-weighted mean across states where both scores have variation. Flagged-set Jaccard on the national sets, plus the matched-count Jaccard that takes the same number of highest scores from the other method, ties broken by `FIPS`. #121 agreement is the share of primary-forest flags in each situation group (`aligned`, `double_gap`, `wider_gap`, `human_ahead`, `undocumented`, `other`) against that group's share of scored counties. A county can meet both `double_gap` and `wider_gap`; report each predicate separately, not as a partition. #120 agreement is the share of primary-forest flags inside the stored gap-community cohort by `CLUSTER_ID`, against that cluster's share of the cohort. Do not compute ROC-AUC, PR-AUC, accuracy, or any other label-based detection metric. A high overlap with one situation is a description of the flag mix, not a validation. If a share looks extreme, say what mechanical feature of the cap or the one-hot coding produced it.

- **Method disposition, applied after the fit and not changed to chase a number:**

  | Call | Rule |
  | --- | --- |
  | keep | The forest is seed-stable and bootstrap-stable, it passes the permutation check, and at least 11 counties are stable useful flags |
  | revise | At least one scored state produces a primary-forest flag, and any keep condition fails |
  | stop | No state is scored, or the primary forest flags nobody |

  The baseline and LOF receive the same keep / revise / stop words in the write-up, using bootstrap stability, the permutation check, and, for the baseline, whether any baseline column was a documentation column. They do not replace the forest as the primary screen unless the forest is stop and the baseline is keep.

- **Product disposition:**

  | Call | Rule |
  | --- | --- |
  | advance | Method keep, the Jaccard of stable useful flags with the baseline flags is below 0.80, and no single #121 predicate holds more than 80 percent of the stable useful flags while that predicate covers under half of scored counties |
  | investigate | The method is keep or revise, and the flags are still a review list with the caveats below |
  | stop | The method is stop, or the permutation check fails and the stable-useful count is zero |

  Advance is permission to show a steward a short within-state review list. It is not permission to publish a score, retrain Tier 1, or treat a flag as a data error.

- **Spatial / temporal dependence:** Counties in one state share a reporting regime. The state-cluster interval and the within-state fit are the dependence controls. One snapshot is not a change over time. Human year 2023 and the context vintages are not one time base. No neighbor weights are used. [#113](113-spatial-neighbor-outliers.md) stopped the neighbor contrast.

- **Effect-size / uncertainty output:** Flag counts, flag shares, Jaccard values, Spearman correlations, the state-cluster percentile interval, and the permutation median Jaccard. No causal interval. No AUC.

- **Profile and chart rules:** No column profile of free text. `EDA.METRICS_LONG` stores aggregate rates, band shares, agreement, stability, and the permutation statistics. A row whose `n_underlying` is below 11 is suppressed by the existing writer. `EDA.FINDINGS` stores the method and product calls without a five-digit token and without a county name. Charts, each a PNG under about 20 KB, dpi about 64, Seaborn, no county names and no state names:

  | File | Content |
  | --- | --- |
  | `band-flag-share.png` | Flagged share by size band and method. A band with a flagged count from 1 to 10 is omitted |
  | `method-agreement.png` | Pairwise flagged-set Jaccard |
  | `stability.png` | Seed Jaccard and median bootstrap Jaccard |
  | `permutation-check.png` | Documentation-shuffle median Jaccard and the three size correlations |

  Size bands are `11_39`, `40_99`, and `100_plus`. The `below_11` band is reported as a county count and is not a flag share.

- **Small-cell and write rule:** Writers target only `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`. Inserts are insert-only and idempotent by `run_id`. A second invocation reuses the run id and does not insert again. No `DELETE`. New table `EDA.COUNTY_DOC_FLAGS_190` holds one row per county, including unscored counties, keyed by `RUN_ID` and `FIPS`. `GRANT SELECT` on that table to `OH_LYME_PROD_READ` is attempted once. The run then reads the grants and records whether that role has `SELECT`. A failed grant is recorded and is not retried as a stronger role. County rows stay in memory and in that table. They are not written to a file, to git, or to Drive.

- **Key caveat / stop conditions:** Stop if the context check, the release pin, or the 3,144 / 51 gate fails. Stop if an unexpected status level appears. A query still running at 10 minutes is cancelled. [#188](188-floor-presence-regime.md) showed that a state reporting mix can separate published floors from their absence even under a leakage-safe encoding. A within-state flag can still be the minority pattern of a state regime. The permutation check is the pre-registered protection. Passing it does not create ground truth. There is no labeled detector to validate.

- **Result disposition:** **PLANNED** before execution. After a clean run, apply the method and product tables above. Do not upgrade a call because a Jaccard or a share looks large.

- **Reproduction / evidence:** `sql/validation/190_doc_outliers.sql`, `src/lyme_gap_atlas_ml/doc_outliers.py`, `src/lyme_gap_atlas_ml/doc_outlier_report.py`, `src/lyme_gap_atlas_ml/snowflake/doc_outlier_flags.py`, `scripts/eda_190_doc_outliers.py`. Command: `MPLBACKEND=Agg uv run python scripts/eda_190_doc_outliers.py`. Tests: `uv run pytest tests/test_doc_outliers.py tests/test_doc_outlier_flags.py`. Full gate: `uv run python scripts/verify.py`. Durable record, after execution: `docs/eda/190-within-state-doc-outliers.md`. Run id pattern `190-within-state-doc-outliers-<UTC yyyymmddThhmmZ>`. Charts go to Drive folder `issue-190` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Transient outputs not committed: `artifacts/charts/190/` and `outputs/`.

## Out of scope

A production model, a model artifact outside the ML Lab, an API, a UI, a change to Tier 1 or the tier policy, a neighbor graph, a refit of #120 or #121 or #188, and any PROD write. The #188 chart registration requested by the ML Lead is a separate insert into `REGISTRY.ARTIFACTS` for run `188-floor-presence-regime-20261026T1522Z`. This story does not upload or edit those Drive files.
