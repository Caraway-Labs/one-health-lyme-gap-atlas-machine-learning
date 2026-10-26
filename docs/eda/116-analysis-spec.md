# ML #116 statistical test selection: registered specification v1

- **Spec/version and owning issue:** `116-test-selection/v1`, [ML #116](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/116), parent [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway authorized this story through the EDA orchestrator. This run does not authorize a Tier 1 change, a PROD write, a UI change, or a public score. It does not repeat the #114 correlation sweep. It owns method selection and inferential safeguards.
- **Question / decision / allowed interpretation:** Which Atlas county comparisons can support an interpretable statistical difference or association, and which cannot? How robust are the 13 October 2026 associations named in epic #22 section 4.1 item 4? The decision is keep, revise, or stop for analyst review of those comparisons. A published human floor is a surveillance-documentation status and a lower bound (CDC floor 5). It is not incidence, risk, burden, or causation. `No records` and `Unknown` are documentation states, not biological negatives. A missing floor is not zero. Do not train on the Tier 1 score, on `EVIDENCE_COMPLETENESS`, or on latent-class membership.
- **Estimand:** Four prespecified contrasts on the pinned release, plus one reproduction set.
  1. Q1 share difference: published-floor share among metro counties (rural-urban codes 1–3) minus the same share among nonmetro counties (codes 4–9). Companion association: Cramér's V on that 2×2 table.
  2. Q2 share difference: published-floor share where the social-vulnerability percentile is below 0.5 minus the share where it is at least 0.5, after the unit rule below.
  3. H3: Spearman rank correlation of the social-vulnerability percentile with the published-floor indicator.
  4. H4: Spearman rank correlation of the rural-urban code (1 through 9, higher is more rural) with the published-floor indicator.
  5. Reproduction, not in the hypothesis family: unweighted county-level Cramér's V for human status × tick status, human status × pathogen status, and tick status × pathogen status, on the in-scope known-category cohort. The tick × pathogen interval uses the existing #65 state-cluster procedure.

  The null used only to describe an interval is a difference of 0 or a coefficient of 0. Crossing zero is a description of the interval. It is not a significance call.
- **Unit / cohort / geography / time:** The descriptive unit is one county on the pinned release. The resampling unit is the state, including the District of Columbia. Census region, from `coverage_audit.CENSUS_REGIONS`, is the leave-one-region stratum. This is one snapshot. It is not a change contrast and not a forecast. Human surveillance is calendar 2023. Tick and pathogen statuses are cumulative through 2025-12-31. The vulnerability percentile is 2022. The rural-urban code is 2023. Those vintages are not one time base.
- **Variables / source / version:** Execution reads `PRESENTATION.CURRENT_RELEASE_V` first and stops unless the pin equals the #109 release `governed-2026-10-15-january-climate-prod`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. The only county object is `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. Columns: `FIPS`, `COUNTY`, `STATE`, `RELEASE_ID`, `HUMAN_STATUS`, `TICK_STATUS`, `BURGDORFERI_STATUS`, `RUCC_2023`, `SVI_PERCENTILE`, `IN_CONTIGUOUS_TICK_SCOPE`. No other column is selected. County rows may stay in memory. They are not written to a file, to git, or to Drive.

  Unit rule, frozen before the fit: if the maximum of `SVI_PERCENTILE` on the release is greater than 1.5, divide that column by 100 and record that the column was rescaled. Do not clip. Do not rescale a column whose maximum is at most 1.5. Bins and the 0.5 cut are applied after that rule.

  October 13 reference figures, compared and not replaced:

  | Association | Displayed value | Coding this spec treats as the target |
  | --- | --- | --- |
  | Tick × pathogen Cramér's V | 0.5607 | In-scope 3×2, Unknown excluded. Unrounded #65 value 0.560660 on 3,109 counties |
  | Tick × pathogen state-block interval | 0.4650–0.6524 | #65 percentile interval 0.464977–0.652404, 2,000 draws, seed 6501 |
  | Human status × tick Cramér's V | 0.4780 | Same 3,109-county cohort, tick levels Established / Reported / No records |
  | Human status × pathogen Cramér's V | 0.5705 | Same cohort, pathogen levels Present / No records |

  The exhaustive write-up's 0.48, 0.57, and 0.81, with chi-square statistics 726, 1,030, and 4,132, are the Unknown-included full-margin sensitivity on all 3,144 counties. They are not the epic item-4 targets. `No records` stays a level in both codings.

  Q1 eligibility: `HUMAN_STATUS` is `published_count_floor` or `no_county_linked_record`, and `RUCC_2023` is an integer from 1 through 9. Metro is 1–3. Nonmetro is 4–9 (USDA metropolitan vs nonmetropolitan). The published-floor indicator is 1 only for `published_count_floor`.

  Q2 eligibility: the same two human statuses and a non-null vulnerability percentile after the unit rule. Lower vulnerability is strictly below 0.5. Higher vulnerability is 0.5 or above.

  Reproduction eligibility: `IN_CONTIGUOUS_TICK_SCOPE` is true, tick status is Established, Reported, or No records, pathogen status is Present or No records, and human status is one of the two levels above. Unknown and out-of-scope rows are exclusions, counted separately. This is the #65 cohort. The tick × pathogen point and interval are computed by `evidence_association_65.analyze_aggregate_counties`, passing `TICK_STATUS` as `VECTOR_STATUS`. Human × tick and human × pathogen use the same cohort and the same interval arithmetic, because the #65 helper is limited to a pathogen table with two columns.
- **Missingness rule:** Do not impute. Do not replace a gap with zero, Established, or Present. A null rural-urban code leaves Q1 and H4. A null vulnerability percentile leaves Q2 and H3. Any other human status leaves every contrast. `No records` and `Unknown` are not recoded to a negative test. Exclusion counts are results. A duplicate `FIPS`, a `FIPS` that is not five digits, a mixed release, or a state missing from the Census map stops the run.
- **Exploratory or confirmatory:** Confirmatory for the release pin, the headline counts 3,144 / 651 / 2,493, the four contrasts, the Holm family, and the three epic V displays. The nine-code rural-urban share table and the five vulnerability bins (edges 0, 0.2, 0.4, 0.6, 0.8, 1, plus a value of exactly 1) are descriptive comparisons with the 13 October share tables. They are not extra hypotheses. Nothing in those tables is used to move the metro cut, the 0.5 cut, a seed, or the family.
- **Method / assumption rationale:** Descriptive estimates with a state-cluster bootstrap. A test is declined when independence, pairing, the outcome scale, or the sampling model fails. Counties in one state share reporting rules, so a county-IID test does not answer the question even when the sample is large.

  Question-to-method decision matrix, frozen before execution:

  | Method | When it would be considered | Decision for these questions | Assumption that fails or holds |
  | --- | --- | --- | --- |
  | Welch t | Unpaired continuous means, unequal variance, independent units | Rejected for Q1, Q2, and the reproduction | The published-floor outcome is binary. The mean difference would only restate the share difference, and counties are not independent. Incidence is not the outcome: it exists only on the published subset and is a censored lower bound |
  | Paired t | Paired continuous differences, independent pairs | Rejected | The pinned release is one row per county. Epic #22 records the multi-year human contrast as not estimable |
  | Mann-Whitney | Unpaired rank shift, independent samples | Rejected | A binary outcome's ranks restate the share difference. The test still treats counties as independent |
  | Wilcoxon signed-rank | Paired ranks, independent pairs | Rejected | No paired county periods on this snapshot |
  | ANOVA / Welch ANOVA | Three or more continuous group means, independent units | Rejected | Rural-urban codes are ordered categories, not normal scores. Code 5 is a small published cell. The tested rural contrast is the two-group metro cut, not nine means |
  | Kruskal-Wallis | Three or more rank distributions, independent samples | Rejected | The nine-code table is descriptive. A rank test would treat counties as independent and would add no estimand beyond H4 |
  | Chi-square | Categorical association, independent observations, expected cells at least 5 | Rejected as a test. Retained only as the numerator of Cramér's V | Expected cells in the national tables are large, but counties are not independent. The IID tail probability is not stored and is not a conclusion |
  | Fisher exact | Small expected cells, fixed margins, independent observations | Rejected | The national tables are not small. Fisher does not repair within-state dependence. The #65 exact routine is not invoked |
  | Spearman | Monotone association of ordered or continuous pairs | Chosen for H3 and H4, as a coefficient with a state-cluster interval | Average ranks handle ties. The coefficient is not a test. Pearson is not the primary coefficient: the floor indicator is binary and the rural-urban steps are not equal |
  | Pearson | Linear association, roughly linear scatter | Rejected as a primary estimate. Not in the Holm family | It is the wrong scale for a binary floor and an ordered rural-urban code. #114 owns the context correlation matrix. This story does not re-estimate it |
  | Regression | A named outcome and a sampling model | Rejected. No `EXPERIMENTS` rows | There is no sampling model for state reporting rules, the CDC floor, or within-state dependence. A logistic regression of the floor indicator would be an independent-county likelihood |

  Chosen uncertainty for every reported coefficient and share difference:

  | Piece | Setting |
  | --- | --- |
  | State-cluster interval | Resample states with replacement. 2,000 replicates. Percentiles 2.5 and 97.5 with the #65 linear index `(n-1)*p`. A replicate with a zero group denominator or a degenerate margin is a failure. If more than 5% fail, or fewer than 10 states remain, the interval is not estimable |
  | New-family seeds | Cluster seed `1162026`. County-IID comparison seed `1162027` |
  | Reproduction seed | `6501`, inside `analyze_aggregate_counties` for tick × pathogen, and the same seed in the generalized bootstrap for the two human associations |
  | Naive comparison | Resample counties with replacement, same replicate count. Report the ratio of state-cluster interval width to naive width. The naive interval is a dependence diagnostic. It is not the reported uncertainty |
  | Tail share | Among successful state-cluster replicates, `2 * min(share <= 0, share >= 0)`, capped at 1. This is the share of state resamples that reach the other side of zero. It is not a design-based p-value |
  | Multiplicity | Holm step-down on the four new-family tail shares, in one family. Benjamini-Hochberg is rejected: four prespecified contrasts do not need a false-discovery rate. The reproduction trio is not in the family |
  | Small cells | A count from 1 to 10 is not written to a lab aggregate, a chart, or a Drive file. A composition whose omitted remainder is 1 to 10 is omitted. A zero on a denominator of at least 11 is kept. The results write-up may name counties and small counts |

  Sensitivities, point estimates only, outside the Holm family:

  - Leave out each Census region and recompute the two share differences.
  - Drop states with fewer than 15 counties in the relevant eligible set and recompute the two share differences.
  - Recompute the three reproduction associations with Unknown kept as its own level, which is the 0.81 coding.
  - Record the #65 Established+Reported collapse that `analyze_aggregate_counties` already returns. Do not add another collapse after seeing it.

  A sensitivity is material when a share difference moves by at least 0.02, or when leaving out a region or the small states makes a cluster interval that excluded zero include zero, or the reverse. The second part uses the primary interval's relationship to zero against the sensitivity point only when the sensitivity point changes sign. Sign change is the frozen sensitivity flag. The 0.02 absolute move is the other flag. No new interval is fit for a sensitivity.
- **Spatial / temporal dependence:** Do not treat counties as IID. The reported interval resamples states. The naive county bootstrap is computed so the write-up can say how many times wider the state-cluster interval is. State resampling does not cover dependence that crosses a state line. It is not a survey-design confidence interval.
- **Effect-size / uncertainty output:** Share differences on the probability scale, Spearman coefficients, Cramér's V, both intervals, the width ratio, the four Holm-adjusted tail shares, exclusion counts, and the nine-code and five-bin descriptive shares where the cell is publishable. Q3 has no estimate.
- **Key caveat / stop conditions:** Q3, climate strata versus tick or pathogen documentation, is not estimable on this pin. #109 already measured `CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V` on this release: one January 2025 window, 31 days, with 35 counties out of source coverage. Tick and pathogen statuses are cumulative through 2025-12-31. The county atlas has no climate-stratum column. This story does not query the climate view and does not invent a January temperature class. Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Stop if the live release id or bundle SHA differs from the #109 pin. Stop if the county count is not 3,144, if `FIPS` are not unique five-digit ids, or if any state is outside the Census map. Stop if Q1 and Q2 are both not estimable. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or any column other than the list above. Do not select payload, part text, limitation text, or geometry. A query still running at 10 minutes is cancelled.

  This story writes no new table. Rows go to existing `REGISTRY.RUNS`, `EDA.METRICS_LONG`, `EDA.CORRELATIONS`, `EDA.FINDINGS`, `REGISTRY.QUERIES`, and, after the Drive upload, `REGISTRY.ARTIFACTS`. The shared writers do not issue `GRANT`. The Snowflake integration guide forbids role and grant administration from this adapter. `OH_LYME_PROD_READ` still cannot count a new lab table until an owner grants `SELECT`. No grant is attempted.
- **Result disposition:** **PLANNED.** After execution, apply this rule without changing it.

  **stop** when a gate above fails, or both Q1 and Q2 are not estimable.

  **revise** when any epic four-decimal V display fails to match, when the tick × pathogen interval fails to match 0.4650–0.6524 at four decimals, when either share-difference interval includes zero, when the naive interval excludes zero and the state-cluster interval includes zero, or when a prespecified sensitivity is material.

  **keep** when the three epic V displays match at four decimals, the tick × pathogen interval matches at four decimals, both share-difference state-cluster intervals exclude zero, the naive-versus-cluster comparison does not change either share reading across zero, no sensitivity is material, and Q3 remains the predeclared no-go.

  keep means the two documentation contrasts and the reproduced associations can be quoted with their state-cluster intervals. It does not authorize a model, a ranking, or a causal sentence. revise means at least one comparison should not be quoted as a stable difference until the named gap is resolved. stop means the run did not produce the estimates.
- **Reproduction / evidence:** SQL in `sql/validation/116_test_selection.sql`. Runner `scripts/eda_116_test_selection.py`. Logic `src/lyme_gap_atlas_ml/test_selection.py`. The tick × pathogen reproduction calls `evidence_association_65.analyze_aggregate_counties`. Lab writes reuse `eda_writer.write_eda_results` and `eda_lab_writers.write_correlations`, `write_findings`, and `write_queries`. Run id pattern `116-test-selection-<UTC yyyymmddThhmmZ>`. Charts under git-ignored `artifacts/charts/116/`, each PNG under 40 KB, uploaded to Drive folder `issue-116` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/116-test-selection.md`.

  Peer-review checks, frozen with the spec: recompute the row count and the distinct five-digit `FIPS` count; recompute the Q1 denominator from the human-status and rural-urban rules and the Q2 denominator from the human-status and vulnerability rules; confirm `No records` and `Unknown` are not coded as zero and that null rural-urban and null vulnerability rows are exclusions; confirm the SQL does not select `EVIDENCE_COMPLETENESS`, incidence, a tier score, payload, limitation text, or geometry. The write-up names three spot-check counties chosen without reference to the estimates: the smallest `FIPS` with a published floor and rural-urban code 1; the smallest `FIPS` with no county-linked human record and rural-urban code 9; the smallest `FIPS` with a null vulnerability percentile, or an explicit zero if none exist.

  ```text
  uv sync --locked --extra dev --extra snowflake
  uv run python scripts/check_ml_agent_context.py
  MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_116_test_selection.py
  uv run python scripts/verify.py
  ```

## Amendment v1.2 — family completeness, before execution

This amendment is recorded before any live read. It does not change a cut, a seed, or a target.

- Holm is applied only when all four family contrasts have an estimable state-cluster interval. A smaller family is not adjusted. If any family contrast has no estimable interval, the disposition is revise, unless both share contrasts are not estimable, which remains stop.
- Each naive interval is an independent stream started at seed `1162027`. The three reproduction associations use that same naive seed. Their state-cluster draws use seed `6501`.
- Reproduction clusters use the county FIPS prefix, the key already used by `evidence_association_65`. The new family resamples the postal `STATE`. Those partitions name the same states on this atlas.

## Amendment v1.1 — disclosure, before execution

Matthew Caraway’s ruling on 2026-10-25: GitHub issue comments, pull-request bodies, and `docs/eda` results write-ups may name counties and may include county-level numbers, including counts under 11. `EDA.METRICS_LONG`, `EDA.CORRELATIONS`, `EDA.FINDINGS`, and the PNG charts still omit a count from 1 to 10. A chart is an aggregate figure. County names do not go into chart titles, axis labels, or Drive files. `EDA.FINDINGS` statements stay aggregate because the lab writer rejects a five-digit county id in prose.
