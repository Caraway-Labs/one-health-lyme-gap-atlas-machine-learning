# Tier 1 county features v2: PROD release admission (ML #104)

**Owner:** Atlas ML. **Version:** `tier1-county-features-v2`.

This is a versioned admission of the governed PROD release
`governed-2026-09-18-unknown-coverage`, bundle SHA-256
`038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`.
It preserves all six ordered predictor names, definitions, transformations,
missing-value meanings, and evidence-sufficiency rules in the
[v1 contract](tier1-county-features-v1.md). The selected model remains
`tier1-statistical-reference-v1`; evaluation remains
`tier1-selection-evaluation-v1`; tier policy remains
`tier1-review-percentile-v1`. DEV v1 remains pinned to its own release.

The fresh read-only comparison found exactly 3,144 identical five-digit FIPS
in DEV and PROD. For each FIPS, human status and published floor, pathogen
status, SVI percentile, and RUCC code are equal. Thus all six predictors and
the selected feature-evidence state are equal. The sorted FIPS joined with LF
and no trailing LF has SHA-256
`4a74ab4f8638b4a02a18b0db4abe9597fc2a6bf364a103314de346338015c690`.

Only the two vector species states differ. PROD has 3,109 counties with
non-Unknown species states; the remaining 35 retain Unknown. Vector species
and aggregate `tick_status` remain **context, not predictors**. V2 records the
governed `TICK_STATUS` value as `vector_evidence_state` rather than writing a
DEV-only Unknown placeholder. Admitted source categories are Established,
Reported, No records, and Unknown. No records is a publisher documentation
category, not biological absence. An unrecognized category fails closed.
Neither vector context nor its changed distribution changes a score, reason,
sufficiency state, or tier in this version.

The CLI requires explicit `--environment prod`, an approved read-only PROD
PAT connection selected through `SNOWFLAKE_CONNECTION_NAME`, and verified
`OH_LYME_PROD_READ` / `ONE_HEALTH_LYME_GAP_ATLAS_PROD` / `COMPUTE_WH` context.
It checks the exact release and bundle before the county read. A wrong role,
warehouse, database, release, bundle, county set, or source state fails before
an output is written. The command writes local files only:

```powershell
$env:SNOWFLAKE_CONNECTION_NAME = 'ATLAS_PROD_READ'
uv run python -m lyme_gap_atlas_ml.tier1_features --environment prod --output .local/ml-104/prod-features.csv --report .local/ml-104/prod-coverage.json
```

The [ML #104 report](../reports/ml-104-prod-feature-admission.md) records the
distribution and selected-model validity checks. A later changed release or
source meaning requires a separate admission; this version is fixed to the
release and bundle above.
