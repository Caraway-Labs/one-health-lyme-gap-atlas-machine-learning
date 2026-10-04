# ML #65 analysis specification v1

Status: PLANNED. Registered before live query or association statistics.
Issue: https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/65
Contract: [analysis-spec-v1](analysis-spec-v1.md); parent #59.

## Question, source scope and estimand

Within one published governed CDC county release, does the documentation state
of host-seeking Ixodes vector evidence co-occur with the documentation state of
Borrelia burgdorferi sensu stricto evidence? This informs whether the two evidence
families warrant separate feature blocks; it does not establish redundancy in a
predictive model, causal effects, pathogen absence or individual exposure risk.

Pairing: **Ixodes scapularis or Ixodes pacificus** with **Borrelia burgdorferi
sensu stricto**. The pathogen source review explicitly defines Present as
identification in host-seeking ticks of either species. The approved normalization
registry v1.0.4 defines this aggregate taxon; do not attribute pathogen records to
one species. The vector category below is a transparent analysis of the two
separate source statuses, not a new biological equivalence or canonical mapping.

Estimand: unweighted county-level Cramer's V for the 3-by-2 table of eligible
documentation states in the fixed release. Source observation units are separate
county/species status records and county/pathogen status records; the analysis
unit is one unique county, not three independent observations. No population
weighting, percentile transformation, annual outcome or predictive target.

## Cohort and category handling (frozen)

Read only DEV `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`, and
`CURRENT_SOURCE_METADATA_V` through the existing authorized read route. Pin the
returned release ID and bundle digest. Do not read semantic internals, restricted
workbooks, RAW/STAGING/CONFORMED or Alpha fixtures. Prefer an already retained,
identity-verified immutable governed snapshot if available through this route.
Availability cutoff: execution on 2026-10-04 UTC. Both source windows must be
cumulative through 2025-12-31; release time is not observation time.

Require unique five-digit FIPS, one release, and explicit
`in_contiguous_tick_scope = true`. Exclude out-of-scope and missing-scope counties
separately. Duplicate/invalid IDs, an unpinned release, incompatible window or
unrecognized categories stop execution; never deduplicate by arbitrary choice.

Accept exact vector source labels Established, Reported, No records. Require
both species statuses to be explicit before constructing the aggregate:

1. Either Established -> Established.
2. Otherwise either Reported -> Reported.
3. Otherwise both No records -> No records.

Unknown, null, unavailable and NO_QUALIFYING_RECORD are excluded, retained and
counted by family/state. Even a known positive species does not resolve an
unknown other-species category under this conservative plan. Pathogen categories
are exact Present and No records. Source-reported No records is eligible **only
as a documentation category**, never as a negative test/biological absence.
Keep it distinct from unknown coverage or a missing source county.

Report projection rows, unique county N, scope exclusions, each missing family,
overlap, eligible N and the full documentation-state table. Do not infer raw
source row counts from release rows. Inaccessible counts are unavailable, not
zero and not fixture/source-profile counts substituted for measured counts.

## Method, sensitivity and uncertainty (frozen)

Exploratory, one primary pairing and one prespecified sensitivity; no hypothesis
search or multiplicity family. Report Cramer's V, expected cells and Pearson
residuals when at least two occupied categories remain on each axis. Empty
margins are dropped for calculation and disclosed. No variation / zero eligible
count makes the association NOT_ESTIMABLE rather than V = 0.

The chi-square reference test is permitted only when all expected cells >= 5.
For a sparse 2-by-2 table use two-sided Fisher conditional exact probabilities;
for a sparse 3-by-2 table use a bounded fixed-margin exact enumeration, with a
declared work cap and no asymptotic fallback. Sparse methods avoid unsupported
large-sample approximation, but do not cure surveillance selection/dependence.

One sensitivity: collapse Established + Reported to Documented vector record,
retaining source-reported No records; retain Present / No records for pathogen.
Unknowns remain excluded under identical cohort rules. Do not choose a collapse
after seeing the result. No positive-only sensitivity, which makes the pathogen
margin constant and cannot estimate the association.

Counties share spatial ecology and surveillance/reporting systems. Treat the
table and V as descriptive finite-release quantities. Any chi-square/Fisher
probability is an IID reference, not population-level evidence. If estimable,
use state-cluster resampling (state prefix of FIPS), 2,000 replicates, seed 6501,
to report a percentile 95% robustness interval for V; report nonestimable
replicates and suppress the interval if >5% fail or fewer than 10 state clusters
are represented. This handles within-state dependence only; across-state
dependence and nonrandom surveillance remain limitations. No causal inference.

Heuristic reporting disposition, fixed in advance: V >= 0.5 STRONG_ASSOCIATION,
0.3 <= V < 0.5 MODERATE_ASSOCIATION, otherwise WEAK_OR_NO_ASSOCIATION. These are
descriptive communication bins, not universal scientific cutoffs or proof of
independence; uncertainty/caveats accompany them. An undefined table is
NOT_ESTIMABLE. Inaccessibility is separately ACCESS_BLOCKED / scientific
estimability unassessed, even if the issue workflow uses NOT_ESTIMABLE.

## Execution bounds and stop conditions

Validate the five Snowflake context fields under the least-privilege DEV read
role before reading data. Select no stronger role or production environment.
At most five read-only SELECT statements, each 30-second statement limit and
bounded output: context 1 row, release 2 rows, source metadata 3 rows, county
projection 3,145 rows. Fetch once, retain privately in ignored outputs, and replay
locally; no repeated exports or warehouse scan concurrency. Missing grants,
authentication, source identity/digest or lineage are access/identity blockers.
The DEV all-unknown coverage exception in ADR 0032 is known from contract review,
not a measured current cohort result; verify current data before asserting N.

Reproduction will use issue-local code/script and reviewed SQL under existing
repository boundaries, plus `uv run python scripts/verify.py`. Findings belong
in `docs/eda/65-vector-pathogen-state-association.md`. No raw extracts are
committed. No training, telemetry, write, grant, ingestion or public release.
Independent scientific/code review remains pending; hold the issue comment.

## Source references inspected before registration

Data repository origin/main: 614dbb7e95766e586e4cac6332d126e53e23933e.
- `docs/contracts/tick-surveillance/canonical-tick-surveillance-v1.md`
- `docs/contracts/tick-surveillance/tick-surveillance-normalization-v1.json`
- `docs/operations/cdc-ixodes-pathogen-source-review.md`
- `docs/contracts/semantic-release/README.md`
- `docs/contracts/semantic-release/current-county-observations-v1.md`
- ADR 0031 and 0032; migrations V072 and V081.

The annual current-county observation view excludes cumulative tick/pathogen
statuses and cannot answer this question. The county-atlas view is the existing
governed projection with both evidence families. Its availability to DEV READ
must be established, not assumed. No shared source contract is modified.
