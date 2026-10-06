# 0003: Tier 1 output persistence boundary

Status: Proposed for product, data, API, and security owner review
Date: 2026-10-05
Decision owner: Atlas product, data, ML, API, and security leads

## Context

Workspace ADR 0020 reserves ML output promotion into API-readable Snowflake objects for a later decision. ML #30 selected the unsupervised statistical reference. The DEV `FEATURE_STORE` schema exists but contains no prediction object; the ML repository has no write migration or approved ML publisher role. The read-only DEV identity must not create objects or broaden grants.

## Proposed decision

Data owns one narrow `FEATURE_STORE.TIER1_COUNTY_REVIEW_OUTPUTS` table, one `FEATURE_STORE.TIER1_REVIEW_BATCHES` manifest table, and a `PRESENTATION.CURRENT_TIER1_COUNTY_REVIEW_V` read view. A protected data-repository migration creates these objects and grants a dedicated ML publisher only the minimum batch publication procedure `USAGE`; API runtime receives `SELECT` on the view only. The procedure accepts an immutable complete batch, validates expected population and digest against the manifest, then publishes the active batch in a single transaction. It rejects replay with changed bytes and never updates an approved row. No direct runtime table DML, general model registry, scheduler, or public browser connection is authorized. DEV is the first application target; PROD uses the existing protected data promotion process after reviewed evidence and approval.

ML owns the score, percentile, tier, evidence sufficiency, reasons, lineage, and batch builder. Data owns Snowflake DDL, narrow publication authority, and the consumer view. API #10 reads only the approved view; it never invokes ML. The initial approved model is `tier1-statistical-reference-v1`; the Forest is excluded.

## Consequences and gate

This proposal does not create a Snowflake object or grant. Owner review must settle the exact migration, procedure identity, and protected promotion path before any live write. The ML branch can regenerate and validate the local batch without pretending that file evidence is persisted approval. If a complete batch fails validation or publication, the active pointer remains at the previous approved batch. PROD promotion remains separately protected.

## Alternatives considered

Writing an unmanaged ML-owned table, using a public API table created ad hoc, and publishing the rejected Forest were rejected. A generalized model registry and online inference add scope without supporting the V1 result.

## Acceptance criteria

- Review accepts the data-owned object/procedure and exact least-privilege roles.
- DEV migration and publication are verified with a real selected batch and API read role.
- Partial, duplicate, wrong-lineage, and changed-digest replays leave the prior active batch readable.
- Protected PROD promotion is separately approved if API #10 requires PROD.

## Rollout, rollback, and links

Roll out in DEV through a reviewed data-repository migration, then publish the ML-generated batch. Rollback changes only the active approved batch pointer through a reviewed owner procedure; immutable rows remain for audit. See [output contract](../contracts/tier1-persisted-output-v1.md), ML #32, API #10, and workspace ADR 0020.
