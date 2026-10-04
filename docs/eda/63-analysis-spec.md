# ML #63 registered analysis specification v1

Registered 2026-10-04 before inspecting SVI-by-RUCC result statistics. Source
contracts and published marginal coverage counts were inspected for provenance;
no joint outcome statistics were inspected. Parent #59 and #60 apply.

- **Question/decision:** How does governed overall SVI differ across official
  RUCC categories? Inform whether both remain candidate context families for
  later experiments. Association cannot establish predictive redundancy, final
  feature selection, causation, disease risk or individual risk.
- **Estimand:** Equal-county heterogeneity of the distribution of national
  overall SVI percentile across exact RUCC 2023 codes 1–9, in the governed
  canonical US county release. RUCC is categorical, never a continuous score.
- **Unit/cohort/time:** One unique canonical five-digit county FIPS, US counties
  and equivalents (50 states and DC), one immutable governed release. SVI 2022
  uses ACS 2018–2022; RUCC 2023 is a different vintage and point-in-time
  classification. No longitudinal or prediction-cutoff claim.
- **Sources:** Data-owned release `governed-2026-09-18-unknown-coverage`,
  `docs/contracts/semantic-release/governed-2026-09-15-manifest.json`;
  SVI source version `b8b6bf61-c6a3-4538-b0df-1b88c61720b1`, RUCC source version
  `87872b36-93ab-4a34-b70e-29569192cb48`. Require matching release/source identity
  and digests before analysis. Prefer existing immutable governed snapshot;
  otherwise only approved presentation read routes, never internal/raw tables.
- **Exclusions/missingness:** Keep source observation rows distinct from county
  N. Require unique FIPS; duplicate/conflicting counties or wrong source lineage
  block execution. Exclude and count missing/unknown/suppressed SVI or RUCC,
  sentinel/out-of-range/nonfinite SVI, and noninteger/non-codebook RUCC. SVI
  valid domain [0,1]; zero is observed. Do not fill missing with zero. No
  population weighting; population is a separate ACS estimate, not percentile.
- **Grouping:** Exact official codes 1–9, no outcome-adaptive regrouping. If any
  category has fewer than 20 eligible counties, descriptive-only and no omnibus
  inference. Codebook labels must come from official USDA documentation.
- **Status/method:** Exploratory, predeclared single Kruskal–Wallis rank omnibus
  with tie correction, H and rank epsilon squared `max(0,(H-k+1)/(N-k))`.
  Bounded percentile distributions and unequal group variances make the rank
  method preferable to unverified Gaussian/equal-variance ANOVA. It tests
  distributions, not median equality without common distribution shapes.
- **Dependence/uncertainty:** Counties are a finite release census, spatially
  dependent rather than independent random draws. Report H/effect descriptively;
  do not claim an IID chi-square p-value as valid inferential evidence. If input
  accessible, state-block bootstrap (2,000 replicates, seed 6302026) gives a
  sensitivity interval for effect, not a spatially validated confidence interval.
  States are imperfect dependence blocks. No repeated periods.
- **Sensitivity:** Official metro/nonmetro split (1–3 / 4–9), descriptive only;
  leave-one-state-out effect range to expose geographic influence. Preserve
  primary exact groups; disclose missingness by group where identifiable.
- **Post-hoc:** None unless epsilon squared >=0.05 and a state-block sensitivity
  interval excludes zero, and an actionable Product interpretation is recorded.
  Any subsequently justified post-hoc requires a dated amendment and at most
  three prespecified contrasts with Holm adjustment; never select pairs from
  attractive observed outcomes. Threshold 0.05 is an operational exploratory
  screen, not an official scientific redundancy definition.
- **Interpretation/disposition:** Distribution separation/overlap is contextual
  evidence only. Do not map effect thresholds to predictive redundancy labels.
  Retain both as candidates with later spatially held-out ablation required.
  `PLANNED` now; inaccessible input = `BLOCKED_ACCESS` (issue vocabulary may use
  NOT_ESTIMABLE with explicit access qualifier); scientific `NOT_ESTIMABLE`
  only for verified unsupported data/estimand. Do not report unobserved N as zero.
- **Stops/replay:** Stop on unavailable governed input, unverifiable identity,
  duplicate FIPS, unsafe access, unsupported geography or insufficient evidence.
  Persist reusable issue-local code/tests and findings in
  `docs/eda/63-svi-heterogeneity-by-rucc.md`; transient extracts remain ignored.
  Exact acquisition and replay commands and digests follow in that artifact.

## Amendment 1 — source availability, before any joint outcome inspection

The authorized DEV published pointer exposes `governed-2026-09-17-unknown-coverage`,
not the initially planned September 18 release. The bounded September 18 query
returned zero matching rows; this is release availability, not zero county N.
Use the published September 17 release, bundle SHA-256
`55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`, independently
matched to the data-owned September 17 parity report. Historical manifest at
data commit `731cd6f5f8dcf6f26499619eac8a7c5099369906` pins SVI source version
`86bed331-992b-4627-a992-ca4c5da7f392`, run
`9c13471a-e763-4864-bb69-5264b4800e34`, and RUCC source version
`84da74ac-e153-4fa1-9809-848c93eb12a7`, run
`6fad7869-a188-47dd-972b-dee0464321b1`. Both retain the same publisher artifact
SHA-256 as the initially planned release. Historical manifest generation time
`2026-09-17T19:00:00Z` and live `2026-09-17T12:00:00-07:00` denote the same
instant. The live release identity/digest, corroborated by its parity report,
is the execution identity. No claim of September 18 results.
Question, cohort, groups, exclusions and methods are unchanged.

## Independent-review clarification — 2026-10-04

The original amendment incorrectly described the two timezone representations
above as a generation-time difference. Independent review identified their
equivalence; corrected here without changing source identity, statistical
specification or results. Earlier commits preserve the correction audit trail.
