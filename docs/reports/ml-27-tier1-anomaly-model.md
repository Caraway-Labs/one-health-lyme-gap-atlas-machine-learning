# ML #27 — Tier 1 county surveillance-review anomaly candidates

**Status:** Technical candidates for ML #30 evaluation; neither is selected.
**Purpose:** Identify unusual county surveillance/evidence profiles for epidemiologist review. Scores are not disease risk, incidence, diagnosis, causal effects, or calibrated probabilities.

## Pinned input and reproduction

The 2026-10-06 UTC read-only DEV run regenerated all 3,144 rows from `tier1-county-features-v1`, release `governed-2026-09-17-unknown-coverage`, bundle SHA-256 `55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`. It read only `PRESENTATION.CURRENT_RELEASE_V` and `PRESENTATION.CURRENT_COUNTY_ATLAS_V` after validating the read-only DEV user, role, database, and warehouse. No Snowflake write occurred. The six ordered predictors come directly from `tier1_features.FEATURE_COLUMNS`; FIPS, RUCC, evidence state, priority, and labels are excluded.

```powershell
$env:SNOWFLAKE_CONNECTION_NAME = '<approved read-only DEV connection>'
uv run python -m lyme_gap_atlas_ml.tier1_model --output-dir .local/ml-27
```

The command creates ignored `county-scores.csv`, `isolation-forest.joblib`, and `run-summary.json`. The latter records run time, run ID, source commit, release, predictor order, seed, configuration, diagnostic slices, and serialized artifact SHA-256. Regeneration from the pinned source is the durable reconstruction path; the generated model is a local artifact pending #30 review. The observed post-implementation run was `ml-27-20261006T040933Z` from code commit `8cf6284b95c68b9c2845849e252307701246b743`, artifact SHA-256 `021715cda001e88c470673300a76d57948822f1e7fe887973b1051e7cc40ce1e`.

## Methods

`tier1-statistical-reference-v1`: population-standardize human published-floor indicator, paired log1p human floor magnitude, pathogen modal-state mismatch indicator, and SVI percentile. Score is the square root of the mean of their four squared standardized values. Thus the three mutually exclusive pathogen columns contribute one domain term. Larger means more unusual. The published-floor count is a privacy-protected lower bound; 0.0 for no county-linked record remains a placeholder paired with the human evidence state.

`tier1-isolation-forest-v1`: scikit-learn Isolation Forest, 100 trees, seed 27, contamination `auto`, one job, all six ordered numeric predictors without scaling or imputation. Raw anomaly score is negative `score_samples`, so larger means more unusual. Both methods use average tied within-batch ranks mapped to 0–100 percentiles, higher meaning more unusual. No tier or product threshold is assigned.

## Live DEV sanity results

All 3,144 counties scored once per method; output duplicates and missing required fields: 0. No selected predictor was constant. Statistical-reference raw score min/median/max: **0.4431 / 0.7803 / 2.5400**; percentile **0 / 50 / 100**. Isolation Forest raw score: **0.4084 / 0.4462 / 0.7285**; percentile **0 / 50.03 / 100**. Top-ten overlap is **0** despite Pearson raw-score correlation **0.8093**.

Statistical reference top ten FIPS: `36103`, `42003`, `25023`, `42129`, `36119`, `42029`, `36071`, `34019`, `25027`, `42019`. Isolation Forest top ten FIPS: `02070`, `02290`, `02188`, `02180`, `02158`, `02050`, `02240`, `02063`, `02195`, `02105`.

| Slice | Statistical median percentile / top-ten | Forest median percentile / top-ten |
| --- | ---: | ---: |
| Human published floor, 651 | 89.66 / 10 | 85.87 / 0 |
| No county-linked human record, 2,493 | 39.64 / 0 | 39.52 / 10 |
| Pathogen Present, 689 | 87.81 / 10 | 81.34 / 0 |
| Pathogen No records, 2,420 | 38.48 / 0 | 38.48 / 0 |
| Pathogen Unknown, 35 | 73.72 / 0 | 99.46 / 10 |
| OBSERVED, 651 | 89.66 / 10 | 85.87 / 0 |
| PARTIAL, 2,493 | 39.64 / 0 | 39.52 / 10 |

**Critical #30 diagnostic:** All ten Forest top counties have rare `pathogen_unknown`, no county-linked human record, and PARTIAL feature evidence. The rare state is 35 of 3,144 counties, so this configuration's extreme ranks are dominated by missing/rare evidence. This is not evidence of biological absence, high burden, or an epidemiologic signal. The reference's top ten instead all have published human floors and Present pathogen status. RUCC was sliced as context: Forest top ten include eight RUCC 9, one RUCC 8, one RUCC 7; reference top ten include eight RUCC 1 and two RUCC 2. Full per-RUCC score and rank distributions are in the local run summary and reproducible by command above.

No model-derived causal reasons are claimed. The preserved human/pathogen/feature states provide descriptive evidence context; per-row prose reasons are deferred because the Forest's rare-state concentration makes a generic reason misleading. ML #30 should inspect this behavior and decide SELECT / REJECT / DEFER, including whether any candidate is suitable for tier policy. This report is technical sanity evidence, not epidemiologic validation or release approval.
