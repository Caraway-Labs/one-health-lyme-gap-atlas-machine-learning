# ML #114 cross-domain associations: registered specification v1

- **Spec/version and owning issue:** `114-cross-domain/v1`, [ML #114](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/114), parent [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway authorized this story through the EDA orchestrator. This run does not authorize a Tier 1 change, a PROD write, an API, a pipeline, a UI, or a public score.
- **Question / decision / allowed interpretation:** Which signals move together across climate, vector and pathogen documentation, the human published floor, and SVI, uninsured, population, and rurality? Does the 13 October 2026 two-component PCA, about 88.5% of variance on SVI, uninsured percentile, and log population (epic #22 section 4.1 item 5), still describe that three-feature block? The decisions are keep, revise, or stop for that representation, and advance, investigate, or stop for a follow-up hypothesis. A coefficient is a surveillance-documentation association. It is not incidence, risk, burden, or causation. `No records` and `Unknown` are documentation states, not biological negatives. A missing floor is not zero. A published count is a lower bound (CDC floor 5). Do not train on the Tier 1 score, on `EVIDENCE_COMPLETENESS`, or on latent-class membership.
- **Estimand:** Two frozen blocks.
  1. Representation. The share of standardized variance on the first two principal components of `svi_percentile`, `uninsured_percentile`, and `log_population`. The comparison target is 0.885. A cross-domain complete-case PCA, defined below, is a separate representation. It is not a replay of the 88.5% figure.
  2. Association register. Marginal coefficients for the discovery pairs below, each with a state-cluster interval, a partial coefficient that removes log population, rurality, and state, and a leave-one-Census-region point. Reproduction pairs are recomputed at the point only and compared with the #116 intervals. They are not a new bootstrap.

  The null used only to describe an interval is a coefficient of 0. Crossing zero is a description of the interval. It is not a significance call and not a causal contrast.
- **Unit / cohort / geography / time:** The descriptive unit is one county on the pinned release. The resampling unit is the postal state, including the District of Columbia. The state block for holdouts is the Census region in `coverage_audit.CENSUS_REGIONS`. This is one snapshot. It is not a change contrast and not a forecast. Human surveillance is calendar 2023. Tick and pathogen statuses are cumulative through 2025-12-31. SVI and the uninsured percentile are 2022. Population is the 2022 county layer. The rural-urban code is 2023. Those vintages are not one time base. Climate, when it is discussed, is the January 2025 county-day window already measured by #110. Expected county count 3,144.
- **Variables / source / version:** Execution reads `PRESENTATION.CURRENT_RELEASE_V` first and stops unless the pin equals release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. The only county object is `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. Columns: `FIPS`, `COUNTY`, `STATE`, `RELEASE_ID`, `POPULATION`, `SVI_PERCENTILE`, `UNINSURED_PERCENTILE`, `RUCC_2023`, `HUMAN_STATUS`, `TICK_STATUS`, `BURGDORFERI_STATUS`, `IN_CONTIGUOUS_TICK_SCOPE`. No other column is selected. County rows may stay in memory. They are not written to a file, to git, or to Drive.

  Unit rule, the same rule as #116, frozen before the fit: if the maximum of `SVI_PERCENTILE` on the release is greater than 1.5, divide that column by 100. Apply the same rule independently to `UNINSURED_PERCENTILE`. Do not clip. `log_population` is the natural log of `POPULATION`. Standardization later removes the log base, so a log10 coding cannot by itself move the PCA share.

  | Name | Type | Grain | Role |
  | --- | --- | --- | --- |
  | `log_population` | positive continuous | 2022 county population | context feature and partial control |
  | `svi_percentile` | continuous on [0, 1] after the unit rule | 2022 | context feature |
  | `uninsured_percentile` | continuous on [0, 1] after the unit rule | 2022 | context feature |
  | `rucc_2023` | ordered integer 1–9 | 2023 | rurality feature and partial control |
  | `human_published` | binary documentation | calendar 2023 | 1 only for `published_count_floor`; 0 only for `no_county_linked_record` |
  | `tick_status` | nominal, 3 known levels | cumulative through 2025-12-31 | Established, Reported, No records |
  | `pathogen_present` | binary documentation | cumulative through 2025-12-31 | 1 for Present, 0 for No records |
  | `in_contiguous_tick_scope` | eligibility flag | release geography | not a feature |

  Not selected, and why: `UNINSURED` percent, because the October exhaustive pass recorded Spearman 1.00 with the percentile and this story does not re-estimate that identity. `CASE_COUNT_FLOOR_2023` and `INCIDENCE_FLOOR_2023`, because they are null on the unpublished counties and #61 owns the published-subset floor association. `EVIDENCE_COMPLETENESS`, species-specific tick columns, tier scores, geometry, payload, part text, and limitation text.

  Climate fields, frozen from #110 run `110-peer-county-clusters-20261026T0644Z` on this same pin. A day counted only when `VALUE_STATE` was `OBSERVED` or `ZERO` and `VALUE_NATIVE_DOUBLE` was non-null. No county reached 20 usable days. This story does not query `CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V` again and does not parse `VALUE`.

  | Field | Usable for a county association |
  | --- | --- |
  | `nclimgrid_tavg_county_day` | Not estimable. Usable native-double days were 0 to 1. |
  | `nclimgrid_prcp_county_day` | Not estimable. Usable native-double days were 0 to 6. |
  | `nclimgrid_tmax_county_day` | Not estimable. Not a separate feature. It repeats the average-temperature contrast, and it was not in the 20-day cohort. |
  | `nclimgrid_tmin_county_day` | Not estimable. Same reason as maximum temperature. |

  The #107 decimal and integer parse of `VALUE` is a different estimand. It is not a source for this PCA or this register.
- **Missingness rule:** Do not impute. Do not replace a gap with zero, Established, or Present. A null SVI, uninsured percentile, population, or rural-urban code leaves every pair and every PCA that uses that column. Population must be finite and strictly positive. A rural-urban code outside the integers 1 through 9 leaves. Any other human status leaves every human pair. `Unknown` tick or pathogen status, and `IN_CONTIGUOUS_TICK_SCOPE` false, leave every tick or pathogen pair. They are exclusions, not zeros. `No records` stays a real documentation level and may be coded 0 on a binary feature whose other level is Present, Established, or Reported. That 0 is a level, not an imputed missing. The three-feature PCA cohort is counties with usable SVI, uninsured percentile, and log population. The cross-domain PCA cohort is the intersection of that cohort with a usable rural-urban code, a two-level human status, a three-level tick status, and a two-level pathogen status. Exclusion counts are results. A duplicate `FIPS`, a `FIPS` that is not five digits, a mixed release, or a state missing from the Census map stops the run.
- **Exploratory or confirmatory:** Confirmatory for the release pin, the counts 3,144 / 651 / 2,493, the reproduction points, and the 0.885 comparison. Exploratory for the discovery register. Nothing in the results is used to add a pair, change a seed, change the 20-day climate rule, or change the 0.885 band. The #116 reproduction points, compared and not replaced:

  | Association | Display | Interval from #116, cited if the point still matches at four decimals |
  | --- | --- | --- |
  | Tick × pathogen Cramér's V, uncorrected | 0.5607 | 0.4650–0.6524, n 3,109 |
  | Human × tick Cramér's V, uncorrected | 0.4780 | 0.3785–0.5810 |
  | Human × pathogen Cramér's V, uncorrected | 0.5705 | 0.4354–0.7130 |
  | Spearman, SVI × published floor | -0.1971 | -0.3067 to -0.0721 |
  | Spearman, RUCC × published floor | -0.2455 | -0.3266 to -0.1661 |

  Bias-corrected V is reported beside the uncorrected reproduction points. The epic display is the uncorrected value. A bias-corrected value is not required to equal 0.5607.
- **Method / assumption rationale:** Counties in one state share reporting rules, so the #116 state-cluster interval is the uncertainty. Methods already implemented are called, not rewritten.

  | Pair | Method | Source | Why this cell of the #116 matrix |
  | --- | --- | --- | --- |
  | Ordered or continuous × ordered or continuous, including a 0/1 documentation level | Spearman | `test_selection.spearman_rho` | #116 chose Spearman for a monotone pair and rejected Pearson as the primary coefficient |
  | Nominal tick status (3 levels) × continuous or ordered | Kruskal-Wallis epsilon-squared | `eda63.omnibus` | Epsilon-squared is the rank eta-squared from #63. ANOVA stays rejected. Two-level pathogen and human pairs stay Spearman, because #116 rejected Kruskal when it only restates a binary contrast |
  | Nominal × nominal, reproduction only | Uncorrected Cramér's V | `test_selection.cramers_v` | This is the #65 and #116 coefficient. Chi-square and Fisher stay rejected as tests |
  | Same nominal tables, register column | Bergsma bias-corrected V | `cramers_v` chi-square, rows, columns, and n, then the correction below | The correction uses that chi-square. It does not recompute an association test |

  Bias correction, applied to the `Association` returned by `cramers_v`:

  ```text
  phi2 = chi2 / n
  phi2_tilde = max(0, phi2 - (r - 1) * (c - 1) / (n - 1))
  r_tilde = r - (r - 1)^2 / (n - 1)
  c_tilde = c - (c - 1)^2 / (n - 1)
  V_tilde = sqrt(phi2_tilde / min(r_tilde - 1, c_tilde - 1))
  ```

  Partial association, descriptive, not the regression #116 rejected as a sampling model. Residualize average ranks within state, then residualize those values on the within-state ranks of the controls, then take the Pearson correlation of the residuals. Controls are log population and RUCC, omitting a control that is one of the two variables. State is removed by the within-state demean. For Kruskal pairs, residualize the continuous rank the same way and pass the residuals to `eda63.omnibus`. For the reproduction V tables, the partial is the n-weighted mean of bias-corrected V inside population-tertile × metro cells (metro is RUCC 1–3). A stratum with n below 11 or a degenerate margin is skipped. If the retained strata cover fewer than 10 states or fewer than 500 counties, the partial is not estimable.

  Discovery family, marginal coefficients, one state-cluster interval each:

  | Id | Pair | Coefficient |
  | --- | --- | --- |
  | D1 | SVI × uninsured percentile | Spearman |
  | D2 | SVI × log population | Spearman |
  | D3 | uninsured percentile × log population | Spearman |
  | D4 | SVI × RUCC | Spearman |
  | D5 | uninsured percentile × RUCC | Spearman |
  | D6 | log population × RUCC | Spearman |
  | D7 | uninsured percentile × human published | Spearman |
  | D8 | log population × human published | Spearman |
  | D9 | SVI × pathogen present | Spearman |
  | D10 | uninsured percentile × pathogen present | Spearman |
  | D11 | log population × pathogen present | Spearman |
  | D12 | RUCC × pathogen present | Spearman |
  | D13 | SVI by tick status | epsilon-squared |
  | D14 | uninsured percentile by tick status | epsilon-squared |
  | D15 | log population by tick status | epsilon-squared |
  | D16 | RUCC by tick status | epsilon-squared |

  Climate × tick, climate × human, and climate × SVI are register rows with status `not_estimable`. They are not tested.

  Uncertainty and multiplicity, frozen:

  | Piece | Setting |
  | --- | --- |
  | State-cluster interval | `test_selection.state_cluster_interval`. 2,000 replicates. Percentiles 2.5 and 97.5. Seed `1142026` |
  | Naive comparison | `test_selection.resample_interval` on counties. Seed `1142027`. Width ratio only. Not the reported interval |
  | Tail share | The #116 share, `2 * min(share <= 0, share >= 0)`, capped at 1. Not a design-based p-value |
  | Signed family | D1–D12. Benjamini-Hochberg on the twelve tail shares is the primary adjustment, because this register is larger than the four-contrast #116 family. Holm, via `test_selection.holm`, is the sensitivity. BH or Holm runs only when all twelve intervals are estimable |
  | Unsigned family | D13–D16 and bias-corrected V. Epsilon-squared and V are truncated at 0, so the #116 tail share is not a two-sided null probability. No BH and no Holm. The interval and the region move are the report |
  | Reporting flag | A signed row is multiplicity-qualified when its BH-adjusted tail share is at most 0.05. That flag ranks the register. It is not a finding of effect |
  | Small cells | A count from 1 to 10 is not written to a lab aggregate, a chart, or a Drive file |

  PCA. Columns are complete-case and standardized with divisor `n - 1` (`numpy.corrcoef`). Components are the eigenvectors of that correlation matrix. The sign of component k is flipped so the loading named below is non-negative: component 1, `log_population`; component 2, `svi_percentile`; later components, `uninsured_percentile`. Explained-variance share is the eigenvalue divided by the sum of eigenvalues. Loadings are the signed eigenvectors. Bootstrap loading intervals resample states with `state_cluster_interval` and the same sign rule applied to each draw. Leave-one-Census-region-out refits the point. Condition number is the 2-norm condition number of the correlation matrix. VIF for a column is `1 / (1 - R^2)` from the least-squares projection of that standardized column on the others. `R^2 >= 1` is recorded as not finite.

  The three-feature fit uses only SVI, uninsured percentile, and log population. The cross-domain fit adds RUCC, `human_published`, `tick_established`, `tick_reported`, and `pathogen_present`. `No records` is the omitted tick and pathogen level, so a 0 on those indicators is that level. Unknown counties are outside this fit.

  Coverage sensitivities, points only, outside the BH family:

  - Leave out each Census region.
  - Drop states with fewer than 15 counties in the relevant cohort and refit the three-feature share and D1–D3.
  - Refit the cross-domain PCA on the contiguous scope only. That is already the primary cross-domain cohort. The sensitivity is the three-feature share on that same scope.
  - Do not add a zero-filled climate matrix.

  A sensitivity is material when a signed coefficient changes sign or moves by at least 0.05, when an unsigned coefficient moves by at least 0.05, or when the three-feature two-component share moves by at least 0.02.
- **Spatial / temporal dependence:** The reported interval resamples states. It does not cover dependence that crosses a state line. The partial coefficient removes state means, log population, and rurality. It does not remove a shared reporting rule that is not constant inside a state, and it does not align the 2022, 2023, and 2025 vintages. No county-adjacency matrix is used.
- **Effect-size / uncertainty output:** Spearman rho, Kruskal epsilon-squared, uncorrected and bias-corrected V, partial coefficients, state-cluster intervals, naive width ratios, BH and Holm adjusted tail shares for D1–D12, VIF, condition number, explained-variance shares, and loadings with bootstrap intervals. Climate rows have no coefficient.
- **Key caveat / stop conditions:** Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Stop if the live release id, schema, methodology, scope, or bundle SHA differs from the pin. Stop if the county count is not 3,144, if `FIPS` are not unique five-digit ids, or if any state is outside the Census map. Stop if the three-feature cohort has fewer than 500 counties or a column with zero variance. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or the climate day view. Do not select payload, part text, limitation text, or geometry. A query still running at 10 minutes is cancelled.

  Ranked register, applied after the fit without changing the rule. Sort key, best first: multiplicity-qualified signed rows, then other signed rows whose interval excludes 0, then unsigned rows whose interval excludes 0, then the remainder. Inside a tier, larger absolute coefficient ranks first. Each row carries the interval, the region-stability flag, the partial coefficient, one confounder sentence, one alternative explanation, and one follow-up sentence from the templates below.

  | Situation | Confounder sentence | Alternative explanation | Follow-up |
  | --- | --- | --- | --- |
  | Partial changes sign, or a signed partial interval includes 0 while the marginal interval excludes 0, or an unsigned partial falls below half the marginal point | The marginal association does not survive log population, rurality, and state. | Shared state reporting, county size, or rurality can produce the marginal coefficient. | Do not carry the marginal association forward. |
  | Absolute Spearman at least 0.80, or VIF at least 5 | The features move together inside the context block. | They can be two codings of rural disadvantage or of county size, measured in different vintages. | Keep one feature in a joint linear block and hold the other for a one-variable sensitivity. |
  | Signed gate holds: interval excludes 0, BH-adjusted tail share at most 0.05, partial keeps its sign, region move is not material | State, size, and rurality do not remove the sign. | Documentation still clusters by reporting practice and by the mismatch of 2022, 2023, and 2025 vintages. | A later story can repeat the contrast on a governed multi-year panel or a spatial block beyond state. This run does not open that story. |
  | Climate row | No partial is estimable. | A January native-double mean is not a habitat series. | Do not add January climate until a reviewed numeric value has 20 usable days. |

  Keep or drop, frozen, for the joint representation:

  - Drop a context feature from the joint linear block when its VIF is at least 5 or its absolute Spearman with another context feature is at least 0.80. Keep the other feature. Prefer, in order, log population, then SVI, then RUCC, then uninsured percentile.
  - Drop climate. No climate column enters a matrix.
  - Keep tick status and pathogen status as separate documentation fields unless their bias-corrected V is at least 0.80. At or above 0.80, use one vector-documentation block in a linear representation and keep both fields for a contingency table.
  - Keep the human published indicator as a documentation outcome. Drop it from the low-dimensional predictor block when its largest absolute loading on the components that together reach 80% of cross-domain variance is below 0.20. Keep it in that block when that loading is at least 0.30.

  This story writes no new table. Rows go to existing `REGISTRY.RUNS`, `EDA.METRICS_LONG`, `EDA.CORRELATIONS`, `EDA.FINDINGS`, `EXPERIMENTS.EXPERIMENTS`, `EXPERIMENTS.MODEL_METRICS`, `REGISTRY.QUERIES`, and, after the Drive upload, `REGISTRY.ARTIFACTS`. Inserts are insert-only. A second invocation reuses the run id and does not insert again. No `DELETE`. No `GRANT`: no new table is created, and the Snowflake integration guide forbids role administration from this adapter. `OH_LYME_PROD_READ` already has no new object to be granted.
- **Result disposition:** **PLANNED.** After execution, apply both rules without changing them.

  **Representation.** **stop** when the three-feature PCA is not estimable. **revise** when it is estimable and the two-component share is outside [0.880, 0.890], or any leave-one-region share moves by at least 0.02, or any of the three features has VIF at least 5. **keep** when the share is inside [0.880, 0.890], every region share moves by less than 0.02, and all three VIFs are below 5. keep describes the three-feature block only. It does not mean the cross-domain matrix is two-dimensional, and it does not authorize a model.

  **Follow-up.** **stop** when no signed discovery interval is estimable. **advance** when at least one signed row meets the signed gate in the template table. **investigate** when signed intervals exist and none meet that gate. advance proposes the highest-ranked gated row as a later analysis. It does not authorize training, a rank, or a public map.
- **Reproduction / evidence:** SQL in `sql/validation/114_cross_domain.sql`. Runner `scripts/eda_114_cross_domain.py`. Logic `src/lyme_gap_atlas_ml/cross_domain.py`. Spearman, Cramér's V, Holm, and the state-cluster interval come from `test_selection`. Kruskal epsilon-squared comes from `eda63.omnibus`. Climate usability is cited from #110, not refit. Run id pattern `114-cross-domain-<UTC yyyymmddThhmmZ>`. Seeds `1142026` and `1142027`. Charts under git-ignored `artifacts/charts/114/`, each PNG under 40 KB: `redundancy-heatmap`, `scree`, `loading-plot`. Upload to Drive folder `issue-114` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/114-cross-domain-associations.md`.

  Peer-review checks, frozen with the spec: recompute the row count and the distinct five-digit `FIPS` count; confirm null SVI, null uninsured, null population, and out-of-range RUCC are exclusions; confirm `Unknown` is not coded 0; confirm `No records` remains a level on the binary pathogen and tick indicators; confirm the SQL does not select incidence, a tier score, payload, limitation text, geometry, or a climate value. The write-up names three spot-check counties chosen without reference to the estimates: the smallest `FIPS` with a published floor; the smallest `FIPS` with no county-linked human record; the smallest `FIPS` outside contiguous tick scope.

  ```text
  uv sync --locked --extra dev --extra snowflake
  uv run python scripts/check_ml_agent_context.py
  MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_114_cross_domain.py
  uv run python scripts/verify.py
  ```

## Amendment v1.1 — disclosure, before execution

Matthew Caraway’s ruling on 2026-10-25: GitHub issue comments, pull-request bodies, and `docs/eda` results write-ups may name counties and may include county-level numbers, including counts under 11. `EDA.METRICS_LONG`, `EDA.CORRELATIONS`, `EDA.FINDINGS`, and the PNG charts still omit a count from 1 to 10. County names do not go into chart titles, axis labels, or Drive files. `EDA.FINDINGS` statements stay aggregate because the lab writer rejects a five-digit county id in prose.

The #110 artifact handoff is not part of this estimand. `REGISTRY.ARTIFACTS` for run `110-peer-county-clusters-20261026T0644Z` receives two insert-only chart rows, `cluster-profile.png` and `stability-heatmap.png`, using the Drive ids supplied by the ML Lead. This story does not upload or edit those Drive files.
