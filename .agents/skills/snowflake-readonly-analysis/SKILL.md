---
name: snowflake-readonly-analysis
description: Perform bounded approved read-only Snowflake analysis with source and scope evidence.
---

# Snowflake read-only analysis

Use for approved, bounded inspection. First complete the
[context check](../snowflake-context-check/SKILL.md). Identify the purpose,
environment, exact source objects, provenance, and row/time/cost bounds before
querying. Use the least-privilege DEV read role and read-only `snow sql` or the
approved Python adapter. Keep repeatable SQL under the reviewed
[SQL convention](../../../sql/README.md); parameterize untrusted inputs.

Record the query/file and revision, observation time, non-secret context,
objects read, bounds, result summary, and limitations. Minimize results and
avoid sensitive row dumps. Stop when context, scope, or provenance is unclear.
If a write or stronger role is needed, escalate for explicit task authorization
and approved DEV target; do not silently switch connections. The
[integration guide](../../../docs/snowflake-integration.md) and repository
`AGENTS.md` remain authoritative.
