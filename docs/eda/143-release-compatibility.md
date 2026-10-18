# 143: Is the pinned latent-class batch compatible with the current Atlas release?

- Issue: [ML #143](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/143), under [ML #138](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/138). Question: can the pinned surveillance-situation batch be displayed with the Atlas release that is current now?
- Data: `ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V`, one release row. Pinned fit: `governed-2026-10-15-january-climate-prod`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`.
- Cohort: the national surveillance-situation batch, 3,144 counties. This check does not reread county rows.

## Method and assumptions

Read the current production release identity with the approved read-only role. Compare release id, bundle SHA-256, schema version, methodology version, scope, and generated and loaded timestamps with the pinned fit. A matching release title, or an equal county count, is not the comparison.

Context immediately before the read, 2026-10-18: user `MATTHEWCARAWAY`, role `OH_LYME_PROD_READ`, database `ONE_HEALTH_LYME_GAP_ATLAS_PROD`, schema `PRESENTATION`, warehouse `COMPUTE_WH`, secondary roles empty. The session selected that schema and warehouse. No stronger role was used.

The historical #119 result is unchanged. This note does not refit the model and does not retag the batch.

## Material findings and limits

Observed at `2026-10-18T10:12:02.959000-07:00`.

| Field | Live release | Pinned fit |
| --- | --- | --- |
| Release | `governed-2026-10-15-january-climate-prod` | `governed-2026-10-15-january-climate-prod` |
| Bundle SHA-256 | `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d` | `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d` |
| Schema / method | `2.0.0` / `semantic-2.0.0` | `2.0.0` / `semantic-2.0.0` |
| Scope | `US_COUNTIES` | `US_COUNTIES` |
| Generated / loaded | `2026-10-15 13:51:25.324 -0700` / `2026-10-15 14:08:33.953 -0700` | `2026-10-15 13:51:25.324 -0700` / `2026-10-15 14:08:33.953 -0700` |

The live row is the same release identity the batch was fit on. There is no newer release in this read. This task writes no production Snowflake object.

[Data #698](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/698) still owns the Tier 1 release-completeness repair and its machine-enforced contract. This batch obeys that contract by remaining eligible only while its release id and bundle SHA-256 equal the current published release. It is not a substitute for a Tier 1 HIGH, MEDIUM, or LOW value, and it does not repair the stored Tier 1 batch.

When the batch is unavailable, including when the current release id or bundle SHA-256 differs from the pinned fit, the consumer returns an explicit unavailable state. The consumer does not substitute another class, a zero, or a Tier 1 priority.

## Decision

Carry forward, dated 2026-10-18, before any publication approval.

The reason is exact release identity: the same release id and the same bundle SHA-256, with the same schema, method, scope, and generated and loaded timestamps. Carry forward applies only to this snapshot. A later Atlas release does not silently inherit these assignments. A different live identity requires a new dated decision: a new versioned batch, or a block. This decision does not approve publication. Approval remains [ML #145](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/145).

## Reproduction and retained evidence

- Repository revision at the read: `603ca089f2f285d4c66da903229215af1db7a4c1`.
- Entry point: [143_release_compatibility.sql](../../sql/validation/143_release_compatibility.sql).
- Command shape: `snow sql` against `ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION` on `COMPUTE_WH`, secondary roles none, after the context check. The local connection name is not recorded.
- Objects read: `PRESENTATION.CURRENT_RELEASE_V`. No county extract. No object was written.
- Verification: `uv run python scripts/verify.py`.
- Transient artifacts not committed: the CLI JSON response. No county file was created by this check.
