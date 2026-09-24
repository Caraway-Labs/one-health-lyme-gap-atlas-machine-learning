---
name: snowflake-context-check
description: Verify approved Snowflake identity and environment before any agent-initiated Snowflake operation.
---

# Snowflake context check

Use before an approved Snowflake action. Read repository `AGENTS.md` and the
workspace [connection inventory](../../../../one-health-lyme-gap-atlas-data/docs/operations/connection-inventory.md).
Select a least-privilege, environment-appropriate local CLI connection without
printing its name or secrets. Query `CURRENT_USER`, `CURRENT_ROLE`,
`CURRENT_DATABASE`, and `CURRENT_WAREHOUSE` read-only; compare to task scope.
Record a sanitized pass/block result. Stop on mismatch, unknown identity,
missing authorization, or unavailable credentials. This grants no write
permission. Story #40 owns execution integration.
