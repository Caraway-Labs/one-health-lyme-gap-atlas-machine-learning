# 0003: Five-stage lifecycle state v2

Status: Proposed
Date: 2026-10-01
Decision owner: Atlas ML product and engineering leads

## Context

Current Story #39 under Epic #36 requires Frame, Data, Baseline, Evaluate and
Decide. The eight-stage v1 foundation exceeds that contract. ADR 0001 forbids
silently changing v1 shape or meaning.

## Decision

Adopt `atlas-ml-lifecycle/v2` through the existing offline validator. Keep v1
schema/template/methodology unchanged for historical evidence. The active
validator rejects v1; do not automatically migrate or infer approvals.
Human review of this ADR and the #39 PR is required before adoption on main.
This supersedes only ADR 0001's requirement that active lifecycle use stay v1;
canonical lineage identities and matching reference checks remain unchanged.

## Consequences

Reuse the stage and holdout checks; reduce active stages from eight to five.
Derive current stage and holdout-used from existing state rather than duplicate
fields. Preserve evidence and required human decisions; no workflow service,
production monitoring gate, new target, telemetry, or execution permission.

## Alternatives considered

Changing v1 in place would reinterpret stored evidence. Supporting both stage
engines indefinitely adds maintenance without a current caller requirement.
Automatic migration cannot establish missing scientific evidence or decisions.

## Rollout and rollback

Update in-repository synthetic fixtures and verifier to v2; retain v1 files.
Owners inspect external v1 states and map evidence using the methodology's
migration note before validation. Revert this PR to restore active v1 handling.
No service deployment or Snowflake object change is involved.

## Acceptance criteria and evidence

Story #39: five stages, validated state, blocked-resume fixture, scientific gate
and transition regression tests, existing #23/#24/#25/#26/#30 references.

- [Lifecycle checklist and migration](../methodology/agentic-ml-lifecycle-v2.md)
- [State schema](../methodology/lifecycle-state-v2.schema.json)
- `src/lyme_gap_atlas_ml/lifecycle.py`
- `tests/test_lifecycle.py`, `tests/test_contracts.py`
