---
name: arize-ml-observability
description: Scope Arize ML telemetry and evaluation integration without exposing private data or inventing policy.
---

# Arize ML observability

Use for a bounded traditional ML telemetry send or review. Read repository
`AGENTS.md`, [Epic #36](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/36),
the [canonical identity contract](../../../docs/architecture/declarative-ml-contracts-v1.md),
and the [integration guide](../../../docs/arize-integration.md).

1. Validate the complete Story #41 bundle. Resolve model ID/version and Arize
   space from its approved mapping. Stop if model, version, project/space, or
   Snowflake registry identity conflicts.
2. Check data classification and the reviewed telemetry allowlist/policy
   reference. Send only approved scalar features/tags. Stop on unknown private
   fields, contact data, arbitrary text, or unresolved classification.
3. Select training/reference, validation, or production explicitly. Validate
   prediction ID, timestamp, label/score, and validation batch ID. For a
   delayed actual, verify the stable prediction linkage and label maturity.
4. Send through the Atlas `ObservabilitySink` and Arize adapter. Keep API keys
   in runtime secret configuration; never place them in lineage files or output.
5. Report the non-secret telemetry outcome. Record a rejected payload,
   unavailable configuration, or failed transport as missing evidence without
   changing the canonical prediction. Do not infer monitoring sufficiency or
   release readiness from a successful send.

Stop when identity, credential scope, privacy, or labeling is ambiguous.
Story #43 owns thresholds and monitoring policy; #44 owns CLI/MCP tooling.
