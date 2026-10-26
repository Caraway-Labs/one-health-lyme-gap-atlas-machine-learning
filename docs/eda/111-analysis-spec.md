# ML #111 cross-signal surveillance gaps: registered specification v1

- **Spec/version and owning issue:** `111-cross-signal-disagreement/v1`, [ML #111](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/111), parent [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md) and the draft [cross-signal disagreement contract](../contracts/cross-signal-disagreement-v1.md). Matthew Caraway authorized this story through the EDA orchestrator. This run does not authorize a Tier 1 change, a PROD write, a UI change, a public score, or the epic gate-C workflow.
- **Question / decision / allowed interpretation:** Where do the published human, tick, and pathogen documentation states disagree, and which of that list is a state-reporting or source-coverage artifact rather than a follow-up candidate? The decision is advance, investigate, or stop for an internal review list. A documentation state is a surveillance signal. It is not incidence, disease risk, biological absence, causation, or a training label. `No records` and `Unknown` are not negatives. A missing human floor is not zero. A published human floor is a lower bound (CDC floor 5). Do not rank counties by risk. Do not train on the Tier 1 score, on `EVIDENCE_COMPLETENESS`, or on latent-class membership.
- **Estimand:** On the pinned release, the county count and share of each mutually exclusive documentation class below; the five October 13 reference counts; the same counts by state and by Census region (the state block); a state-cluster percentile interval for each national and regional count and share; and, on the publishing-state cohort, four associations of the positive-CDC / no-human indicator with rural-urban code, social-vulnerability strata, and population size. The share of each class that sits in a zero-floor state is the reporting-intensity decomposition. No numeric residual, score, or disagreement flag from the contract baseline is an estimand.
- **Unit / cohort / geography / time:** One county on the pinned release, including the District of Columbia, Connecticut planning-region FIPS, Alaska, and Hawaii. The integrity gate is 3,144 rows, 3,144 distinct five-digit `FIPS`, and one `RELEASE_ID`. Census region comes from `coverage_audit.CENSUS_REGIONS`. The resampling unit is the state. This is one snapshot. It is not a change contrast and not a forecast.

  Vintages, read from `PRESENTATION.CURRENT_SOURCE_METADATA_V` (`SOURCE_KEY`, `VINTAGE` only) before any disagreement count and checked again at execution:

  | Source key | Vintage on the pin |
  | --- | --- |
  | `human` | `2023` |
  | `tick` | `through 2025-12-31` |
  | `pathogen` | `through 2025-12-31` |
  | `context_svi` | `2022 (2018-2022 ACS)` |
  | `context_rucc` | `2023` |
  | `context_nlcd_2025` | `C1V2-2025` |

  Human surveillance is calendar 2023. Tick and pathogen statuses are cumulative through 2025-12-31. Social vulnerability is 2022. The rural-urban code is 2023. Population on the atlas is the 2022 county layer named by #109. Those windows are not one time base. Every candidate row carries `ALT_VINTAGE_MISMATCH = TRUE` for that reason. The flag is not a county filter.

- **Variables / source / version:** Execution reads `PRESENTATION.CURRENT_RELEASE_V` first and stops unless the pin equals `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. That identity was read on 2026-10-26 after `scripts/check_ml_agent_context.py` returned `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. The October 13 reference release `governed-2026-10-06-nlcd-demo-cohort` is not re-queried.

  The only county object is `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. Columns: `FIPS`, `COUNTY`, `STATE`, `RELEASE_ID`, `POPULATION`, `SVI_PERCENTILE`, `RUCC_2023`, `HUMAN_STATUS`, `TICK_STATUS`, `BURGDORFERI_STATUS`, `IN_CONTIGUOUS_TICK_SCOPE`. No other column is selected. County rows may stay in memory. They are not written to a file, to git, or to Drive.

  Unit rule, the same rule as #116: if the maximum of `SVI_PERCENTILE` is greater than 1.5, divide that column by 100 and record the rescaling. Do not clip. Do not rescale a column whose maximum is at most 1.5. Bins and the 0.5 cut are applied after that rule.

- **Contract baseline:** The [cross-signal disagreement contract](../contracts/cross-signal-disagreement-v1.md) defines a scored disagreement only as a signed difference of two approved transforms on one comparison scale, summarized with a median and a median absolute deviation, then compared with an approved threshold. Human floors are counts, and tick and pathogen statuses are categorical documentation states. The contract forbids subtracting counts and rates, and it forbids making unrelated constructs comparable by normalization. No transform, reference minimum, or threshold `tau` is approved for this pair. Applying a library default would be the contract's `NEEDS_DECISION` failure. This run does not compute `d`, a center, a spread, a residual, a score, or a `DISAGREEMENT_FOR_REVIEW` flag. Those fields stay absent. `Unknown`, `No records`, and a missing human floor are insufficient evidence for that baseline. They are summarized as documentation states. They are not coded as zero, Established, Present, or a negative test.

- **Documentation classes:** Assign exactly one class, in this order. Positive tick documentation is `Established` or `Reported`. Positive pathogen documentation is `Present`. `No records` is unobserved. `Unknown` is insufficient.

  | Order | Class | Rule |
  | --- | --- | --- |
  | 1 | `insufficient_unknown` | Tick `Unknown`, or pathogen `Unknown`, or `IN_CONTIGUOUS_TICK_SCOPE` is false |
  | 2 | `human_without_vector_documentation` | Human `published_count_floor`, tick `No records`, pathogen `No records` |
  | 3 | `double_gap` | Human `no_county_linked_record`, tick `Established`, pathogen `Present` |
  | 4 | `established_no_pathogen_record` | Human `no_county_linked_record`, tick `Established`, pathogen `No records` |
  | 5 | `reported_pathogen_present` | Human `no_county_linked_record`, tick `Reported`, pathogen `Present` |
  | 6 | `reported_no_pathogen_record` | Human `no_county_linked_record`, tick `Reported`, pathogen `No records` |
  | 7 | `pathogen_without_tick_record` | Human `no_county_linked_record`, tick `No records`, pathogen `Present` |
  | 8 | `concordant_undocumented` | Human `no_county_linked_record`, tick `No records`, pathogen `No records` |
  | 9 | `concordant_documented` | Human `published_count_floor`, and not class 2 |

  Any other combination stops the run. Classes 2 through 7 are the candidate rows. Classes 1, 8, and 9 are not candidates and are not ranked.

  Derived predicates, not extra classes:

  | Predicate | Classes | October 13 reference |
  | --- | --- | ---: |
  | Positive CDC documentation, no county-linked 2023 human record | 3–7 | 1,269 |
  | 2023 human floor and neither tick nor pathogen documentation | 2 | 25 |
  | Unknown or out of scope | 1 | 35 |
  | Double gap | 3 | 228 |
  | Established-tick gap (the 810-county gap) | 3 + 4 | 810 |

  Headline checks, same release comparison as #109: 3,144 counties, 651 published floors, 2,493 with no county-linked human record. The 1,269 figure is epic #22 section 4.1 item 2. The 228 and 810 figures are section 4.1 and section 5.1. The 25 and 35 figures are section 4.1 item 2.

- **Reporting-intensity and source-coverage flags:** A zero-floor state is a state whose count of `published_count_floor` is 0. The October 13 comparison set, from epic #22 section 5.1, is Alaska, Arkansas, Colorado, Georgia, Hawaii, Idaho, Kansas, Louisiana, Missouri, Mississippi, Montana, Nebraska, New Mexico, North Dakota, Oklahoma, South Dakota, Texas, Washington, and Wyoming (`AK`, `AR`, `CO`, `GA`, `HI`, `ID`, `KS`, `LA`, `MO`, `MS`, `MT`, `NE`, `NM`, `ND`, `OK`, `SD`, `TX`, `WA`, `WY`). The live set is computed from the pin. It is not typed in as a filter before that count.

  Candidate flags, all prespecified:

  | Flag | Rule |
  | --- | --- |
  | `ALT_ZERO_FLOOR_STATE` | The county's state publishes no county floor |
  | `ALT_PARTIAL_REPORTING_STATE` | The state publishes at least one floor, and this county has no county-linked human record |
  | `ALT_PATHOGEN_UNOBSERVED` | Pathogen status is `No records` |
  | `ALT_TICK_REPORTED_NOT_ESTABLISHED` | Tick status is `Reported` |
  | `ALT_NO_VECTOR_RECORD` | Tick and pathogen are both `No records` |
  | `ALT_VINTAGE_MISMATCH` | True on every candidate |

  `REVIEW_READING`, first match:

  | Order | Reading | Rule |
  | --- | --- | --- |
  | 1 | `source_coverage` | Class 2, or class 7, or pathogen `No records` |
  | 2 | `reporting_artifact` | Zero-floor state |
  | 3 | `weaker_tick_record` | Tick `Reported` |
  | 4 | `follow_up` | Remaining candidates: established tick, pathogen `Present`, no county-linked human record, in a state that publishes at least one floor |

  `source_coverage` means the blank vector status is unobserved, which the contract does not treat as disagreement evidence. `reporting_artifact` means the human blank is the state's publication rule. `weaker_tick_record` is `Reported`, not `Established`. `follow_up` is the residual double gap after those explanations. None of the four readings is a risk rank.

  Supporting-evidence tokens, from the positive side only: `human_published_floor`, `tick_established`, `tick_reported`, `pathogen_present`. Contradicting-evidence tokens name the documentation gap, not a biological contradiction: `human_no_county_linked_record`, `tick_no_records`, `pathogen_no_records`.

- **Missingness rule:** Do not impute. Do not replace a gap with zero, Established, or Present. A null rural-urban code leaves the rural-urban tables and the rural-urban contrasts. A null vulnerability percentile leaves the vulnerability tables and that contrast. A null or non-positive population leaves the population tables and that contrast. Those exclusions are counted. `No records` and `Unknown` stay levels. A duplicate `FIPS`, a `FIPS` that is not five digits, a state outside the Census map, a mixed release, or an unmapped class stops the run.
- **Exploratory or confirmatory:** Confirmatory for the release pin, the vintage strings, the headline counts 3,144 / 651 / 2,493, the five reference counts, and the nineteen-state set. The class counts, the bootstrap intervals, and the four associations are the prespecified descriptive results. Nothing in the October 13 narrative is used to change a class rule, a cut, a seed, or the disposition thresholds after the counts are seen.
- **Method / assumption rationale:** The atlas statuses are a county census with explicit levels, so a count of counties in each class answers the gap question. Counties in one state share reporting rules, so uncertainty resamples states. The #116 decision matrix is reused rather than reopened: Welch t, paired t, Mann-Whitney, Wilcoxon signed-rank, ANOVA, Kruskal-Wallis, chi-square as a test, Fisher exact, Pearson, and regression stay rejected. Chi-square remains only the numerator inside `test_selection.cramers_v`, reported as a companion on the metro 2×2 and not as a test. Spearman, via `test_selection.spearman_rho`, is the rank coefficient. Share differences and Spearman coefficients use `test_selection.state_cluster_interval` (2,000 replicates, percentiles 2.5 and 97.5, linear index `(n-1)*p`, the #116 rule). A county resample from `test_selection.resample_interval` is the dependence diagnostic. Holm, via `test_selection.holm`, adjusts the four tail shares. Benjamini-Hochberg is not used: #116 rejected it for a four-contrast family, and this repository has no Benjamini-Hochberg helper to reuse.

  The association cohort drops zero-floor states. That is the reporting-intensity adjustment: a state that publishes no county floor makes every positive-CDC county a human gap by rule, so a national contrast would restate that rule. The same four point estimates on all states are the sensitivity. No second interval is fit for the sensitivity.

  | Piece | Setting |
  | --- | --- |
  | Indicator | Classes 3–7 (positive CDC documentation and no county-linked human record) |
  | H1 | Share in rural-urban codes 1–3 minus share in codes 4–9 |
  | H2 | Share where vulnerability is strictly below 0.5 minus share where it is at least 0.5 |
  | H3 | Spearman of rural-urban code with the indicator |
  | H4 | Spearman of log10(population) with the indicator |
  | Cluster seed | `1112026`, restarted for each interval |
  | Naive seed | `1112027`, restarted for each association interval |
  | Failure | A draw with a zero group denominator, a degenerate rank, or a non-finite value is a failure. If more than 5% fail, or fewer than 10 states remain, the interval is not estimable |
  | Multiplicity | Holm on H1–H4 only when all four cluster intervals are estimable. Otherwise Holm is not applied |
  | Sensitivity | Material when an all-state point estimate moves by at least 0.02 from the publishing-state estimate, or when the two point estimates have opposite signs |
  | Region intervals | Resample the states inside the region. Northeast has 9 states, so its interval is not estimable under the 10-state minimum. That minimum is not lowered after the result |
  | State counts | Point counts only. One state is one cluster, so a state count has no state-cluster interval |

  Descriptive stratum tables, not in the Holm family, use the #116 rural-urban codes and vulnerability bins (edges 0, 0.2, 0.4, 0.6, 0.8, 1, plus a value of exactly 1) and the published population bins from the October exhaustive table: under 10,000; 10,000 to under 50,000; 50,000 to under 100,000; 100,000 to under 500,000; 500,000 or more. The indicator share is the cell. A count from 1 to 10, or a binary complement from 1 to 10, is not written to a lab aggregate or a chart.

- **Spatial / temporal dependence:** The reported interval resamples states. It does not cover dependence that crosses a state line. It is not a survey-design confidence interval. The human year and the cumulative tick and pathogen window are not aligned, so a later tick or pathogen record can sit beside a 2023 human blank without being a same-year contradiction.
- **Effect-size / uncertainty output:** Class counts and shares, state and region counts, national and regional percentile intervals where estimable, the four publishing-state estimates with cluster and naive intervals, Holm-adjusted tail shares when the family is complete, and the zero-floor composition of each class. Review yield in the contract's sense is `NOT_ESTIMABLE`: this run does not have an independent adjudication sample. The false-positive review is an illustration of the flags, not a yield.
- **False-positive review:** After classification, and without reference to the association estimates, list up to three counties in each of these groups, smallest `FIPS` first: `double_gap` with `reporting_artifact`; class 2 (`human_without_vector_documentation`); `double_gap` with `follow_up`. Names and county-level numbers from that list may appear in the results write-up, the pull-request body, and the issue comment. They do not appear in chart titles, axis labels, Drive files, `EDA.FINDINGS`, or `EDA.METRICS_LONG`.
- **Candidate table:** `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.CROSS_SIGNAL_CANDIDATES_111`, one row per candidate county, keyed by `RUN_ID` and `FIPS`. Columns are the class, the three statuses, supporting-evidence tokens, contradicting-evidence tokens, the six alternative flags, `REVIEW_READING`, state, Census region, rural-urban code, vulnerability percentile, population, scope flag, and the county name. County rows are not written anywhere else. The shared lab writers do not grant `SELECT`. This story does not add a grant. `OH_LYME_PROD_READ` cannot count the new table until an owner grants it.
- **Small-cell and write rule:** `EDA.METRICS_LONG` uses `write_eda_results`. `EDA.FINDINGS` and `REGISTRY.QUERIES` use the lab helpers. A count from 1 to 10 is removed, including interval endpoints for that count. A zero on a denominator of at least 11 is kept. Charts are aggregate. A suppressed cell is labeled `<11` and is not drawn at its true height. `REGISTRY.QUERIES` stores statement text, SHA-256, the Snowflake query id, row cardinality, and elapsed time. Statements that mention `PART_TEXT`, `CONTEXT_LIMITATIONS`, `PAYLOAD`, `GEOMETRY_JSON`, or a limitations column are rejected.
- **Key caveat / stop conditions:** Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Stop if the live release id or bundle SHA differs from the pin. Stop if the county count is not 3,144, if `FIPS` are not unique five-digit ids, if any state is outside the Census map, if a vintage string differs from the table above, or if any county is unmapped. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or any column other than the list above. Do not select payload, part text, limitation text, or geometry. A query still running at 10 minutes is cancelled.
- **Result disposition:** **PLANNED.** After execution, apply this rule without changing it.

  **stop** when a gate above fails, or when the `follow_up` reading of `double_gap` has fewer than 11 counties.

  **revise** when any headline count, reference count, vintage string, or the nineteen-state set differs from this spec.

  **investigate** when the pin, the vintages, the headline counts, the five reference counts, and the nineteen-state set match, and the `follow_up` double gap has at least 11 counties.

  **advance** is not available from this run. Epic #22 section 4.1 item 2 says to inspect and not to rank by risk, and it leaves a public map or a workflow to a separate governance and epidemiology review. A matched list is a lab review table, not a product score.

  An association interval that is not estimable, or a material sensitivity, is stated beside **investigate**. It does not change the word, and it does not authorize a stronger claim. The numeric contract baseline stays unapplied under every word.
- **Reproduction / evidence:** SQL in `sql/validation/111_cross_signal_disagreement.sql`. Runner `scripts/eda_111_cross_signal.py`. Logic `src/lyme_gap_atlas_ml/cross_signal_disagreement.py`. The bootstrap, Spearman, Cramér's V, and Holm calls use `src/lyme_gap_atlas_ml/test_selection.py`. Lab writes reuse `eda_writer.write_eda_results` and `eda_lab_writers.write_findings` and `write_queries`. The candidate insert lives in `src/lyme_gap_atlas_ml/snowflake/cross_signal_candidates.py`. Run id pattern `111-cross-signal-disagreement-<UTC yyyymmddThhmmZ>`. Charts under git-ignored `artifacts/charts/111/`, each PNG under 40 KB: `disagreement-type-matrix` (Census region by class) and `state-review-counts` (state counts of classes 3–7). Upload to Drive folder `issue-111` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/111-cross-signal-disagreement.md`.

  ```text
  uv sync --locked --extra dev --extra snowflake
  uv run python scripts/check_ml_agent_context.py
  MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_111_cross_signal.py
  uv run python scripts/verify.py
  ```
