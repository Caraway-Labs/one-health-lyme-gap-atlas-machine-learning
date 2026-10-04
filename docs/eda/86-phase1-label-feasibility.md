# ML #86: Phase 1 county-time label feasibility

Research date: 2026-10-04 UTC. Decision proposed for independent owner review:
**BLOCK** a Phase 1 supervised experiment now. **No primary or fallback label
is admitted.** Best next qualification candidate: Pennsylvania's official
county report-year Lyme counts (A). Conditional fallback research: CDC
publication-evidence transitions (C), not biological emergence. This is a
bounded negative decision, not proof that defensible labels cannot exist.

The user decision is where epidemiologists should give surveillance more
attention. None of these outcomes directly measures the benefit of that
attention. A burden forecast or new published detection can be a separately
reviewed proxy; choosing that proxy belongs to [ML #23](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/23).
No production target, threshold, experiment, or model is adopted here.

## Comparison and admission decision

| Candidate | Proposed research definition and grain | Observed support | Scientifically usable Phase 1 label count | Disposition |
| --- | --- | --- | --- | --- |
| A: current CDC human Lyme | County of residence/report-year Y, reported Confirmed+Probable count; possible next-year count or rate regression | 45,513 demographic/status rows; 7,681 distinct published county-years, 2008–2023 | No exact mature totals admitted under current governed floor contract; strict historical eligibility unproved | **DEFER**; BLOCK exact totals/rates from current floors |
| A alternative: PA DOH | County/report-year count, with publisher suppression; annual forward horizon only if reviewed | 67 county rows × 45 years = 3,015 cells, 1980–2024; 2,358 numeric, 657 suppressed | UNKNOWN after case-inclusion, revision, geography and historical-availability qualification; none admitted | **DEFER**, best bounded next lead |
| B: CDC tracker/NSSP | Native region/week or month ED tick-bite visits per 100,000 ED visits | Five regions; controls 2017–2026, completeness unknown | County labels unsupported; native regional sample count UNKNOWN | **BLOCK** county target; **DEFER** regional comparator |
| C: CDC tick/pathogen | New publisher-supported county/species/pathogen evidence between dated releases; proposed next-release horizon | Current cumulative-through-2025 county status; repeated eligible historical snapshots not proven | Transition/class counts UNKNOWN, none admitted | **DEFER** publication-event formulation; BLOCK annual incidence/absence inference |
| C: NEON | Future qualifying individual test/event result at native site/plot, with completed effort/QA | Existing governed run has 171 canonical observations, one site/month/release | County labels unsupported; positive/negative native test counts UNKNOWN to this read role | **BLOCK** county target; site question would be a separate pivot |

"None admitted" is an evidence decision, not a surveillance zero. UNKNOWN
counts are not zero. Source cells, observations, artifacts and independent
county-period examples are different units. Synthetic tests below are never
included in these counts.

## A: authoritative human outcomes

### Current CDC contract and fresh counts

The two public Socrata products expose `year,state,fips,case_status,sex,
age_cat_yrs,frequency`. The query groups only publisher rows; numeric
five-digit FIPS identify published county keys, not a complete geography panel.
Residence is not exposure location; annual report year is not onset season.
The metadata describes annual updates after health-department final verification,
privacy transformations, varying ascertainment and alternative state methods.
No all-age/all-sex exact county-total field is present.

The [DATA #110](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/110)
and [#113](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/113)
full issues/comments were read. Their prior governed and publisher audits
classify county sums as published floors, not exact mature Confirmed+Probable
totals. Suppressed/unknown county identities cannot be allocated. A missing
case category is not proven zero. This investigation reproduces their key
counts, not their private run-pinned lineage or all category-completeness checks.

| Source/window | Source rows | Unallocated FIPS rows | Published county-years | Distinct counties | FIPS state prefixes |
| --- | ---: | ---: | ---: | ---: | ---: |
| qtbi-xd4i, 2008–2021 | 40,468 | 2,855 | 6,445 | 782 | 41 |
| x5j9-wybp, 2022–2023 | 5,045 | 363 | 1,236 | 688 | 35 |

The 840-county union is **prior #110 evidence**, not independently recounted
by this script. The post-2022 query has 36 source state labels including
`Unknown`; these must not be described as 36 verified states. FIPS prefixes
and publisher state labels are separately counted.

| Report year | Published county-years |
| --- | ---: |
| 2008 / 2009 / 2010 | 367 / 400 / 393 |
| 2011 / 2012 / 2013 | 404 / 430 / 471 |
| 2014 / 2015 / 2016 | 454 / 497 / 509 |
| 2017 / 2018 / 2019 | 548 / 500 / 525 |
| 2020 / 2021 | 422 / 525 |
| 2022 / 2023 | 585 / 651 |

Geographic concentration: WI/PA/NY/MN/VA account for 3,536 of 6,445 pre-2022
keys (54.9%); the corresponding post-2022 source labels account for 621 of
1,236 (50.2%). These are published-key concentration, not case burden shares.
The 2011–2016 window has 2,765 keys and 2017–2019 has 1,573. Prior #110
reports 626/639 counties respectively, 327 present in all six primary years,
424 in all three replication years, and only 189 across all 14 pre-2022 years.
Those overlap counts are inspected earlier evidence, not new live counts.

For exact-count regression, class balance is N/A. For an annual directional
classification, the prior interval audit admitted no unambiguous increase or
non-increase pairs because county floors have no established finite upper
bounds. That result applies to that exact/floor interval rule. It does **not**
reject ML #64's separately authorized investigation of changes in published
lower bounds. A lower-bound change is a distinct construct and must retain
that meaning; its issue-specific analysis is not duplicated here.

### Historical availability and denominators

Socrata `publicationDate` is 2025-08-19 18:29:16 UTC (qtbi) and 18:35:27 UTC
(x5j9). Observation years start in 2008/2022. Neither catalog publication nor
current retrieval proves the exact historic cells were available at a prior
January 1 forecast cutoff. Original cell publication, historical revisions and
per-cell maturity remain UNKNOWN. Current products support **retrospective
floor EDA**, not a proven strict historical forecast replay.

Outcome finalization can occur after the predicted year: that is permissible
for evaluation if the target version/maturity contract is fixed. Prior outcomes
used as predictors must have exact availability before each forecast cutoff.
These are separate requirements; a late outcome publication alone does not
invalidate all retrospective prediction, but it does not establish historical
predictor eligibility either.

The approved DEV presentation path was independently counted after context
verification. It returns **9,432 observations / 3,144 counties / 2023 only**:
three governed measures per county, including missingness, not 9,432 labels.
The current [projection contract](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-release/current-county-observations-v1.md)
has only human status and 2023 count/rate floors; tick/pathogen cumulative
status and private historical lineage are excluded. No internal/raw/conformed
query or stronger role was used. Historical run/snapshot counts unavailable
through this path remain UNKNOWN.

Rates need governed same-year county population and geography. [DATA #111](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/111)
names Census PEP July 1 county estimates and exact archived vintages as the
candidate denominator; current SVI 2022/ACS 2018–2022 is not that series.
Later intercensal revisions may evaluate retrospective rates but cannot be
forecast inputs before their release. No population acquisition is justified
until numerator/target feasibility passes. Count regression avoids a target
denominator but does not eliminate population change or ascertainment bias.
2011/2017/2022 definition changes and jurisdiction applicability must pass
DATA #430 separately from DATA #431 timing. Dropping 2022 alone is no repair.

### Official alternatives: a concrete PA qualification lead

The [PA DOH dashboard/data page](https://www.pa.gov/agencies/health/diseases-conditions/infectious-disease/vectorborne-diseases/tick-diseases/dashboard-data)
links the [1980–2024 workbook](https://www.pa.gov/content/dam/copapwp-pagov/en/health/documents/topics/documents/diseases-and-conditions/vectorborne/OfficialLymeByReport2024withMap.xlsx).
Its county count worksheet has 67 unique county names, 45 year columns, no
missing cells, explicit numeric zeros and `*` suppression. Numeric cells are
exact **displayed source counts**, not certified mature/complete target labels.
No FIPS mapping is manufactured. Workbook notes identify PA-NEDSS/Vital
Statistics, investigation-resource differences, enhanced surveillance in
Butler/Delaware/York in 2012 and Allegheny in 2014, pandemic effects in 2020–21,
and the 2022 lab-based case-definition change.

| Window | County-year cells | Numeric positive | Explicit numeric zero | Suppressed | Numeric cells |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1980–2024 | 3,015 | 1,659 | 699 | 657 | 2,358 |
| 2011–2016 | 402 | 389 | 3 | 10 | 392 |
| 2017–2019 | 201 | 200 | 0 | 1 | 200 |
| 2020–2021 | 134 | 95 | 12 | 27 | 107 |
| 2022–2024 | 201 | 200 | 0 | 1 | 200 |

These positive/zero counts describe the **source count sign**, not a chosen
surveillance-priority class. `*` is never negative. The note says counts below
five are not displayed; a conservative candidate interval is [0,4], pending
publisher clarification, rather than assuming which nonzero values were
redacted. No classification threshold is adopted. Numeric annual cohorts have
depth for a prospective holdout *in principle*, but release lineage and
methodology comparability must still be qualified. The cohort is one state;
national generalization cannot be claimed. 2014–2018 have 67 numeric positive
cells per year, making a presence classifier trivial and unsuitable.

The workbook's core `modified` value is 2025-09-12T18:36:28Z, its `created`
value is 2015-06-02T22:28:57Z, and its title is stale (1980–2021). None is a
verified public release timestamp. It is a current historical compilation,
not 45 archived vintages. [2021 report](https://www.pa.gov/content/dam/copapwp-pagov/en/health/documents/topics/documents/diseases-and-conditions/vectorborne/Pennsylvania%20Lyme%20Disease%20Annual%20report%202021.pdf)
is cover-dated June 2023, includes Confirmed+Probable cases and redacts <5;
it reports nine zero counties whereas this workbook displays ten for 2021.
That discrepancy requires revision/definition reconciliation, not a preferred
value chosen by Atlas. [2023 report](https://www.pa.gov/content/dam/copapwp-pagov/en/health/documents/topics/documents/diseases-and-conditions/vectorborne/Lyme%20Disease%20Annual%20Report%202023.pdf)
is cover-dated May 2025 and says its Lyme totals are probable cases under the
high-incidence lab-based definition. A Confirmed+Probable label must explicitly
reconcile this with earlier methods. Cover dates are dated publication evidence
at month precision, not proof of original posting or immutable revisions.

Other official paths were explored, without claiming an exhaustive national
inventory:

- CDC's [current download page](https://www.cdc.gov/lyme/data-research/facts-stats/surveillance-data-1.html)
  lists state/locality and region case tables and national onset tables; county
  residence/onset pairs are not established by combining these. [WONDER](https://wonder.cdc.gov/nndss-annual-summary.html)
  annual tables offer state/region strata, not county labels. Dated [2008–2015 MMWR](https://www.cdc.gov/mmwr/volumes/66/ss/ss6622a1.htm)
  and [case maps](https://www.cdc.gov/lyme/data-research/facts-stats/lyme-disease-case-map.html)
  are evidence of surveillance publications, not complete county total files.
- Three historically cited official CDC county file URLs returned HTTP 404
  under bounded direct requests (reproduction below). Research repositories
  and university archives identify former files, but their copies are not
  silently admitted as publisher-authenticated vintages. Recovery through
  CDC Stacks/publisher archives remains a bounded #111 question.
- [New York annual reports](https://www.health.ny.gov/statistics/diseases/communicable/index.htm)
  and the 2019/2022 county PDFs were found, but direct opens returned 403.
  Indexed official 2022 notes describe 2013–2021 sampling/extrapolation in
  participating counties. Usable county counts and vintages remain UNKNOWN;
  estimated totals must not be relabeled as exact individual case totals.
- [Minnesota statistics](https://www.health.mn.gov/diseases/lyme/statistics.html)
  and official annual reports were located; full direct content was inaccessible.
  Indexed official material flags the 2022 method change. Its accessible
  regional summary leads do not prove a county-year panel. Counts UNKNOWN.

Thus authoritative county outputs do exist (PA), contradicting a blanket
"no county source" claim. They still do not prove a Phase 1 target or a strict
as-of panel. Conditional primary recommendation is qualification of annual PA
reported counts, not national incidence and not an automatic Phase 1 proxy.
If eventually selected, regression/ranking and a prior-count baseline are
plausible; errors and selection bias from suppression require explicit review.

## B: tracker/NSSP — reuse DATA #384, no duplicate acquisition

[Merged PR #591](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/pull/591)
(merge `9d3dece40a419ebf1b8a14d10672815a4da1b682`, 2026-10-03) records
DEFER and public screenshots. Native regions are Midwest, Northeast, South
Central, Southeast and West. Rate denominator is ED visits, not residents.
The signal reflects text-detected tick-related ED care, not diagnosed Lyme.
Weekly/monthly panels and 2017–2026 controls do not prove complete historic
observations. The inspected refresh is September 27, 2026; latest-month data
are preliminary; December 2025 quality filters create a method-era concern.

Use the qualification record and retained screenshots in
[PR #591's files](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/pull/591/files)
at the immutable merge ref above.
No dashboard scrape/export is repeated here. PR evidence leaves exact regional
membership/attribution, facility and denominator eligibility, blank/zero/
suppression, revision history and original availability UNKNOWN. The CDC
[surveillance page](https://www.cdc.gov/lyme/data-research/facts-stats/index.html)
independently confirms the regional NSSP signal.

Region/week forecasting could be a separate useful question once #384 passes;
it would not answer county prioritization. Regional rates cannot be copied,
allocated, averaged or mapped into county labels. Applicable sample/class
counts and geographic/temporal concentration are UNKNOWN without a qualified
export. A seasonal regional baseline is merely a future proposal. No stability
or future-event-label claim is established. Current permitted role: deferred
native-region context/comparator; no current feature/label admission.

## C: vector/pathogen transitions

The [CDC blacklegged tick page](https://www.cdc.gov/ticks/data-research/facts-stats/blacklegged-tick-surveillance.html)
dated May 14, 2026 describes cumulative established status through 2025.
The [pathogen page](https://www.cdc.gov/ticks/data-research/facts-stats/tickborne-pathogen-surveillance-1.html)
dated April 29, 2026 describes detections through 2025. The reviewed workbook
profile is `Public_Use_Ixodes_County_Table_2026_03252026.xlsx`, sheet
`Ixodes records 2025`, seven status/source fields. These dates are page/file
metadata and as-of scope, not dates of first detection or historical release.
The workbook has no collection/test effort or annual incidence denominator.
Restricted raw bytes were not downloaded or exposed.

CDC's establishment criteria use qualifying life-stage collections within a
12-month period, but the published established status persists thereafter.
Consequently an unchanged established county is not a new annual detection,
and a missing/`No records` county is not a biological negative. A delta between
snapshots can reflect new surveillance, old observation backfill, changed
identification or revision. No repeated publisher-vintage series with
availability and row revision lineage was proven by this authorized path.
Actual transition positives, negatives, counties/states and concentration are
UNKNOWN. Current snapshot county totals are not independent annual examples.

Conditional fallback definition: for county × species/pathogen, a **newly
published qualifying evidence record by the next dated release**, among a
defined at-risk evidence cohort. The event is publication, not newly acquired
biological presence. A no-new-publication comparator requires proven complete
capture of both releases; it means no new publisher record, never tick/pathogen
absence. A biological sampled-not-detected class requires documented qualifying
effort and test results. [DATA #429](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/429)
remains open and owns these explicit state semantics; no state is invented here.
For retrospective emergence or annual abundance, this candidate is BLOCKED.
For publication-event prediction it is DEFERRED until vintages, revision causes
and actual sparse transition counts support temporal validation. A persistence/
no-new-record baseline would be necessary but is not evaluated here.

NEON [RELEASE-2026](https://www.neonscience.org/release-2026) was released
January 23, 2026. Collection `DP1.10093.001` DOI `10.48443/5e20-3763` and
pathogen `DP1.10092.001` DOI `10.48443/n2yp-5a62` have native plot/event
`collectDate` and individual-test `testedDate`, respectively. Historical
observations inside the 2026 release were not available in that version in
2016. Prior releases exist generally, but paired eligible tick vintages were
not proven here; the publisher explicitly documents removal of untested blank/
NA pathogen rows between 2025 and 2026, illustrating revision rather than
new detection.

Current [source scope](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/config/sources/neon_tick_release_2026.yml)
and [DATA #162 receipt](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/162#issuecomment-5789110264)
prove only BLAN/2016-05, run `ea8db548-62b0-4632-84ca-02eee97ead41`,
31 immutable artifacts and 171 persisted canonical observations. These are
**inspected integration receipts**, not a new live warehouse count. One
site/month cannot establish county-time transitions or a future-period holdout.
The [canonical contract](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/tick-surveillance/canonical-tick-surveillance-v1.md)
preserves UNMAPPED and NOT_COUNTY_REPRESENTATIVE. Positive/negative eligible
tests by pathogen/QA/stratum remain UNKNOWN to this investigation; 171 cannot
be treated as 171 county labels or individual tests. NEON event labels could
justify a separate site-focused target after qualification, never a county
absence class. No token/download or broader acquisition was attempted.

## Reproduction, receipts and environment bounds

Code: [publisher profiler](../../src/lyme_gap_atlas_ml/label_feasibility.py),
[entry point](../../scripts/research_86.py),
[DEV aggregate SQL](../../sql/validation/86_current_county_inventory.sql),
[boundary tests](../../tests/test_label_feasibility.py).

```powershell
uv sync --locked --extra dev
uv run --no-sync python scripts/research_86.py
uv run --no-sync python scripts/research_86.py --pa
uv run --no-sync python scripts/verify.py
# After independent DEV context validation, using an existing local selector:
snow sql -c $env:SNOWFLAKE_CONNECTION_NAME --schema PRESENTATION -f sql/validation/86_current_county_inventory.sql
```

The CDC entry point makes four fixed requests: metadata for each resource plus
SoQL `year,state,fips,count(*) as n,sum(frequency) as published_floor`, grouped
and ordered by `year,state,fips`, `$limit=10000`. Each response is capped at
2,000,000 bytes, timeout 30 seconds; a limit-sized result fails closed.
PA mode makes one fixed 2 MB request and enforces a 10 MB uncompressed ZIP
cap, the exact count worksheet, 67 distinct names and 1980–2024 range. Neither
persists raw extracts nor certifies scientific eligibility. Changed schema,
duplicate aggregate keys and truncation block instead of producing false counts.
Changing publisher responses can change digests; these are retrieval receipts,
not immutable source hosting or future replay guarantees.

| Response, retrieved 2026-10-04 UTC | Bytes | SHA-256 |
| --- | ---: | --- |
| qtbi aggregate, 00:40:57 | 540,568 | `45f583aca6b871d76a7f3e91c85287fb17783a6ba339a3ae6c45f381067b03bc` |
| [qtbi metadata](https://data.cdc.gov/api/views/qtbi-xd4i), 00:40:56 | 16,446 | `1fed47cf7d375647b5dfdd709cd685c5a370b10734a7ae711230976b039752d3` |
| x5j9 aggregate, 00:40:58 | 101,836 | `1e13410aba4911d22db3c8b731959aa01e6b8b0a7ba8789b24a8e2726aca3b38` |
| [x5j9 metadata](https://data.cdc.gov/api/views/x5j9-wybp), 00:40:57 | 15,862 | `17387aa9d0f86d9861e074bcb1cf9f41175b34768538f688d0fc271f25fad0e6` |
| PA workbook, 00:46:55 | 435,622 | `9d3d5a8194db7099d9ff5f894c5b0580be292a3298c4627e847ed5847013b262` |
| PA 2023 PDF, bounded direct read | 1,759,704 | `6fdfcd96ccd6494e5c14865ff87843fe08143b4e1c2fad4efeebae53d6c3870f` |

Legacy CDC probes (single GET, 25-second timeout, 2 MB cap) returned 404:
`https://www.cdc.gov/lyme/resources/datasurveillance/LD-Case-Counts-by-County-01-20.csv`,
`https://www.cdc.gov/lyme/resources/LD-Case-Counts-by-County-00-18.csv`, and
`https://www.cdc.gov/lyme/resources/datasurveillance/Ld-Case-Counts-by-County-01-21.xlsx`.
PA 2021 PDF exceeded the local 2 MB probe cap; its methods/cover/text were
inspected through the public PDF research renderer, not a retained raw extract.
NY/MN inaccessible requests are access limits, never zero label counts.

Existing DATA #384 screenshots are reused at PR #591's immutable merge ref.
Latest-main GitHub file inspection returned blob SHAs `ddffc61a6108c58faf489fd67d48197ab3403472`
(canonical tick contract), `094a46a0e2bac58cd4c84ab94f6d33f2c1786fe2`
(NEON profile), and `effe7315a908da1e44408a4e821e4b413ad0f40f`
(current-county projection). These are Git blob IDs, not SHA-256 file receipts.
No inferred raw workbook/sample counts come from fixtures.

DEV identity passed: MATTHEWCARAWAY / OH_LYME_DEV_READ /
ONE_HEALTH_LYME_GAP_ATLAS_DEV / PRESENTATION / OH_LYME_DEV_INGEST_XS_WH.
The initial default schema was null; PRESENTATION was selected session-only
and context was repeated before the aggregate. Exactly one data object was
read, the approved current-county view. No writes, grants, credentials,
persistent connection configuration, PROD, training, paid calls or Web changes.

## Next actions and review gate

1. Independent review of this exact PR head, counts, semantics and proposed
   result comment; retain #86 open until the reviewed artifact is merged and
   its single decision-ready comment is authorized/published.
2. Through existing DATA #110/#111, qualify PA **without ingestion**: verify
   report-year/residence definition and category inclusion by era; suppression
   intervals; reconcile 2021 report/workbook discrepancy; obtain dated prior
   vintages and exact revision/maturity evidence; verify county/FIPS identity.
   Start with 2011–2016 and separately 2017–2019; assess pandemic/post-2022
   separately. DATA #113 then evaluates availability. Stop if these cannot be
   proven with bounded evidence. No blanket national source build is required.
3. ML #23 records whether reported counts can answer Phase 1 or belong solely
   to Phase 2. If no proxy is scientifically supported, choose an explicitly
   unsupervised/descriptive surveillance review formulation rather than
   learning the existing heuristic. No such pivot is implemented here.
4. Reuse #384 for regional qualification. Reuse #429 for CDC state semantics;
   first prove two dated complete releases and revision lineage before any
   transition count/training proposal. A NEON site pivot needs separate scope.

Suggested experiment sufficiency considerations (not approved thresholds):
multiple comparable outcome years plus an untouched later-year holdout;
adequate counties and outcome variation; source-native geography; known
cutoff availability for inputs; and source-supported exclusions/abstention.
No numerical production sufficiency threshold is invented.

Validation: isolated ML branch from `c063b8aa4cf26b55cfc1b32cf0a660f955948195`;
`uv run --no-sync python scripts/verify.py` passes contract validation, Ruff
lint/format and mypy; pytest **140 passed, 1 skipped** (optional Arize SDK
not installed). Latest-main reconciliation and `git diff --check` pass.
Final head is recorded in [draft PR #87](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/87).
The [single result-comment draft](86-result-comment-draft.md) is review-only;
no issue comment has been published and no issue is closed.
Other worktrees, including concurrent #61–65 sessions, were not modified.
