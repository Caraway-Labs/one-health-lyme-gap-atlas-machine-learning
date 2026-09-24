# 0001: Declarative ML lineage identity

Status: Accepted
Date: 2026-09-24
Decision owner: Atlas ML product and engineering leads

## Context

Story #41 under Epic #36 requires one identity and lineage contract across
GitHub, Atlas ML artifacts, Snowflake, Arize, prediction runs, and monitoring
evidence. The accepted workspace ADR 0020 assigns ML model and experiment work
to this repository; Story #39 already defines lifecycle state v1 and Story #40
establishes the Snowflake integration boundary. Stories #23 and #30 have not
approved a real prediction target, metrics, or thresholds.

## Decision

Use versioned JSON declarations validated offline by the ML repository. A
canonical model identity is a lowercase kebab-case Atlas model ID, `vN` style
version, family, owning GitHub issue URL, and full lowercase git commit SHA.
Dataset, feature, split, evaluation, experiment, and run identifiers remain
separate. The Snowflake registry model/version and Arize model/version mapping
must retain the exact canonical Atlas ID/version; platform object handles are
additional references. The contract carries an explicit prediction run and
monitoring/evaluation evidence state. Missing evidence is `not_collected`,
never implied approval.

Keep lifecycle `atlas-ml-lifecycle/v1` unchanged and validate compatible
references when both contracts are supplied. Governed source ingestion and
normalization remain in the data repository. No real model target, data source,
Snowflake object, Arize telemetry, or release is approved by this decision.

## Consequences

Future #26 runs, #32 outputs, and #42–#43 integrations must use this identity
or propose an explicit schema/ADR evolution. Every published bundle needs
stable references and a source commit; arbitrary independent registry names
fail validation. A new schema version and migration are required for breaking
shape or meaning changes. The JSON Schema covers structure; the standard
library Python validator also checks compatibility and prohibited secret keys.

## Alternatives considered

- Separate Snowflake and Arize naming was rejected because it breaks the
  requested single lineage chain.
- Random IDs were rejected where a stable versioned reference suffices.
- A configuration framework or SDK dependency was rejected for offline JSON
  validation.
- Changing lifecycle v1 in place was rejected because it would silently alter
  Story #39 semantics and fixtures.

## Acceptance criteria

- A complete synthetic bundle validates offline and round-trips.
- Unknown schema versions, missing or colliding IDs, incompatible references,
  and secret-bearing fields fail.
- Snowflake and Arize mappings resolve to the same canonical model/version.
- Lifecycle references can be checked without modifying lifecycle v1.
- No external service access is needed for contract tests.

## Rollout, observability, and rollback

Roll out as metadata and tests in the ML repository only. Human review of this
proposed ADR and the Story #41 PR is required before adopting it on `main`.
No Snowflake or Arize object is mutated. If review rejects the convention,
revise the branch and schema before merge; do not reinterpret v1 in place.

## Links to affected contracts and tests

- [Declarative contract guide](../architecture/declarative-ml-contracts-v1.md)
- [Structural JSON Schema](../architecture/declarative-ml-contracts-v1.schema.json)
- `src/lyme_gap_atlas_ml/contracts.py`
- `tests/test_contracts.py`
- [Workspace ADR 0020](../../../docs/adr/0020-machine-learning-owning-repository.md)
