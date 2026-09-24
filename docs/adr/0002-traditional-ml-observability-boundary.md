# 0002: Traditional ML observability boundary

Status: Proposed
Date: 2026-09-24
Decision owner: Atlas ML product and engineering leads

## Context

Epic #36 and Story #42 call for Arize traditional ML observability. Existing
ADR 0001 establishes canonical lineage identity but does not approve the
external telemetry or field-classification boundary. Sending model row data
to a third party is a security and privacy decision under the workspace
technology baseline. Stories #23, #30, #34 and #43 have not approved a real
Atlas target, source row set, feature list, label maturity or monitoring rule.

## Decision

Propose a single `observability` package in the ML repository. Core model
code depends on Atlas-owned telemetry values and an `ObservabilitySink`;
Arize SDK types and credentials remain inside the adapter. Snowflake remains
the governed data, execution, experiment and registry system of record.
Story #41's validated model ID/version and Arize mapping supply exact Arize
model/version and space identity. Every feature and tag requires an explicit
reviewed allowlist with a matching policy reference. No real source data is
approved by this ADR. Training/reference and validation need eligible actuals;
production actuals can arrive separately by stable prediction ID. Transport
failure remains visible to the caller and never changes the canonical result.

## Consequences

The adapter can send only typed, bounded scalar telemetry. It rejects unknown
fields and suspect contact, credential and free-text names. The SDK dependency
is optional; ordinary unit tests and documentation need no credentials or
network. A future model-specific approval must resolve data classification,
permitted features/tags, target semantics, and Arize space before any real
telemetry. Successful transport alone is not evaluation or release evidence.

## Alternatives considered

- Scattered direct Arize calls would couple model code to the vendor and make
  identity/privacy checks inconsistent.
- Sending whole DataFrames by implicit column discovery would risk unreviewed
  fields. This adapter uses explicit scalar fields and a narrow actual schema.
- Phoenix/OpenInference tracing is not the traditional ML telemetry surface
  selected by the current Arize Python v8 SDK.
- A queue or second registry would expand Story #42 beyond its remit.

## Acceptance criteria

- Canonical model/version/space mismatch blocks before transmission.
- Training, validation, production, and delayed actual paths use reviewed
  Atlas payloads and explicit environment semantics.
- Unknown/private fields and missing credentials fail clearly without secret
  text in diagnostics.
- Offline tests cover valid paths, zero actual, transport failures and retry
  limits; optional synthetic DEV proof requires explicit opt-in.

## Rollout, observability, and rollback

Review this proposal and the Story #42 PR before merge. The integration stays
optional and performs no automatic sending. After approval, enable per model
only with separately reviewed telemetry field classification and a local
Arize credential/space. To roll back, stop invoking the adapter; retain
Snowflake canonical predictions and report telemetry as unavailable. No
Snowflake or Arize object is created by merging this code.

## Links to affected contracts and tests

- [Canonical lineage contract](../architecture/declarative-ml-contracts-v1.md)
- [Arize integration guide](../arize-integration.md)
- `src/lyme_gap_atlas_ml/observability/`
- `tests/test_observability.py`
- [Workspace governance baseline](../../../TECHNOLOGY_AND_GOVERNANCE.md)
