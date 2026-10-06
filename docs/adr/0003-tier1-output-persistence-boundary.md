# 0003: Tier 1 output persistence boundary

Status: Product direction approved; exact Data implementation and security review pending
Date: 2026-10-05
Decision owner: Atlas product, data, ML, API, and security leads

## Context

Workspace ADR 0020 reserves ML output promotion into API-readable Snowflake objects for a later decision. ML #30 selected the unsupervised statistical reference. The DEV `FEATURE_STORE` schema exists but contains no prediction object; the ML repository has no write migration or approved ML publisher role. The read-only DEV identity must not create objects or broaden grants.

## Approved product direction

Data owns one narrow `FEATURE_STORE.TIER1_COUNTY_REVIEW_OUTPUTS` table, one `FEATURE_STORE.TIER1_REVIEW_BATCHES` manifest table, and a `PRESENTATION.CURRENT_TIER1_COUNTY_REVIEW_V` read view. A protected data-repository migration creates these objects and grants a dedicated ML publisher only the minimum batch publication procedure `USAGE`; API runtime receives `SELECT` on the view only. The procedure accepts an immutable complete batch, validates expected population and digest against the manifest, then publishes the active batch in a single transaction. It rejects replay with changed bytes and never updates an approved row. No direct runtime table DML, general model registry, scheduler, or public browser connection is authorized. DEV is the first application target; PROD uses the existing protected data promotion process after reviewed evidence and approval.

ML owns the score, percentile, tier, evidence sufficiency, reasons, lineage, and batch builder. Data owns Snowflake DDL, narrow publication authority, and the consumer view. API #10 reads only the approved view; it never invokes ML. The initial approved model is `tier1-statistical-reference-v1`; the Forest is excluded.

## Consequences and gate

This ADR does not create a Snowflake object or grant. Data and security review must settle the exact migration, procedure identity, role bootstrap, and protected promotion path before any live write. The ML branch can regenerate and validate a local batch without pretending that file evidence is persisted approval. Its county FIPS set must exactly equal the regenerated governed feature population, and the Data-owned publisher must verify that equality independently before activation. A pre-merge PR artifact is review evidence only. The first publishable candidate must be regenerated from the final merged `origin/main` commit; its source commit, batch ID, output digest, and generation time are recorded after that run, including when the PR is squash merged. If validation or publication fails, the active pointer remains at the previous approved batch. PROD promotion remains separately protected.

## Alternatives considered

Writing an unmanaged ML-owned table, using a public API table created ad hoc, and publishing the rejected Forest were rejected. A generalized model registry and online inference add scope without supporting the V1 result.

## Acceptance criteria

- Review accepts the data-owned object/procedure and exact least-privilege roles.
- DEV migration and publication are verified with a real selected batch and API read role.
- Partial, duplicate, wrong-lineage, and changed-digest replays leave the prior active batch readable.
- Protected PROD promotion is separately approved if API #10 requires PROD.

## Data implementation handoff

Implement the approved direction in a separate Data-repository issue, isolated worktree, and PR based on its then-current `origin/main`. Data #114 remains its deferred, post-slice boundary-documentation story; it is not the migration issue. Use the next available forward-only migration version at implementation time, after verifying the live ledger and main. Do not alter historical migration checksums.

The bounded migration needs the two named `FEATURE_STORE` tables, a singleton active-batch pointer and write-serialization row, a narrow owner-rights chunk-stage procedure and finalize/activate procedure, and the named `PRESENTATION` current-batch view. Stage immutable county rows in bounded chunks under an unpublished batch ID. The Data PR must specify and test byte-identical canonical row serialization for the ML output digest; Snowflake `VARIANT` reserialization must not silently change it. The finalize procedure must serialize concurrent publishers, reject changed-digest replay, independently compare the exact staged FIPS set to the pinned governed release's county population in the same environment, validate row count, lineage, selected model, score/tier/evidence invariants, and digest, then activate the pointer in one transaction. An error or lost acknowledgment must leave the previous active batch intact and support an idempotent same-digest retry. Snowflake informational primary/unique keys alone do not enforce this.

Security review must approve an environment-specific, least-privilege ML publisher service role with only procedure `USAGE`, a separate non-login procedure owner with only required object privileges, and the existing `OH_LYME_{ENV}_READ` consumer role's `SELECT` on the current-batch view only. No direct publisher table DML or API base-table access is proposed. Account-level role/service bootstrap is separate from the Data migration and needs its own reviewed authorization. DEV migration application uses the Data repository's protected `deploy-dev.yml`; PROD uses its protected `promote-prod.yml` only after DEV proof and a reviewed, same-environment governed release/batch plan. A DEV-only release ID must not be silently copied into PROD.

## Rollout, rollback, and links

Roll out in DEV through a reviewed data-repository migration, then publish the ML-generated batch. Rollback changes only the active approved batch pointer through a reviewed owner procedure; immutable rows remain for audit. See [output contract](../contracts/tier1-persisted-output-v1.md), ML #32, API #10, and workspace ADR 0020.
