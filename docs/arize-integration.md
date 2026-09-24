# Arize traditional ML telemetry (Story #42)

Snowflake remains Atlas's governed data, execution, experiment, and registry
system of record. Arize receives explicitly approved telemetry for evaluation,
drift and data-quality diagnosis. This adapter creates no model, promotion, or
monitoring policy. Stories #30 and #34 can consume the Atlas-owned
`ObservabilitySink` and its visible `TelemetryOutcome`; Story #43 will define
slice, sufficiency, alert and delayed-label performance policy. Story #44 owns
CLI/MCP and agent tooling.

## SDK choice and identity

The optional `arize` Python SDK v8 is the current traditional-ML path. The
installed lock resolves 8.55.0 (Python >=3.10); Atlas supports Python
3.11–3.13. The installed `ArizeClient(api_key=...)` exposes
`client.ml.log_stream(...)` and `client.ml.log(...)` for DataFrame batches.
The SDK's current `log_stream` returns a Future; Atlas waits for its HTTP
result. The [v8 migration guide](https://arize.com/docs/api-clients/python/version-8/migration/stream-client)
documents the space, model, environment, prediction ID/timestamp, label,
features, tags, batch ID, timeout, and Future. The
[official SDK repository](https://github.com/Arize-ai/client_python) documents
traditional ML streaming and batch paths. The installed 8.55.0 API calls the
DataFrame method `ml.log`, despite an older README example using `log_batch`.
Atlas uses bounded streaming calls (at most 1000 rows per invocation) to avoid
implicit DataFrame column ingestion. A later batch path requires an explicit
schema and privacy review.

`key_from_bundle` revalidates the Story #41 contract before resolving identity.
`model_spec.identity.id/version` become Arize model name/version exactly;
`arize.project_ref` is the Arize **space ID** passed to `space_id`. A project
display name or independent model name is not accepted. The contract validator
also checks Snowflake registry identity. Project, model, or version mismatch
stops before transmission. The Story #41 synthetic bundle is only a test
identity and is not a deployed model.

## Payload and data boundary

`TelemetryRecord` supports explicit training/reference, validation, and
production environments, stable prediction ID, timezone-aware event time,
prediction and optional actual, scalar features and tags, and an optional
categorical probability. Training and validation require a ground-truth value;
validation also requires a batch ID. `Actual` sends a separate production
actual with the same model, version, space, prediction ID, and prediction
timestamp. A zero or false actual is transmitted through an explicit one-row
DataFrame schema; `None` means unavailable. The installed v8.55 stream path
uses a truthiness check on actuals, so a zero/false immediate actual is rejected
and must use `log_actual`. Arize joins delayed actuals by prediction ID and model/
space. Its [documented joiner](https://arize.com/docs/ax/machine-learning/machine-learning/concepts-ml/how-to-send-delayed-actuals)
runs daily with a default 14-day lookback; a later label may require an
account-specific extension. An actual timestamp is retained for Atlas
validation but `log_stream` has no separate actual-time field.

The caller must supply a reviewed `TelemetryPolicy` with exact feature and tag
allowlists and a matching lineage policy reference. Empty allowlists send no
fields. Unknown fields, suspect names (credentials, authorization, contact
information, names, free text), long strings, unsupported values and nonfinite
numbers fail. No input object or DataFrame is automatically serialized.
`uncertainty_interval` and `data_quality_state` are separate typed Atlas
concepts and intentionally are not mapped to Arize until model-specific
semantics and a permitted representation are reviewed. A prediction score is
a model probability, never surveillance completeness. Drift and observed
performance are downstream diagnostics, not payload synonyms. No source row,
private contact data, credentials, or arbitrary free text is approved by this
guide. If classification is uncertain, stop before logging.

## Configuration, outcomes, and verification

Install with `uv sync --extra dev --extra arize`. Set `ARIZE_API_KEY` only in
local/runtime secret configuration. It is not stored in the lineage JSON,
source, logs or errors. Missing credentials or optional SDK cause an explicit
`IntegrationUnavailable`. Payload errors raise `TelemetryError`. An HTTP 2xx
response returns `TelemetryOutcome(sent, "sent")`. Authentication, rejection,
and retry exhaustion raise sanitized `TelemetryFailure`; the caller must
record missing telemetry evidence and retain its canonical prediction.

The SDK submits streaming calls asynchronously and owns its underlying HTTP
transport. Atlas waits for completion, uses a finite 30-second SDK timeout
and 35-second Future wait, and by default performs **no additional retry**.
Optional Atlas retries (maximum three) apply only after explicit HTTP 429 or
500/502/503/504 responses, with stable prediction IDs and bounded backoff.
Ambiguous exceptions are never retried because delivery may have occurred.
The DataFrame actual path raises SDK errors for non-2xx responses; Atlas treats
these as visible failures without another automatic retry.
Arize may perform transport-level retries internally; an HTTP acceptance is
transport proof, not evidence that monitoring or actual joins have completed.
There is no queue, automatic retraining, or model-output mutation here.

Ordinary `uv run pytest` uses fakes and needs no Arize or Snowflake account.
For a strictly optional synthetic DEV proof, configure a locally approved
test space and API key, then run:

```powershell
$env:ATLAS_RUN_ARIZE_DEV_TEST = '1'
$env:ATLAS_ARIZE_TEST_SPACE_ID = '<approved test space ID>'
uv run --extra arize pytest -s tests/test_arize_dev_integration.py
```

The test sends one synthetic production prediction using the synthetic #41
identity and prints only non-secret delivery evidence. It skips unless both
the opt-in flag and local settings exist. Do not point it at a production
space. No real Atlas data is used.
