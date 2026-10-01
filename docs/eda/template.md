# <issue-number>: <question or decision>

- Issue: <link>; question/intended use: <bounded question>.
- Data: <governed source/table/view and release/version or snapshot/query identity>.
- Cohort: <inclusion/exclusion, geography, time window and availability cutoff>.

## Method and assumptions

<Method, preprocessing, test/metric selection, leakage/holdout protections,
random seed and nondeterminism if applicable. Separate planned from executed work.>

## Material findings and limits

<Findings, sample size, effect size/uncertainty where applicable; otherwise explain
why not applicable or not estimable. Missingness/value states, data quality,
coverage and interpretation limits. Preserve negative/inconclusive evidence.>

## Decision

<PROCEED / REJECT / DEFER / FOLLOW_UP / INCONCLUSIVE / NOT_ESTIMABLE, reason,
smallest next step, unresolved authority or evidence needed. No implied release.>

## Reproduction and retained evidence

- Code revision/run/config/data references: <exact identities; no local paths/secrets>.
- Entry points: <repository-relative SQL/code/config paths>.
- Commands and configuration assumptions: <exact replay and verification commands>.
- Lifecycle/review evidence references: <existing records, if applicable>.
- Transient artifacts intentionally not committed: <exports/caches/plots and reason>.
