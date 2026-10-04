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
  SMALL_DIFFERENCE, <0.05 for NO_MEANINGFUL_DIFFERENCE **in directional rank
  superiority only**, conditional on defensible
  uncertainty and geographic robustness. These are EDA decision thresholds,
  not clinical/biological cutoffs. Wide uncertainty crossing categories or
  unstable geographic effects forbids a confident categorical conclusion.
  Superiority near 0.5 does not establish equivalent distributions or equal
  spreads; always retain group IQR, ranges, common-range overlap and empirical
  CDF separation. For example {0.1,0.9} versus {0.4,0.6} has superiority 0.5
  despite different spread. Median/mean/IQR descriptors are separate estimands.
- Stop: absent compatible positive states/adequate N or invalid grouping means
  scientifically NOT_ESTIMABLE. Inaccessible inputs mean ACCESS_BLOCKED and N
  unknown, not zero and not proof of scientific non-estimability. No stronger
  role, internal source scan, ingestion, source-contract change or model training.
- Execution state: PLANNED. No SVI outcome statistics inspected. No holdout
  labels used. One contrast; sensitivity is not a separate hypothesis family.
- Reproduction: issue-local availability SQL/code and durable
  `docs/eda/62-svi-by-vector-evidence-state.md`; results and any amendment will
  distinguish planned from executed work. Transient exports remain ignored.

## Outcome-blind route amendment — 2026-10-04

Parent review identified the preexisting approved V072 consumer route
`PRESENTATION.CURRENT_COUNTY_ATLAS_V`, with `CURRENT_RELEASE_V` and
`CURRENT_SOURCE_METADATA_V`. The first observation-view audit was too narrow
to establish global input unavailability. Audit these existing consumer views
using `sql/validation/62-county-atlas-screen.sql` before any SVI summaries.
Keep the same question, taxon order, positive states, N thresholds and method.
Source status, unique county/state counts, FIPS integrity and SVI missing/domain
eligibility are outcome-blind screening; no distribution statistics are read.
Value visibility is separate from matching immutable release/source/vintage
authority. Do not retry denied private objects or change identities to obtain
restricted source data. Existing public API/approved receipts may be inspected
for provenance without using alternative raw-source access.

## Offline implementation amendment — before any outcome results

Independent review requested executable inference/effect/sensitivity code.
Use a tie-corrected normal-approximation Mann–Whitney U with continuity
correction (>=30 complete counties each); its county-independence p-value is
explicitly ancillary, not state-adjusted inference. State-cluster bootstrap
uses the union of states, resampling whole states with replacement, fixed seed
62 and 2,000 draws; discard draws missing either group and report draw counts.
Require >=10 represented states, >=5 mixed states and >=90% valid draws for a
cluster interval. Do not treat nominal cluster confidence as removing
cross-state correlation. Return no confident effect category when its interval
crosses category boundaries or a dominant-state exclusion changes the point
category (or leaves fewer than 30 counties in either group).
Within-state >=10/group contrasts and IQR/range/CDF overlap stay descriptive.
The near-0.5 counterexample above must remain a regression test. This amendment
changes interpretation precision, not taxon/state selection or the estimand;
no SVI outcome statistics have been inspected.

## Shared-input gate record — before any alternative outcome analysis

The parent's shared DEV consumer capture SHA-256
`be74f3affff2e7753f14e7b804d672fb83d21eabe8f1dc4abead873ea21e8e45`
matches current DEV release September 17 and again has only Unknown taxa.
Shared PROD public summary SHA-256
`5dbc0e4a66e1d702b5deafc3a430d62fe317984a6ee2e5c1759b74182f06e9ed`
matches September 18 but lacks species states and raw SVI. Combined tick status
must not replace species-specific evidence; no taxon or PROD eligible N selected.
A single documented public county-detail probe at fixed county 01001 confirmed
the required fields exist at that PROD release/hash. It is a field/provenance
availability check, not a representative cohort, eligibility screen or result.
No outcome distribution statistics were inspected. No valid scientific scope
or source-input amendment has been admitted for alternative outcome execution.
Remain stopped pending a bounded approved species/SVI cohort projection with
matching source/release/vintage and metadata authority. No broad detail crawl,
private-object retry, new grants, alternate restricted-source identity or
change to question, taxon order, states, method or thresholds.

## Published-projection descriptive EDA amendment — before outcomes

Parent scientific review corrected an overstrict gate: private source-record
hashes and REVIEWED #191/#193 metadata envelopes are not universal prerequisites
for descriptive EDA of the already-governed published county projection.
Use the existing semantic-release consumer boundary plus immutable release/bundle,
published source/vintage semantics, canonical county coverage, explicit status
and missingness handling, capture digest and interpretation limits. Native
source-lineage verification and ML feature admission remain separate, unclaimed
activities; unavailable private proof is a caveat, not a stop for this scoped EDA.
This explicitly supersedes the private-authority prerequisite above without
relaxing species mapping or replacing raw SVI with scores.

Authorized acquisition: one existing PROD `CURRENT_COUNTY_ATLAS_V` consumer
capture under the existing runbook-authorized runtime-read identity, not another
identity retry against private objects. Verify all session context fields first.
Read only release/bundle before and after and <=3,145 ordered county rows with
release ID, FIPS/state, scapularis_status, pacificus_status, svi_percentile, and
burgdorferi_status for the coordinated #65 evidence gate. Pin September 18
release and bundle `038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`;
30-second statement timeout. No object/PROD writes, credential/config changes,
raw/private source read, national API fanout or upload.
Freeze capture/digests, screen species status and eligible county N without
SVI distribution statistics, then commit selected taxon/input identity before
outcomes. Preserve original question, positive states, >=30 N, county weighting,
cumulative tick through 2025-12-31 versus 2022 SVI/ACS 2018–2022 context,
method, sensitivities, thresholds and noncausal interpretation. The result is
exploratory descriptive association in this published county release, not
native-data scientific validation or ML feature admission.
