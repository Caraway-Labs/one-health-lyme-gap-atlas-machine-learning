# 114: Which cross-domain signals move together?

- Issue: [ML #114](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/114), part of [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
  Spec: [114-cross-domain/v1](114-analysis-spec.md).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.
  Pinned release `governed-2026-10-15-january-climate-prod`.
- Cohort: 3144 counties. Published floor 651. No county-linked record 2493. Context complete case 3144. Cross-domain complete case 3109.

## Method and assumptions

Spec [114-cross-domain/v1](114-analysis-spec.md), frozen before the fit.
The descriptive unit is the county. The resampling unit is the state.
Spearman and the state-cluster interval come from `test_selection`.
Kruskal epsilon-squared comes from `eda63.omnibus`.
Bias-corrected Cramér's V uses the chi-square from `cramers_v`.
Partials residualize average ranks within state on log population and rurality.
BH is the primary adjustment for the twelve signed tail shares. Holm is the sensitivity.
Climate is the #110 native-double result: no county reached 20 usable days.
No missing value was imputed as zero. Seeds 1142026 and 1142027.

## Material findings and limits

Headline counts: published floor 651, no county-linked record 2493, of 3144.
SVI rescaled by 100: False. Uninsured percentile rescaled by 100: False.
Three-feature PCA n 3144, two-component share 0.8847, October 13 target 0.8850, difference -0.0003.
Cross-domain PCA n 3109, two-component share 0.5758. That share is a different block and is not the 88.5% figure.
Context condition number 4.5751. Cross-domain condition number 13.8771.
Signed BH family complete: True.
Context VIFs: log population 1.1267, SVI 1.6650, uninsured percentile 1.6646. All are below 5.
Leave-one-Census-region two-component shares: Northeast 0.8820 (move -0.0027), Midwest 0.8534 (move -0.0313), South 0.8898 (move 0.0051), West 0.8936 (move 0.0089). The Midwest move meets the frozen 0.02 rule.
Climate fields not estimable: average temperature (usable native-double days 0 to 1), precipitation (0 to 6), maximum temperature, and minimum temperature.
Small-state three-feature share 0.8833, material move False. Contiguous-scope share 0.8840, material move False.

| Rank | Pair | Estimate | State-cluster interval | Partial | BH tail | Qualified |
| --- | --- | ---: | --- | ---: | ---: | --- |
| 1 | D6 log population x RUCC | -0.7596 | -0.8048 to -0.7120 | -0.7181 | 0.0000 | no |
| 2 | D1 SVI x uninsured percentile | 0.5823 | 0.4801 to 0.6528 | 0.5115 | 0.0000 | no |
| 3 | D7 uninsured percentile x human published | -0.3714 | -0.4864 to -0.2315 | 0.0204 | 0.0000 | no |
| 4 | D8 log population x human published | 0.3644 | 0.2719 to 0.4526 | 0.1746 | 0.0000 | no |
| 5 | D10 uninsured percentile x pathogen present | -0.3623 | -0.4614 to -0.2413 | 0.0083 | 0.0000 | no |
| 6 | D11 log population x pathogen present | 0.2848 | 0.2019 to 0.3692 | 0.0699 | 0.0000 | no |
| 7 | D9 SVI x pathogen present | -0.2028 | -0.3027 to -0.0816 | -0.0302 | 0.0013 | no |
| 8 | D12 RUCC x pathogen present | -0.1881 | -0.2630 to -0.1145 | 0.0175 | 0.0000 | no |
| 9 | D5 uninsured percentile x RUCC | 0.1726 | 0.0969 to 0.2572 | 0.1863 | 0.0000 | no |
| 10 | D3 uninsured percentile x log population | -0.1621 | -0.2640 to -0.0580 | 0.0608 | 0.0024 | no |
| 11 | D2 SVI x log population | 0.1334 | 0.0155 to 0.2555 | 0.2380 | 0.0295 | no |
| 12 | D15 log population by tick status | 0.1725 | 0.0996 to 0.2589 | 0.0201 | not estimable | no |
| 13 | D14 uninsured percentile by tick status | 0.0938 | 0.0343 to 0.1749 | 0.0022 | not estimable | no |
| 14 | D16 RUCC by tick status | 0.0776 | 0.0335 to 0.1442 | 0.0003 | not estimable | no |
| 15 | D13 SVI by tick status | 0.0181 | 0.0067 to 0.0532 | 0.0024 | not estimable | no |
| 16 | D4 SVI x RUCC | 0.0026 | -0.1065 to 0.1083 | 0.2557 | 0.9750 | no |

Reproduction points, compared with the #116 displays. A cited interval is used
only when the point still matches at four decimals.

| Association | Point | Bias-corrected V | n | Matches #116 display | Cited interval |
| --- | ---: | ---: | ---: | --- | --- |
| tick_pathogen | 0.5607 | 0.5602 | 3109 | True | 0.4650 to 0.6524 |
| human_tick | 0.4780 | 0.4774 | 3109 | True | 0.3785 to 0.5810 |
| human_pathogen | 0.5705 | 0.5703 | 3109 | True | 0.4354 to 0.7130 |
| svi_human | -0.1971 | not estimable | 3144 | True | -0.3067 to -0.0721 |
| rucc_human | -0.2455 | not estimable | 3144 | True | -0.3266 to -0.1661 |

Recommendations:

- Keep in the joint context block: log_population, svi_percentile, rucc_2023, uninsured_percentile.
- Drop from the joint context block: none.
- Bias-corrected tick by pathogen V is below 0.80. Keep tick status and pathogen status as separate documentation fields.
- Human published largest absolute loading on the components that reach 80% is 0.4390. Keep it in the low-dimensional block and as a documentation outcome.
- Drop January climate. No native-double field reached 20 usable days.
- Three-feature two-component share is 0.8847 against the October 13 figure 0.8850.

Spot checks chosen by smallest FIPS, not by the coefficients:

- published_floor: Baldwin County, AL, FIPS 01003, human published_count_floor, tick Established, pathogen No records.
- no_county_record: Autauga County, AL, FIPS 01001, human no_county_linked_record, tick Established, pathogen No records.
- outside_tick_scope: Aleutians East Borough, AK, FIPS 02013, human no_county_linked_record, tick Unknown, pathogen Unknown.

A published human floor is a surveillance lower bound, not incidence or risk. No records and Unknown are documentation states, not negatives. Missing is not zero. Vintages are 2022 for SVI, uninsured, and population, 2023 for the human floor and rural-urban code, and cumulative through 2025 for tick and pathogen status. State resampling does not cover cross-border dependence.

## Decision

Representation call: **revise**. Follow-up call: **investigate**.

The full-sample share 0.8847 is inside 0.880 to 0.890, so the October 13 description still fits that sample. The representation call is revise because leaving out the Midwest moves the share by 0.0313. No signed row met the frozen follow-up gate: every signed row moves by at least 0.05 in at least one Census region. D1, SVI by uninsured percentile, is 0.5823 with partial 0.5115 (interval 0.4532 to 0.5652) and moves by 0.0850 in the Midwest and 0.1178 in the South. D6, log population by RUCC, is -0.7596 with partial -0.7181 (interval -0.7566 to -0.6731) and moves by 0.0610 in the South. Uninsured percentile by the human published floor, uninsured percentile by pathogen present, and RUCC by pathogen present lose a partial interval that excludes zero. Uninsured percentile by log population changes sign. January climate stays out of the feature matrix. Use the keep and drop lines as a representation note for a later design story, not as a training decision.

This is permission to quote the named coefficients with their intervals. It is not permission to train a model or publish a score.

## Reproduction and retained evidence

- Code revision/run: `68f21995dd6af4a48281ae2cc5b80ad8e13cf880`. Run `114-cross-domain-20261026T0822Z`. Spec `114-cross-domain/v1`.
- Entry points: `sql/validation/114_cross_domain.sql`, `scripts/eda_114_cross_domain.py`, `src/lyme_gap_atlas_ml/cross_domain.py`.
- Commands: `uv run python scripts/check_ml_agent_context.py`, then `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_114_cross_domain.py`, then `uv run python scripts/verify.py`.
- Lab row counts: `REGISTRY.RUNS` 1, `EDA.METRICS_LONG` 111, `EDA.CORRELATIONS` 40, `EDA.FINDINGS` 5, `REGISTRY.QUERIES` 3, `EXPERIMENTS.EXPERIMENTS` 2, `EXPERIMENTS.MODEL_METRICS` 48. `REGISTRY.ARTIFACTS` for this run is 0. Chart registration is pending.
- Drive: folder `issue-114` (`1bWaXnJvpeQFL81CNVOmUnCSfn9RAliI-`, parent `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`) has no live PNG. Uploaded copies were trashed because the Drive byte size did not match the local file. Do not register those trashed ids. Heatmap: `1dlHjttlupMolP6rOqFJSzqbrQbKoiOnY` (20364 bytes), `1GnpoZHU0bNS5jk5XeQdw8_oWso2rWSt3` (20363), `1H0oMzr73R00lZqdtyUIsZKBQPsWQInyw` (8). Scree: `1TxGHcnPX5ojwr-cg4M7druRIbBNE7U-_` (11939), `1yVxCaisyPZ5LyzAXr9WUvy8gZ2QG-dn2` (11939). Loading plot: `1ChqyVC8LFlykX-XXRsDNKmuQGlV6HMGp` (7698), `1IUtnqnWiFcJQkQcPSFA5nBfiTGbdgMIc` (7698), `1Ovh9rrQQRThCkgiYbhKYFIZJk2UaJ8KW` (8). The ML Lead will upload fresh files and register `REGISTRY.ARTIFACTS` only when bytes and sha256 match the local files below.
  - `redundancy-heatmap.png`, 22398 bytes, sha256 `ab721479d05ab8e54dbf848de91d84d87a8ce9d7e405f610f0cdc1d437d5173d`.
  - `scree.png`, 11942 bytes, sha256 `b8e237808e94053b211964ce3c4b64b77a66873546ad12391a8579a0148e2256`.
  - `loading-plot.png`, 7614 bytes, sha256 `59138842a6747e0c586733784d885563c3e0c3085e7b9b20512d4fa0672611fb`.
- Transient artifacts not committed: county rows, chart PNGs under `artifacts/charts/114/`, and `outputs/114-run-id.txt`.
