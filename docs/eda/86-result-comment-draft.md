<!-- Review draft only; publish once after independent owner review. -->

### Phase 1 label feasibility result

**Overall recommendation:** BLOCK a supervised Phase 1 experiment now; DEFER concrete qualification leads.

**Best candidate:** Maryland official county-year outcomes, conditional on reproducing the reviewer receipt. Pennsylvania is the locally reproduced fallback. No surveillance-priority label is admitted.

**Why:** Published outcomes and coarse vector-status transitions exist. Historical predictor availability, a defensible later holdout and the choice of a surveillance-priority proxy remain unproved. Late outcome publication alone does not rule out retrospective evaluation: predictors must be frozen at their decision date, while outcomes can mature later.

**Feasibility evidence:**

- usable periods: no admitted experiment periods. Retrospective source support: CDC 2008–2023; PA 1980–2024; reviewer-verified Maryland 2011–2022; Wisconsin 1991–2025; Eisen vector status December 1996 to August 2015, one coarse interval.
- county-period N: CDC 7,681 published keys from 45,513 rows, with privacy-protected floors rather than proven complete totals. PA 3,015 cells (2,358 numeric/657 suppressed); primary 2011–2016 has 392 numeric/10 suppressed. Maryland reviewer verified 288 numeric cells and all 12 sums against state totals; local PDF returned 403/404, so local receipt/digest is UNKNOWN. Wisconsin freshly reproduces 2,520 count county-years; its 2,520 rate rows are not extra outcomes. Eisen reports 654 changed county-intervals. These are source inventories, not approved training examples.
- positive/negative counts if applicable: no Phase 1 class is approved. Displayed signs: PA 1,659 positive/699 explicit zero/657 suppressed; Maryland 279/9, primary window 139/5; Wisconsin 2,264/256. Suppression, missing surveillance and source access failure are never negatives. Eisen narrative splits changes 262 no-record-to-established /184 reported-to-established /208 no-record-to-reported; displayed table gives 264/182/208. Both total 654, but subtype/identity/source reconciliation is required. Unchanged inherited status is not a validated negative.
- geography coverage: CDC 782 pre-2022 and 688 post-2022 counties; WI/PA/NY/MN/VA form 54.9% of pre-2022 keys. PA 67 counties, Maryland 24 jurisdictions, Wisconsin 72 counties: each is one-state evidence. Eisen changes span 30 displayed states; VA/OH/NC/IN/PA account for 39.4%. NSSP has five native regions; delivered NEON evidence is one site/month. Approved DEV has 3,144 counties but only 2023.
- point-in-time status: historical predictor reconstruction and later holdout NOT PROVEN. CDC publication August 2025, PA modification September 2025 and Maryland revision May 1, 2024 do not timestamp original historical values. Eisen publication March 2016/Stacks availability March 1, 2017 differs from collection cutoffs. Wisconsin current compilation is not 35 archived vintages. Outcome maturity and predictor availability must be assessed separately.
- major exclusions: unallocated identities, suppression/category completeness, surveillance-method changes, incomplete collection/revision lineage, unqualified historical denominators, regional allocation and site-to-county inference. Wisconsin partial surveillance during 2012–2021 and PA enhanced surveillance/COVID/2022 methods require era separation.

**Rejected/deferred candidates:**

- A: DEFER Maryland qualification and PA fallback; Wisconsin is a temporal-depth lead with partial-surveillance caveats. BLOCK exact CDC totals/rates from current floors; ML #64 separately evaluates published-lower-bound change.
- B: BLOCK county labels; DEFER native regional comparator using DATA #384/merged PR #591.
- C: DEFER source-backed coarse vector-status transitions after reconciling Eisen table/narrative, county identities, observation timing and later comparability under DATA #429. BLOCK biological emergence/absence, annual forecasts from the coarse pair, and NEON county labels (NOT_COUNTY_REPRESENTATIVE).

**Required next action:**

- DATA #110/#113: reproduce Maryland's official receipt, verify residence/year/case meaning, dated predictors and revisions; compare its unsuppressed 2011–2016 and separate 2017–2019 windows with PA. Resolve PA's 2021 report/workbook discrepancy. Qualify a later holdout before an experiment; no ingestion is authorized.
- ML #23: decide whether reported burden or source-backed status change is a defensible proxy for Phase 1 surveillance attention. If neither answers that decision, consider a descriptive/unsupervised surveillance-review pivot. Reuse DATA #429 and #384 for their separate gates. Keep #86 open until these decisions are resolved; launch no model.

**Product interpretation boundary:** Reported Lyme counts describe surveillance-captured cases, tick-bite ED activity describes care-seeking, and vector-status changes describe documented evidence. None directly proves true incidence, individual risk, biological emergence, absence, underreporting or the benefit of more surveillance. Do not train on an existing heuristic priority as ground truth.

**Links:**

- [Durable EDA artifact](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/blob/codex/ml-86-label-feasibility/docs/eda/86-phase1-label-feasibility.md), [draft PR #87](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/87)
- [Maryland official PDF](https://health.maryland.gov/phpa/OIDEOR/CZVBD/Shared%20Documents/Lyme%20Disease%20Data%202011%20to%202022.pdf), [PA source](https://www.pa.gov/agencies/health/diseases-conditions/infectious-disease/vectorborne-diseases/tick-diseases/dashboard-data), [Wisconsin methods](https://www.dhs.wisconsin.gov/epht/lyme.htm), [Eisen 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4844559/)
- [DATA #110](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/110), [#113](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/113), [#384/PR #591](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/pull/591), [#429](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/429), [NEON #162](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/162)
- [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22), [#23](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/23)
