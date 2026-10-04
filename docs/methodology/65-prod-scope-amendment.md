# ML #65 scope amendment v2: published PROD consumer capture

Status: PLANNED / awaiting shared capture, registered before PROD association
statistics. Amendment requested by Matthew after review of the DEV finding.
The [v1 specification](65-analysis-plan.md) and its registration commit
`459d53d` remain unchanged. DEV nonestimability is retained as release-specific
evidence; it does not settle the issue's requested governed CDC association.

## Reason, prior inspection and interpretation

The deliberately all-unknown DEV release cannot identify the contrast. Existing
PROD metadata and historical build/publication evidence identify a different
published release with source-backed evidence. The public metadata response and
manifest have been inspected; no PROD county association statistics, table,
effect, category distribution or uncertainty have been inspected by this agent.
Matthew has stated that positive source evidence exists. The extension is
exploratory and explicitly follows the DEV result; it is not confirmatory or
chosen after seeing a PROD p-value. Do not pool environments or substitute PROD
lineage for DEV observations.

Question, estimand, pairing, cohort, unknown handling, category rules, sparse-cell
method, sensitivity, state-cluster uncertainty, interpretation criteria and stop
rules stay exactly as registered in v1. Pairing: **Ixodes scapularis or Ixodes
pacificus + Borrelia burgdorferi sensu stricto**. Require both explicit species
statuses; preserve source-reported No records as documentation only. Retain
unique county N, scope exclusions, family missingness/overlap and source
observation-unit distinctions. No biological absence, annual incidence, causation
or local exposure claim. No model training or feature-admission approval.

## New release/input scope (frozen)

Use the single shared capture owned by ML #63. This runner must not acquire PROD
data or duplicate exports. Accept a private JSON county array or CSV with these
explicit consumer projection fields (case-insensitive column names only):

- `release_id`
- `fips` (five-character county ID, leading zero preserved)
- `in_contiguous_tick_scope` (boolean, or explicitly missing)
- `scapularis_status`
- `pacificus_status`
- `burgdorferi_status`

Additional #63 context columns may exist; ignore them for #65. Do not derive
species categories from an aggregate tick score or synthesize county IDs/scope.
CSV boolean literals true/false (case-insensitive) are allowed; blank is missing,
never false. Status blanks are null, never No records. JSON types stay explicit.
Require exactly 3,144 unique valid counties from the same pinned release.

The private provenance envelope must bind the county-file SHA-256 to the known
published release and source metadata. Verify the envelope's separate byte digest
before parsing data. Required keys:

- `county_sha256`, `observed_at` (timezone-aware capture timestamp)
- `release`: release_id `governed-2026-09-18-unknown-coverage`, bundle_sha256
  `038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`,
  schema_version `1.0.0`, methodology_version `semantic-1.0.0`, scope
  `US_COUNTIES`, status `PUBLISHED`
- `sources`: distinct tick/pathogen identities from the reviewed manifest,
  including exact source/dataset/version/run/artifact/SHA tuples and vintage
  `through 2025-12-31`
- `capture`: the approved PROD `PRESENTATION.CURRENT_COUNTY_ATLAS_V` object,
  bounded SELECT query ID and SHA-256, row_limit <= 3,145, timeout_seconds <= 30
- `receipts`: exact build head/manifest path and successful build/publication
  URLs already documented in the EDA artifact

Provenance can come from existing approved receipts; no new grant, private
metadata table, raw source read or alternative identity is authorized. This
envelope is an audit declaration bound to retained bytes, not a claim that a
digest alone proves source truth. The capture owner/reviewer must verify it
against the existing consumer query/receipt evidence. Missing or mismatched
provenance means INPUT_BLOCKED / estimability unassessed, not N = 0 and not
scientific NOT_ESTIMABLE. The current public metadata proves accessibility of
metadata, not the required county-pair input or scientific contrast.

## Execution and disposition

After registration, implement a local-only shared-capture loader and test its
successful path with explicitly synthetic data, plus digest/release/source/
period/missingness rejection. Reuse the v1 pure analysis implementation and the
repository verification harness. Verify input gates before computing counts or
statistics. Read retained files once; no network or warehouse access in the
shared-input path. Record both file digests and accepted provenance in the
summary. Raw rows and temporary outputs stay ignored/private.

Run the same primary analysis and one prespecified category-collapse sensitivity
only after #63 supplies the capture and provenance and these gates pass. All
prespecified results must be reported, including invalid/undefined uncertainty
or exact work-cap failure. Review-ready code without input is PLANNED /
INPUT_PENDING, not a completed scientific issue. Hold the final issue comment,
merge and closure until the shared capture and independent scientific review.

References: [EDA evidence and inspected PROD manifest/receipt links](../eda/65-vector-pathogen-state-association.md).
No source contracts, other worktrees, production or Web code are changed.
