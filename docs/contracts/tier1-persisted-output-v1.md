# Tier 1 persisted county review output v1

PROD admission under ML #104 uses [feature v2](tier1-county-features-v2.md)
against the pinned PROD release while preserving this output schema, selected
model, evaluation, tier policy, reason meanings, and publication invariants.
The DEV identity and counts below document the original v1 batch; see the
[PROD comparison](../reports/ml-104-prod-feature-admission.md) for admission
evidence. A PR-head PROD artifact is a review candidate until regenerated
from a reviewed final source commit.

**Owner:** Atlas ML for values and semantics; Atlas data for Snowflake objects. **Status:** Product direction approved; exact Data implementation and security review pending. No live batch is approved.

The selected model is `tier1-statistical-reference-v1`, using `tier1-county-features-v1`, evaluation `tier1-selection-evaluation-v1`, and tier policy `tier1-review-percentile-v1`. The pinned DEV release is `governed-2026-09-17-unknown-coverage` with bundle SHA-256 `55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`. No Isolation Forest output may be published as the selected batch.

One row per county contains `county_fips`, those four versions, `prediction_batch_version`, `run_id`, `release_id`, `bundle_sha256`, `source_commit`, `generated_at_utc`, `raw_model_score`, `priority_percentile`, `priority_tier`, `evidence_sufficiency`, `human_evidence_state`, `pathogen_evidence_state`, `feature_evidence_state`, up to three structured `reasons` (`code`, `text`), and `limitation_ref`. The batch manifest records row count and SHA-256 of canonical sorted JSON. Batch identity is a deterministic hash of release, bundle, model, feature, evaluation, policy, and source commit. A later generation timestamp can yield a different digest for the same identity; publication must reject a changed-digest replay instead of mutating an existing batch.

`SUFFICIENT` means selected scoring inputs are present enough for this contract; it does not assert complete surveillance, disease certainty, or clinical confidence. `INSUFFICIENT` means a scientifically scorable county has partial evidence and may retain score, percentile, and any tier. `NOT_ESTIMABLE` has no score, percentile, or tier. The current pinned cohort has no `NOT_ESTIMABLE` row. Raw source states distinguish no county-linked human record, pathogen `No records`, and pathogen `Unknown` from observed zeros or biological absence.

HIGH is percentile >=90; MEDIUM is >=70 and <90; LOW is <70, using tied average within-batch percentiles from ML #27. These bands are relative surveillance-review priority, never disease risk, incidence, probability, clinical severity, or true burden. The API must return the stored tier without recalculation. Raw score is model-native; percentile is batch-relative.

Reason codes are `PUBLISHED_HUMAN_FLOOR`, `NO_COUNTY_HUMAN_RECORD`, `PATHOGEN_PRESENT`, `PATHOGEN_NO_RECORDS`, `PATHOGEN_UNKNOWN`, and optionally `SVI_CONTEXT_DIFFERENCE` when SVI differs by at least 0.25 from the scored-population mean. Text is descriptive, noncausal, and bounded to two or three reasons. The published count floor is privacy protected, unadjusted, and a lower bound. Limitations include source coverage/reporting variation, no clinical or disease-risk interpretation, and no causal attribution.

The approved architectural destination under [ADR 0003](../adr/0003-tier1-output-persistence-boundary.md) is `ONE_HEALTH_LYME_GAP_ATLAS_DEV.FEATURE_STORE.TIER1_COUNTY_REVIEW_OUTPUTS` with a manifest in `FEATURE_STORE.TIER1_REVIEW_BATCHES` and an API-readable `PRESENTATION.CURRENT_TIER1_COUNTY_REVIEW_V`. These objects do **not yet exist**. Publication must stage and validate the complete 3,144-row selected batch, require exact equality with the FIPS set regenerated from the pinned governed feature matrix, prevent duplicate FIPS and changed-digest replay, and change the active approved batch only after all rows and metadata pass. The Data-owned publisher must independently enforce the same exact county-population check before activation; row count and format alone are insufficient. A failed or partial run leaves the last approved batch untouched. For this pinned batch only, expected tiers are 315 HIGH, 628 MEDIUM, 2,201 LOW; sufficiency is 651 SUFFICIENT, 2,493 INSUFFICIENT, zero NOT_ESTIMABLE. Count drift stops publication and needs diagnosis; these are not eternal schema limits.

The unlabeled run uses `atlas-ml-contracts/v2` with `supervision_mode=unsupervised`, immutable source/output digests, and no label, label date, split, or holdout fiction. **This v2 shape is only the selected Tier 1 unsupervised companion**, with fixed model, feature, evaluation, release, and policy identities. It is not a general replacement for declarative ML lineage. Supervised `atlas-ml-contracts/v1` remains unchanged and strict. Reproduce a local, unpublished batch from the committed selected model with:

```powershell
$env:SNOWFLAKE_CONNECTION_NAME = '<approved read-only DEV connection>'
uv run python -m lyme_gap_atlas_ml.tier1_persisted --output-dir .local/ml-32
```

The command verifies Snowflake user, role, database, warehouse, release and bundle before reading `PRESENTATION.CURRENT_RELEASE_V` and `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. It writes ignored local JSON only. Any batch generated from PR #103 before merge is **PRE-MERGE / UNPUBLISHED review evidence and must not be published**. After review and merge, fetch and verify the final `origin/main`, run the command from that exact merged commit, and record its new source commit, batch ID, digest, UTC generation time, exact governed FIPS-set equality, and counts. A squash merge will change the code SHA and therefore the batch ID; do not preserve a pre-merge identity artificially. Only the post-merge, reviewed, independently validated batch may enter the Data-owned publication path. API #10 should read the approved `PRESENTATION.CURRENT_TIER1_COUNTY_REVIEW_V` by FIPS once the data-owned destination is deployed and the batch is approved. API #10 must preserve the stored state, versions, timestamp, reasons, and limitation reference; absent result is not LOW and no heuristic fallback is authorized.
