---
name: snowflake-readonly-analysis
description: Perform bounded approved read-only Snowflake analysis with source and scope evidence.
---

# Snowflake read-only analysis

Use for authorized Snowflake inspection. First run
[context check](../snowflake-context-check/SKILL.md). Identify approved
environment, objects, purpose, and query bounds. Use read-only CLI queries and
minimize results. Record objects read, query or method, observation time, and
limitations. Stop if scope, provenance, access, or context is unclear; do not
switch to stronger credentials. Repository `AGENTS.md` remains authoritative.
Story #40 owns reusable data adapters.
