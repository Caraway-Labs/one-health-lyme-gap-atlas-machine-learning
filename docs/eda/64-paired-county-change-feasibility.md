# ML #64: paired county change feasibility

**Disposition: NOT_ESTIMABLE_WITH_CURRENT_SOURCE.** Current public CDC
county-linked floors do not identify the direction or magnitude of change in
annual reported Confirmed + Probable totals. Stop before statistical tests.
This is a supported scientific negative result, with a separate **ACCESS_BLOCKED**
limitation on governed historical run/revision verification.

Question: can consecutive report years within a compatible reporting era support
within-county total change? The [registered specification](64-analysis-spec.md)
was committed at `4a4349e` before new result statistics. The public coverage
fallback amendment was committed at `d8b9d7c` before new pair counts. Both are
exploratory, not confirmatory. No model, holdout, training or inference was used.

## Source and interpretation

Use [DATA #110](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/110),
[#113](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/113), and
merged [#430](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/430).
Their entire current bodies/comments were inspected along with ML #59/#60/#64.
DATA #110's September 29 numerator/directional audit establishes that the current
county sums are floors, with no approved county-specific finite upper bounds.
They are not complete incidence or exact mature county totals. The absence of
a case-category row is unknown, not a zero. Suppressed/Unknown county identities
cannot be allocated. Residence is not exposure, and annual surveillance report
year is not illness onset, diagnosis, original publication or availability.

The fresh coverage input is CDC `qtbi-xd4i`, restricted to 2011–2019, grouped by
`year,fips,case_status`, with `COUNT(*)` source-observation counts. No frequency
sum, floor difference, effect estimate, p-value or statistical interval was
examined. The source observation unit is county/year/status/sex/age demographic
record; aggregate response rows and distinct county-years are different units.
Numeric five-digit FIPS are syntactically linked keys, not proof of historical
boundary identity. The source has Confirmed and Probable records; requiring
both categories does not establish their complete county totals.

This is **publisher-current aggregate evidence**, cross-checked against DATA
#110's recorded year/window/category key counts, not a new governed DEV snapshot.
Exact private source-version/run/artifact/revision identity remains unavailable.
No pair is admitted on that missing evidence. A source response digest pins the
observed public bytes; it does not establish publisher historical revisions.

## Coverage, missingness and exclusions

The candidate denominator is the union of counties observed anywhere within each
window, times its within-window consecutive-year contrasts. It is not a national
historical county grid. Window county N cannot be added across eras: **719**
distinct numeric-FIPS counties occur across both windows, with overlapping membership.
Pairs also repeat counties and are not independent sample units.

| Window | Source observation rows | Unallocated county-identity rows | Published county-years | Unique county N | Counties in every year | Candidate pair slots | Both-year observed pairs | Missing either year | Valid total-change pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2011–2016 | 17,597 | 1,226 | 2,765 | 626 | 327 | 3,130 | 2,020 | 1,110 | 0 |
| 2017–2019 | 9,954 | 656 | 1,573 | 639 | 424 | 1,278 | 899 | 379 | 0 |
| Pair/row totals | 27,551 | 1,882 | 4,338 | see union above | N/A | 4,408 | 2,919 | 1,489 | 0 |

Source rows include the unallocated rows; county-year counts exclude them.
The 1,882 unallocated rows are observations, not missing counties, pairs or cases.
The 25,669 rows with syntactically numeric FIPS collapse to 4,338 county-years.
The replay now derives unallocated and numeric-FIPS source-observation totals
for each window and overall. Independent review found and corrected a manual
addition error in these row totals; pair coverage and nonidentification were
unaffected. Tests cover observation-row reconciliation separately from county keys.
No unknown or missing year was filled with zero.

| Contrast | Candidates | Neither year | Earlier only | Later only | Both years | Both categories in both years | Observed pairs missing either category |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2011→2012 | 626 | 150 | 46 | 72 | 358 | 314 | 44 |
| 2012→2013 | 626 | 123 | 32 | 73 | 398 | 337 | 61 |
| 2013→2014 | 626 | 106 | 66 | 49 | 405 | 348 | 57 |
| 2014→2015 | 626 | 94 | 35 | 78 | 419 | 367 | 52 |
| 2015→2016 | 626 | 60 | 57 | 69 | 440 | 390 | 50 |
| 2017→2018 | 639 | 43 | 96 | 48 | 452 | 423 | 29 |
| 2018→2019 | 639 | 61 | 53 | 78 | 447 | 424 | 23 |

Mutually exclusive primary attrition: 4,408 slots minus 1,489 missing-year
slots leaves 2,919 observed pairs; all 2,919 fail total-change identification
under the current floor/unknown-upper rule, leaving **0 valid pairs**.
Both-category sensitivity retains 2,603 observed pairs and excludes 316 more
for category absence; all 2,603 still fail identification. These numbers match
DATA #110's separately recorded both-category overlaps. This is coverage
sensitivity, not a different estimand or a test of published-floor change.

Secondary, overlapping limitations for the 2,919 observed pairs: no verified
governed source/revision binding, no certified historical boundary mapping,
and no supplied reviewed jurisdiction applicability sufficient to establish
DATA #430 COMPARABLE. Do not add these overlapping reasons to primary attrition.
The #430 contract was inspected, not executed against a governed run-pinned
pair manifest. These pairs remain unresolved/UNKNOWN for admission; merely
sharing the `cdc_2011` or `cdc_2017` era does not establish comparability.
No 2016→2017 comparison or cross-era pooling was performed.

## Mathematical feasibility and ML decision

For annual totals `T0 ∈ [L0,U0]` and `T1 ∈ [L1,U1]`, the supported change
interval is `[L1−U0,U1−L0]`, absent additional evidenced joint constraints.
When both upper bounds are unknown/unbounded, this interval is `(-∞,+∞)`.
For any published floors one can choose totals satisfying those floors that
increase, decrease or remain equal. A large numerical floor increase therefore
does not identify a total increase. Finite separated bounds could identify a
sign while still failing to identify an exact magnitude for a paired t-test.

**No paired t-test or Wilcoxon signed-rank was run.** Matched inferential N,
effect size, standard error, p-value and statistical confidence interval are
not estimable, rather than zero. The identifiability interval above expresses
source-supported uncertainty, not a statistical confidence interval. Repeated
county/contrast and spatial dependence would require separate justification
if an inferential cohort ever survived. No measurement-process difference is
attributed to epidemiological or biological change.

Human total-count change/direction features and exact-total lag labels are
**not admissible from these floors**. Separately governed source-native floor
context may remain useful; this finding does not authorize an exact-total
reinterpretation, prospective forecast replay, imputation or source removal.
DATA #113's unknown historical availability remains an additional ML blocker.
No population rates were calculated or current-vintage denominators back-projected.

To unblock: through existing DATA #110/#111, obtain authoritative complete
county/report-year C+P totals or justified finite county-specific bounds and
any joint suppression constraints; prove stable historical geography, category
scope and missing/zero meaning; bind source version, revision, maturity and
artifact identity; supply reviewed #430 jurisdiction applicability/comparability.
Directional identification alone does not authorize exact-change inference.
Historical lag-feature admission additionally needs #113/#431 first-publication
and exact-revision availability at the proposed cutoff. No new ingestion,
population acquisition or training follows automatically.

## Reproduction and evidence

- Code: [interval/coverage logic](../../src/lyme_gap_atlas_ml/paired_change.py),
  [bounded entry point](../../scripts/64_paired_change_feasibility.py),
  [tests](../../tests/test_paired_change_64.py), and
  [governed coverage SQL](../../sql/validation/64_pair_coverage.sql).
- Publisher request: `https://data.cdc.gov/resource/qtbi-xd4i.json`, SoQL
  `$select=year,fips,case_status,count(*) as n`,
  `$where=year between '2011' and '2019'`,
  `$group=year,fips,case_status`, `$order=year,fips,case_status`, `$limit=10000`.
  One successful GET, 30-second timeout, 2,000,000-byte cap, no pagination/retries.
  A numeric-year attempt and bounded diagnostic request returned HTTP 400;
  these yielded no result statistics. The corrected filter is text-valued.
- Retrieved **2026-10-04 01:05:13 UTC**; 546,572 bytes; 8,340 aggregate rows;
  response SHA-256 `c0eeb3589da36153ad534e2264454df118505ff5f945144bf6b9fcbcc42e99f4`.
  Ignored response retained for digest-checked offline replay. Fresh publisher
  reads may change; current URL availability is not immutable hosting.
- Reused [ML #86 draft PR #87](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/87)
  at inspected head `a7a8d0e67feb7f7af0fdd900ba84302ce2b8dee0`,
  [source research artifact](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/blob/a7a8d0e67feb7f7af0fdd900ba84302ce2b8dee0/docs/eda/86-phase1-label-feasibility.md).
  It records CDC metadata and historical-availability limitations. Its suggestion
  that #64 separately investigates published-floor changes is not adopted:
  #64's current approved question requires total-change identifiability and STOP.
  Broader archival/state-source research belongs to #86; none was duplicated.
- #430 accepted Data PR #508, reviewed head
  `b26ab372bc64238dd66fea4258e8d86e4b1160da`; contract/module inspected at local
  Data `origin/main` `614dbb7e95766e586e4cac6332d126e53e23933e`.
- Fresh DEV context: MATTHEWCARAWAY / OH_LYME_DEV_READ /
  ONE_HEALTH_LYME_GAP_ATLAS_DEV / PRESENTATION / OH_LYME_DEV_INGEST_XS_WH.
  Schema selected session-only after the default was null. The historical
  conformed aggregate failed with SQL 002003, query ID
  `01c77e76-040b-dea2-0064-2d070110a342`: no CONFORMED schema visibility.
  No stronger role, RAW payload, grant, write, credential change or PROD action.
  A pending request for bounded owner reads is unnecessary for this negative
  publisher-source decision; private run-pinned reconciliation remains blocked.

```powershell
uv sync --locked --extra dev
uv run --no-sync python scripts/64_paired_change_feasibility.py --publisher
# Prefer the retained snapshot; no new external request:
uv run --no-sync python scripts/64_paired_change_feasibility.py --snapshot outputs/ml64/publisher-response.json --sha256 c0eeb3589da36153ad534e2264454df118505ff5f945144bf6b9fcbcc42e99f4 --output-dir outputs/ml64/replay
uv run --no-sync pytest tests/test_paired_change_64.py
uv run --no-sync python scripts/verify.py
```

The governed SQL is an **unexecuted replay path**, requiring separately authorized
visibility, repeated context validation, 30-second statement/queue limits and
seven-row output bound. It does not include statistical tests or access changes.
All source aggregates/receipts, replay outputs and caches remain ignored under
`outputs/`; none is committed. The durable tables are curated coverage evidence,
not raw extracts. No randomness or nondeterministic computation; publisher
revision drift is explicitly separate. Final verification and exact PR head
are recorded in the draft PR. Independent scientific/code review is pending;
the [single issue-comment draft](64-result-comment-draft.md) must not be posted
until that review, and the issue is not closed or merged here.

Validation: mandatory `uv run --no-sync python scripts/verify.py` passed
contracts/skill/lifecycle/hygiene validation, Ruff, format, mypy and **151 tests**;
one optional Arize SDK test skipped. Focused #64 tests: **14 passed**. Exact
snapshot replay independently reproduced the same coverage. Latest-main
reconciliation against `c063b8aa4cf26b55cfc1b32cf0a660f955948195` and whitespace
checks passed. [Draft PR #90](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/90)
contains the implementation and exact-head handoff for review. These are local
verification results, not completed independent scientific review or live
governed-source verification.
