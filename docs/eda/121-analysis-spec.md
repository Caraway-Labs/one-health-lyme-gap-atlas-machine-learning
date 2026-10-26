# ML #121 county contrasts: registered specification v1

- **Spec/version and owning issue:** `121-county-contrasts/v1`, [ML #121](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/121), parent epic [ML #118](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/118), program epic [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway authorized this story through the EDA queue on 2026-10-26. This run does not authorize a Tier 1 change, a PROD write, an API, a pipeline, a UI, or a public score.
- **Question / decision / allowed interpretation:** Which two or three contrasts explain most of the categorical difference among counties? Do those contrasts separate reporting completeness, rurality, or tick species? Where do the aligned counties and the double-gap counties sit on that map, relative to the other three surveillance situations in epic #118? Does one pre-registered shift of a population bin edge move the axes? The method decision is keep, revise, or stop. The product decision is advance, investigate, or stop. An axis is an exploratory exhibit. It is not a feature for k-prototypes, a mixture model, or any other model. The map is not a risk surface and not a production score. A status is a surveillance signal. It is not incidence, risk, or causation. `No records` and `Unknown` are not negatives. A missing human floor is not zero. A published human count is a lower bound (CDC floor 5). Say published floor, not incidence.
- **Estimand:** On the pinned release, Greenacre-adjusted inertia shares for the first three axes of one multiple correspondence analysis; the category contrasts that define those axes; the county counts and axis-1/axis-2 centroids of the five epic #118 situations; and the pre-registered sensitivity similarity below. #109 supplies the status definitions and the joint cells that named 443 and 228. #114 supplies the documentation reading of these attributes and the SVI unit rule; this story does not refit those associations. #123 supplies state reporting-regime groups; those groups are not inputs and are not features here.

## Unit, cohort, and pin

One county on `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. The expected county count is 3,144. This is one snapshot. It is not a change contrast and not a forecast. Human surveillance is calendar 2023. Population and social vulnerability are the 2022 county layer. The rural-urban code is 2023. Tick species and pathogen statuses are cumulative through 2025-12-31. Those vintages are not one time base.

Pin `RELEASE_ID`, `SCHEMA_VERSION`, `BUNDLE_SHA256`, `METHODOLOGY_VERSION`, and `SCOPE` from `PRESENTATION.CURRENT_RELEASE_V` before the fit. The pin, the same pin as #109, is release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`.

Objects and columns read:

| Object | Columns |
| --- | --- |
| `PRESENTATION.CURRENT_RELEASE_V` | `RELEASE_ID`, `SCHEMA_VERSION`, `METHODOLOGY_VERSION`, `SCOPE`, `BUNDLE_SHA256` |
| `PRESENTATION.CURRENT_COUNTY_ATLAS_V` | `FIPS`, `COUNTY`, `STATE`, `RELEASE_ID`, `POPULATION`, `SVI_PERCENTILE`, `RUCC_2023`, `HUMAN_STATUS`, `TICK_STATUS`, `SCAPULARIS_STATUS`, `PACIFICUS_STATUS`, `BURGDORFERI_STATUS` |

No other column is selected. Do not select payload, part text, limitation text, geometry, case floors, incidence floors, evidence completeness, uninsured fields, or a tier score. County rows may stay in memory. They are not written to git, to a chart, or to Drive. If county coordinates are stored, the only destination is `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.COUNTY_MCA_COORDINATES_121`.

## Variables and bin edges

Seven active variables. The bin edges below were chosen before any axis is computed.

| Variable | Coding | Why this coding |
| --- | --- | --- |
| Social vulnerability | Four quartiles of the unit-scaled percentile | CDC/ATSDR groups the percentile in quarters. Quartiles are equal-width on a percentile, so they are not cut from this map |
| Population | Four ordered size bands | County population is skewed. Equal-width bins would collapse the map. The cuts are three interior edges already named in the #122 histogram |
| Rural-urban code | Codes 1 through 9, unbinned | #109 already counted every code at or above 76 counties. Binning would hide rurality |
| Human status | Published levels | #109: `published_count_floor`, `no_county_linked_record` |
| Blacklegged tick | Published levels | #109: `Established`, `Reported`, `No records`, `Unknown` |
| Western blacklegged tick | Published levels | Same four levels. The species stays separate from the blacklegged tick, as epic #118 requires |
| Pathogen status | Published levels | #109: `Present`, `No records`, `Unknown` |

`TICK_STATUS` is not an active MCA variable. It is the epic situation predicate, because #109 showed `TICK_STATUS = Established` equals the sum of the two species Established counts.

Unit rule, the #114 rule, applied before the SVI bins: if the maximum of `SVI_PERCENTILE` is greater than 1.5, divide that column by 100. Do not clip. A value outside [0, 1] after that rule stops the fit.

Primary SVI edges, right-closed: 0.25, 0.50, 0.75. Labels `q1_low`, `q2`, `q3`, `q4_high`. A value of 0.25 is `q1_low`. A value of 1 is `q4_high`.

Primary population edges, left-closed: 10 thousand, 50 thousand, 250 thousand. Labels `lt_10k`, `10k_to_50k`, `50k_to_250k`, `ge_250k`. A population of 10 thousand is `10k_to_50k`. A population of 50 thousand is `50k_to_250k`. A population of 250 thousand is `ge_250k`.

Category frequencies before these MCA bins:

- Native levels of rural-urban code, human status, both tick species, and pathogen status.
- A finer population histogram using the #122 interior edges 10, 25, 50, 100, 250, and 500 thousand, and 1 million. This is a frequency exhibit. It is not the MCA coding.
- A finer social-vulnerability histogram at tenths from 0.1 through 0.9. Same role.

A null or non-positive population, a null SVI, a rural-urban code outside the integers 1 through 9, a duplicate or non-five-digit `FIPS`, a state that is blank, a mixed release id, or a status outside the #109 levels stops the fit. Do not impute. Do not replace a gap with zero, Established, or Present.

## Rare categories and inertia

Do not drop or pool a category. Pooling would be a second binning after the edges above. A category is rare when fewer than 30 counties carry it. On the #109 counts, western-blacklegged `Reported` (15 counties) is rare. `Unknown` (35) is not. Rare categories stay in the indicator matrix so the frequency table can show them.

Headline inertia is the Greenacre adjustment, not the Benzécri percentage and not the raw indicator-matrix share. Both adjustments use the same corrected eigenvalues. Benzécri percentages divide only by the sum of those corrected eigenvalues, which drops inertia at or below `1/Q` and inflates the first axes. Greenacre divides by the average off-diagonal inertia instead. Raw indicator inertia counts the artificial diagonal of the Burt matrix. The fit stores all three. The briefing quotes Greenacre shares.

Notation: `Q = 7` variables, `J` categories that occur, indicator eigenvalues `λ` from the correspondence analysis of the complete disjunctive table. Corrected eigenvalue, the prince / Benzécri form:

```text
λ*_k = (Q / (Q - 1) * (λ_k - 1/Q))^2    if λ_k > 1/Q
λ*_k = 0                                 otherwise
```

Greenacre denominator, the prince form of the average off-diagonal inertia:

```text
λ_tot = (Q / (Q - 1)) * (sum_k λ_k^2 - (J - Q) / Q^2)
share_k = λ*_k / λ_tot
```

`sum_k λ_k^2` is the squared Frobenius norm of the Gram matrix of the standardized residuals, over every component, not only the first three. A non-positive denominator stops the fit. Shares are not renormalized to sum to 1. A component with `λ_k <= 1/Q` has share 0 and is not given a contrast.

Column contribution on axis k is `mass_j * coordinate_jk^2 / λ_k`. Contributions on one axis sum to 1.

Sign rule, deterministic, applied before any contrast is named: flip axis k so the category with the largest contribution has a positive coordinate. Ties break by category id ascending. Seed `1212026` is stored. `numpy.linalg.svd` does not consume it. The seed is not used to jitter, subsample, or rotate. No remaining randomness is intended.

## Contrasts and the five situations

A contrast is one sentence for one axis. It names the highest-contribution category on the positive side and the highest-contribution category on the negative side. A third category is named only when it sits on one of those sides, its contribution is at least 0.10, and it is within 0.02 of that side's leader. At most three contrasts are named, and only for axes whose Greenacre share is positive, in axis order. The sentence is filled from a fixed phrase table. It does not call the axis a risk gradient.

The five epic #118 situations are predicates on published columns, the same reading as the #109 joint cells and the #111 double-gap predicate. They are not a partition. The double-gap counties are inside the wider established-tick gap.

| Situation | Rule | October reference |
| --- | --- | ---: |
| Aligned | Human `published_count_floor`, tick `Established`, pathogen `Present` | 443 |
| Double gap | Human `no_county_linked_record`, tick `Established`, pathogen `Present` | 228 |
| Wider gap | Human `no_county_linked_record`, tick `Established` | 810 |
| Human floor without a pathogen record | Human `published_count_floor`, pathogen `No records` | 207 |
| No human, tick, or pathogen documentation | Human `no_county_linked_record`, tick `No records`, pathogen `No records` | 1,189 |

`Unknown` is not folded into `No records`. If a live count differs from the reference, report the live count. That mismatch does not stop the fit. It makes the method disposition revise.

Group location is the count and the mean of the county principal coordinates on axes 1 and 2. The chart is a hexbin of all counties plus those centroids. It is not a scatter of county points. A hex cell whose count is below 11 is not drawn. A confidence ellipse is the 95 percent ellipse of the centroid: sample covariance with divisor `n - 1`, divided by `n`, at chi-square 5.991464547107979 (df 2, probability 0.95). The ellipse is drawn only when `n` is at least 11 and the covariance is positive definite. County names do not appear on the chart.

Separation ratio, used only for the product decision: Euclidean distance between the aligned centroid and the double-gap centroid, divided by the pooled within-group root-mean-square distance from each county to its own centroid. The root-mean-square uses division by the group count. The pool weights those two mean squares by the group counts. This ratio is not a causal effect.

## Sensitivity

One change, and only one: move the population edge at 50 thousand to 100 thousand. The edges at 10 thousand and 250 thousand stay. SVI edges stay. Status codes stay. Refit with the same sign rule.

Stability, all three required:

| Check | Gate |
| --- | --- |
| Spearman rank correlation of county scores on axis 1, after sign alignment | at least 0.90 |
| The same correlation on axis 2 | at least 0.90 |
| Procrustes similarity of shared category coordinates on axes 1 and 2 | at least 0.90 |

Axes are matched in inertia order. They are not swapped. Sign alignment multiplies a sensitivity axis by the sign of its Pearson correlation with the primary county scores, then Spearman is computed. Axis 3 Spearman is reported and is not gated.

Procrustes uses the categories whose definitions did not change: rural-urban codes and the four status variables. Binned population and SVI categories are excluded because the one change redefines the population bins. Similarity is `1 - disparity` from the orthogonal Procrustes criterion after each cloud is mean-centered and scaled to Frobenius norm 1: disparity is `1 - (sum of singular values)^2`. A shared set smaller than 11 categories fails the gate.

## Disposition

**Method.** **stop** when the context check fails, the pin differs, the county count is not 3,144, the published-floor count is not 651, the no-county-linked count is not 2,493, a required level or field is illegal, a variable has fewer than two observed levels, or the Greenacre denominator is not positive. **revise** when the fit completes and any reference situation count differs, or a rare category has the largest contribution on axis 1 or axis 2, or the sensitivity gate fails. **keep** otherwise.

**Product.** **stop** when the method is stop. **advance** when the method is keep and the separation ratio is at least 0.50. **investigate** otherwise. Advance means the exhibit is stable enough to brief. It does not authorize a model, a rank, or a public risk map. The axes are not passed to another model in this epic.

- **Exploratory or confirmatory:** Confirmatory for the release pin, the counts 3,144 / 651 / 2,493, and the five situation counts as reproduction checks. Exploratory for the axis contrasts. Nothing in the results is used to move an edge, change the rare threshold of 30, change the stability gates, or add a variable.
- **Spatial / temporal dependence:** Counties in one state share reporting rules. No p-value and no county-independent interval are reported. The sensitivity refit is the stability evidence. The 2022, 2023, and 2025 vintages are not aligned.
- **Effect-size / uncertainty output:** Greenacre shares, Benzécri corrected eigenvalues, unadjusted eigenvalues, category contributions, situation counts and centroids, Spearman correlations, and Procrustes similarity. The centroid ellipse is a chart geometry, not a survey interval.
- **Key caveat / stop conditions:** Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or conformed history. Do not select payload, part text, limitation text, or geometry. A query still running at 10 minutes is cancelled. Small cells: a count from 1 to 10 is omitted from `EDA.METRICS_LONG`, experiment metrics, chart labels, and Drive files. A zero count is not a category column. The results write-up may name a small category count. It does not name a county unless a later amendment says so. This spec does not name counties.
- **Result disposition:** **PLANNED.** Apply the two rules above after the fit without changing them.
- **Reproduction / evidence:** SQL in `sql/validation/121_county_mca.sql`. Runner `scripts/eda_121_county_mca.py`. Logic `src/lyme_gap_atlas_ml/county_mca.py`. Lab coordinate writer `src/lyme_gap_atlas_ml/snowflake/mca_coordinates.py`, reusing `eda_writer.write_eda_results` and `eda_lab_writers.write_findings` / `write_queries`. Run id pattern `121-county-contrasts-<UTC yyyymmddThhmmZ>`. Seed `1212026`. Charts under git-ignored `artifacts/charts/121/`, each PNG under 40 KB: `greenacre-scree`, `category-pulls`, `axis-map`. Upload to Drive folder `issue-121` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/121-county-contrasts.md`. Inserts are insert-only. A second invocation with the same run id does not insert again. No `DELETE`. `GRANT SELECT` on the new coordinate table to `OH_LYME_PROD_READ` is attempted once; a failed grant is recorded and is not retried as a stronger role.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_121_county_mca.py
uv run python scripts/verify.py
```
