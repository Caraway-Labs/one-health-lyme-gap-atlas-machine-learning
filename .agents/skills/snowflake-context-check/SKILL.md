---
name: snowflake-context-check
description: Verify approved Snowflake identity and environment before any agent-initiated Snowflake operation.
---

# Snowflake context check

Before an approved action, read repository `AGENTS.md`, the
[connection inventory](../../../../one-health-lyme-gap-atlas-data/docs/operations/connection-inventory.md),
and [integration guide](../../../docs/snowflake-integration.md).

1. Select a least-privilege local named PAT connection through
   `SNOWFLAKE_CONNECTION_NAME`; do not print the selector or secret. Missing
   configuration blocks live work, not docs or unit tests.
2. Run the guide's read-only `snow sql` context query. Verify user, role,
   database, schema, and warehouse against the authorized task and intended
   environment. Do not infer DEV from the connection name alone.
3. Stop on missing or ambiguous fields, mismatch, unsafe privilege, expired
   PAT, or absent task authorization. Do not switch to a stronger connection
   or interactive authentication as a workaround.
4. Record a sanitized pass/block result with the five context fields and
   scope. Context validation grants no write permission.
