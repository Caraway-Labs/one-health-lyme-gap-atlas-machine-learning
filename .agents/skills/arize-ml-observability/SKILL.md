---
name: arize-ml-observability
description: Scope Arize ML telemetry and evaluation integration without exposing private data or inventing policy.
---

# Arize ML observability

Use for Arize integration planning or review. Read repository `AGENTS.md`,
[Epic #36](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/36),
and approved data classification. Identify permitted fields, lineage keys,
purpose, and unresolved privacy or access decisions. Stop before sending data
or credentials without approved scope. Stories #42-#44 own the adapter,
monitoring policy, and optional tools; this defines no telemetry implementation.
Use the [canonical identity mapping](../../../docs/architecture/declarative-ml-contracts-v1.md)
for Arize project/model/version; stop if it differs from Atlas model/version
or the corresponding Snowflake registry mapping.
