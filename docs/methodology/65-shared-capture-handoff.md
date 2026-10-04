# ML #65 shared PROD input handoff

The [pre-result amendment](65-prod-scope-amendment.md) is registered at
`fb0a6a8`. No PROD association statistics have been inspected or run. The #63
capture owner supplies retained bytes/provenance; #65 makes no new export.

## County payload

JSON: array of county objects. CSV: header plus records. Require all six fields:
`release_id`, `fips`, `in_contiguous_tick_scope`, `scapularis_status`,
`pacificus_status`, `burgdorferi_status`. Names may be uppercase/lowercase;
duplicate case-equivalent names are invalid. Additional context fields are
ignored for #65 and never emitted in its summary. Preserve leading-zero FIPS.
Require exactly 3,144 unique counties from the pinned PROD release. Payload cap:
16 MiB. No per-source observation count is inferred from this projection.

JSON scope is true/false/null. CSV scope is true/false (case-insensitive), or
blank for missing; numeric 0/1 is rejected. CSV status blanks become null.
Unknown/unavailable statuses stay excluded; No records remains its own
source-reported documentation category. Never manufacture missing fields from
an aggregate score or use synthetic data as the scientific input.

## Private provenance sidecar

JSON object, capped at 128 KiB, with these exact lowercase key names:

| Key | Required content |
| --- | --- |
| `county_sha256` | Actual SHA-256 of the retained county file bytes. |
| `observed_at` | Actual timezone-aware capture timestamp. |
| `release` | `release_id`, `bundle_sha256`, `schema_version`, `methodology_version`, `scope`, `status`. Must equal the pinned published PROD identity below. |
| `sources` | Two objects with `source_key`, `source_id`, `dataset_id`, `release_version`, `vintage`, `data_source_version_id`, `ingestion_run_id`, `artifact_id`, `artifact_sha256`. Exact historical manifest anchors are in `SOURCE_ANCHORS` in the issue-local loader; both vintages must be `through 2025-12-31`. |
| `capture` | `object`, `query_id`, `query_sha256`, `row_limit`, `timeout_seconds`, `user`, `role`, `database`, `schema`, `warehouse`. Actual capture evidence, not a new connection. |
| `receipts` | `build_head`, `manifest_path`, `build_url`, `publication_url`, `build_status`, `publication_status`; exact inspected receipt anchors are in loader `RECEIPTS`. Both statuses `SUCCESS`. |

Pinned release: `governed-2026-09-18-unknown-coverage`; bundle SHA-256
`038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`;
schema `1.0.0`; method `semantic-1.0.0`; scope `US_COUNTIES`; status `PUBLISHED`.

Capture object:
`ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V`.
Capture context: user `MATTHEWCARAWAY`; existing authorized role
`OH_LYME_PROD_READ` or `OH_LYME_PROD_RUNTIME`; database
`ONE_HEALTH_LYME_GAP_ATLAS_PROD`, schema `PRESENTATION`, warehouse
`OH_LYME_PROD_INGEST_XS_WH`. Capture SELECT must be reviewed/read-only and bounded
to 3,144-3,145 output rows and at most 30 seconds. The owner/reviewer checks the
actual retained SQL against its digest/query ID; the loader validates the
declaration, not Snowflake query history or raw source bytes. If existing capture
evidence does not satisfy these gates, report the exact mismatch; do not re-export
or silently relax the gate. No new grant/private metadata/raw route is needed.

Use the existing historical manifest and build/publication receipts cited in the
[EDA artifact](../eda/65-vector-pathogen-state-association.md). Do not present
their source-artifact digests as an independent fresh raw-artifact audit. Both
county-file and sidecar byte digests must be supplied independently by the capture
owner before local execution. Unknown sidecar extras such as local paths/selectors
are not emitted by the runner. Sidecars must contain no credentials.

## Local replay command

```powershell
uv run python scripts/eda_65.py --shared-counties data/local/shared/counties.csv --provenance data/local/shared/65-provenance.json --expected-sha256 "<actual-county-file-sha256>" --expected-provenance-sha256 "<actual-sidecar-sha256>" --output outputs/65-prod
uv run python scripts/verify.py
```

This path performs no network/Snowflake call. Missing or invalid provenance emits
`INPUT_BLOCKED`, `scientific_estimability: UNASSESSED`, `counts: null` and exit
code 2; it does not claim NOT_ESTIMABLE or zero eligible N. Accepted input runs
the same registered primary/sensitivity methods and returns both input digests,
the accepted provenance and bounded aggregate findings. All files stay private
and ignored; commit the material conclusion to the existing EDA artifact only
after actual input is supplied. Keep the final comment, merge and #65 closure
held for shared-capture completion and independent scientific review.

## v3 retained public route completed

The six-field route above remains a guarded optional input protocol. The supplied
public bulk capture exposes governed aggregate `tick_status`, not species fields.
The separately committed [v3 amendment](65-public-aggregate-amendment.md) registers
its source/producer equivalence gates and one fixed detail check before outcomes.
The public loader verifies the five retained responses and manifest, immutable
release and canonical county universe, plus that detail response; it performs no
network call or species reconstruction. This route passed and the actual PROD
result is reported in the [EDA artifact](../eda/65-vector-pathogen-state-association.md),
with its exact local replay command and digests. No additional bulk export is
needed. Private source integrity and metadata admission are not thereby established.
The issue comment, merge and closure remain held for independent review.
