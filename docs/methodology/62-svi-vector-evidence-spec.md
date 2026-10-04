# ML #62 analysis specification v1

Registered before SVI outcome inspection; exploratory ecological association.
Issue: https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/62.
Uses [analysis-spec-v1](analysis-spec-v1.md), parent #59 and #60.

- Question: Do county SVI distributions differ between stronger and weaker
  positive source-reported vector evidence? Inform contextual feature research,
  never causation, vector abundance, surveillance quality or individual risk.
- Estimand: county-weighted difference in distributions of national overall
  SVI percentile; direction ESTABLISHED minus REPORTED. Report median difference
  and probability of superiority (ties receive half weight), not a claim that
  Mann–Whitney is a test solely of medians. No population weighting.
- Sources: governed CDC ArboNET `cdc-ixodes-county-status-2025`, cumulative
  through 2025-12-31, and CDC/ATSDR 2022 national county SVI `RPL_THEMES`
  (ACS 2018–2022). Freeze matching governed release identities/digests before
  reading outcomes. These windows are contextual, not synchronous measurement.
- Unit: one unique canonical county FIPS per taxon in one compatible release.
  Source rows and county N are separate counts. Reject conflicting duplicate
  county statuses; do not pool taxa or repeated release rows as independent.
- Selection before outcomes: screen only source semantics, source status,
  geography and eligible unique county N. Candidate order IXODES_SCAPULARIS,
  IXODES_PACIFICUS; select the first with at least 30 unique counties in each
  exact positive state ESTABLISHED and REPORTED. This is a pragmatic EDA
  eligibility floor, not a power calculation or biological definition.
  No taxon has been selected and eligible N is unknown at registration.
- Exclude UNKNOWN, NO_RECORDS, no qualifying record, unmapped/ambiguous geography,
  null/suppressed SVI and invalid/sentinel percentiles; count each separately.
  Unknown is never negative. Require a governed national percentile in [0,1];
  do not substitute uninsured percent, category, population or state rankings.
- Method: two-sided Mann–Whitney U with tie handling, chosen before outcomes
  because the estimand concerns bounded distributions and equal shapes are not
  assumed. Report county N, mean/median/IQR, superiority effect and overlap.
  County-independent p-values are ancillary and invalid when residual spatial
  dependence is material; do not present them as dependence-adjusted evidence.
- Geographic check: always tabulate state counts/shares by group. A state with
  >25% of either group triggers leave-that-state-out sensitivity; also report
  within-state contrasts where both groups have >=10 counties. Use state-cluster
  bootstrap (seed 62, 2000 resamples) for uncertainty only with >=10 contributing
  states and >=5 states containing both groups. Otherwise descriptive only;
  unsupported independent inference is NOT_ESTIMABLE. State clustering does not
  remove cross-state spatial correlation or ecological confounding.
- Interpretation criteria: prespecified practical distribution effect is
  |P(A>B)+0.5P(A=B)-0.5| >=0.10 for MATERIAL_DIFFERENCE, 0.05–<0.10 for
  SMALL_DIFFERENCE, <0.05 for NO_MEANINGFUL_DIFFERENCE, conditional on defensible
  uncertainty and geographic robustness. These are EDA decision thresholds,
  not clinical/biological cutoffs. Wide uncertainty crossing categories or
  unstable geographic effects forbids a confident categorical conclusion.
- Stop: absent compatible positive states/adequate N or invalid grouping means
  scientifically NOT_ESTIMABLE. Inaccessible inputs mean ACCESS_BLOCKED and N
  unknown, not zero and not proof of scientific non-estimability. No stronger
  role, internal source scan, ingestion, source-contract change or model training.
- Execution state: PLANNED. No SVI outcome statistics inspected. No holdout
  labels used. One contrast; sensitivity is not a separate hypothesis family.
- Reproduction: issue-local availability SQL/code and durable
  `docs/eda/62-svi-by-vector-evidence-state.md`; results and any amendment will
  distinguish planned from executed work. Transient exports remain ignored.
