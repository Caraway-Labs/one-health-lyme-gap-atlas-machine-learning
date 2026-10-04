<!-- Review draft only. Publish once on ML #86 only after independent owner review. -->

### Phase 1 label feasibility result

**Overall recommendation:** BLOCK

**Best candidate:** NONE admitted. Best next qualification lead: official
Pennsylvania county report-year Lyme counts (Candidate A).

**Why:**
- No candidate currently proves a county-time outcome with an executable
  scientific meaning and historical availability for a Phase 1 experiment.
- Fresh CDC aggregates reproduce 7,681 published county-years, but the governed
  county sums remain privacy-protected floors rather than proven complete totals.
- Official PA data is materially more complete: 3,015 county-year cells, of
  which 2,358 are numeric and 657 suppressed. It merits focused qualification;
  it does not prove historical vintages or surveillance-priority ground truth.
- The CDC tick-bite tracker is regional. DATA #384 / merged PR #591 already
  establishes the qualification limits; county allocation is unsupported.
- Current CDC vector/pathogen snapshots do not prove historical detection
  transitions; NEON's delivered site evidence is NOT_COUNTY_REPRESENTATIVE.

**Feasibility evidence:**
- usable periods: none admitted for a Phase 1 experiment. Retrospective source
  support: CDC report years 2008–2023; PA compilation 1980–2024.
- county-period N: CDC 7,681 published keys from 45,513 demographic/status
  rows. PA 3,015 cells across 67 counties; 2011–2016 has 392 numeric/10
  suppressed cells, and 2017–2019 has 200 numeric/1 suppressed cell. These
  source counts are not approved training examples. Usable historical class
  counts for regional/transition candidates remain UNKNOWN.
- positive/negative counts if applicable: no Phase 1 class is defined. PA's
  displayed count signs are 1,659 positive / 699 explicit zero / 657 suppressed
  overall; primary-window signs are 389 / 3 / 10. Suppressed and missing
  surveillance are never negatives. CDC exact directional classes remain
  unproved under the earlier complete-count interval rule; ML #64 separately
  owns published-lower-bound change feasibility.
- geography coverage: CDC has 782 published counties pre-2022 and 688
  post-2022; WI/PA/NY/MN/VA account for 54.9% of pre-2022 keys. PA is one
  state only. NSSP has five native regions; delivered NEON evidence is one
  site/month. The approved DEV presentation has 3,144 counties but only 2023.
- point-in-time status: strict historical reconstruction is NOT PROVEN.
  CDC catalog publication is August 2025; PA workbook modification is September
  2025. Neither timestamps original historical values. Dated PA reports are
  useful leads, with revisions still to reconcile.
- major exclusions: unallocated county identities, unknown category
  completeness, privacy suppression, incompatible reporting methods/eras,
  absent publication/revision lineage, unsupported historical population,
  regional allocation and unsampled county-area inference.

**Rejected/deferred candidates:**
- Candidate A: DEFER official PA qualification; BLOCK exact CDC totals/rates
  from current floors. Count/rate forecasts require a separate proxy decision.
- Candidate B: BLOCK county labels; DEFER native regional comparator under
  existing DATA #384 / PR #591.
- Candidate C: DEFER newly published county-evidence events until dated
  snapshots/revision causes and actual transitions are proven. BLOCK biological
  emergence/absence from current cumulative status and NEON county labels.

**Required next action:**
- Independently review and merge PR #87's research artifact after approval.
  Keep #86 open through the review and single-comment publication gate.
- Use existing DATA #110/#111 to qualify PA 2011–2016 and separately
  2017–2019: case inclusion, residence/report-year meaning, suppression,
  county identity, dated vintages and revision/maturity. Reconcile the 2021
  report/workbook zero-count discrepancy. No ingestion is authorized.
- DATA #113 then checks historical availability; ML #23 decides whether
  reported counts answer Phase 1 or belong solely to Phase 2. If no defensible
  proxy is selected, record a descriptive/unsupervised surveillance-review
  pivot. Reuse #429/#384 for their distinct remaining qualification gates.

**Product interpretation boundary:**
Reported Lyme counts describe cases captured by surveillance among residents;
ED tick-bite activity describes care-seeking; a newly published vector/pathogen
record describes evidence becoming available. None directly proves true
incidence, individual risk, biological emergence, absence, underreporting or
the benefit of more surveillance. Atlas must retain these meanings and unknown
states, and must not train on an existing heuristic priority as ground truth.

**Links:**
- [Durable EDA artifact](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/blob/codex/ml-86-label-feasibility/docs/eda/86-phase1-label-feasibility.md)
- [Draft PR #87](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/87)
- [Official PA source](https://www.pa.gov/agencies/health/diseases-conditions/infectious-disease/vectorborne-diseases/tick-diseases/dashboard-data)
- [DATA #110](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/110), [#111](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/111), [#113](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/113)
- [DATA #384 / merged PR #591](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/pull/591), [#429](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/429), [NEON #162 evidence](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/162#issuecomment-5789110264)
- [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22), [#23](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/23)
