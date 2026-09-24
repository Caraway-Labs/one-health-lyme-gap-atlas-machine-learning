# Atlas machine learning repository rules

Workspace [AGENTS.md](../AGENTS.md) and the accepted [ML ownership ADR](../docs/adr/0020-machine-learning-owning-repository.md) also apply. These rules are shared by Codex, Cursor, OpenCode, and Cortex Code; do not maintain conflicting harness-specific policy.

## Scope and authority

This repository owns ML feature, model, evaluation, experiment, registry, monitoring integration, and lifecycle-related code. Governed source ingestion and canonical normalization belong to the data repository; public REST contracts belong to the API repository; browser behavior belongs to the web repository. Production secrets belong in approved external secret stores, never here. No issue alone authorizes production Snowflake mutation, autonomous retraining, model promotion, or public release.

For bounded work, use this source-of-truth order: GitHub issue acceptance criteria, this `AGENTS.md` (alongside mandatory workspace rules), versioned architecture/ADR/methodology documents, code and tests, examples, then agent assumptions. Higher-level workspace safety and ownership rules remain mandatory. Resolve contradictions with the owner before implementation; do not treat an example or assumption as approval.

## Agent workflow

Before implementation, read the issue and relevant parent/context, applicable rules and contracts, and the working tree. Identify the owning repository, affected methodology and architecture decisions, approved environment, data/target definitions, acceptance criteria, and out-of-scope work. Stop for a recorded decision when a target, public interpretation, access boundary, or production write scope is ambiguous.

During implementation, keep Snowflake I/O in adapters or integration boundaries and core feature/model/evaluation logic independently testable. Version the dataset snapshot or query, feature definitions, split assignment, and experiment configuration; record code revision and dependencies so results can be reproduced. Set and record deterministic seeds wherever randomness is used, and disclose remaining nondeterminism. Prevent temporal, spatial, and target leakage in feature construction and evaluation. Protect holdout membership and labels from tuning, selection, and repeated exploratory use. Preserve negative and inconclusive findings with their evidence; never turn missing evidence into a positive result.

Use an environment/config-selected, least-privilege Snowflake CLI connection. Validate current user, role, database, and warehouse with a read-only query before any Snowflake action. Keep credentials, PATs, API keys, local connection identifiers, `.env` values, and secrets out of source control, logs, tests, and examples. Do not use an administrative or production connection without explicit authorization. Do not use browser authentication as a fallback. No Snowflake access is required for documentation-only work.

Before declaring completion, review the diff against every issue criterion; run the documented `uv`, Ruff, mypy, and pytest gates and relevant focused checks. Report files changed, architecture/methodology decisions, test evidence, Snowflake objects read or written (or none), assumptions, unresolved risks and dependencies. Distinguish local checks from live Snowflake or hosted evidence. Do not claim a lifecycle gate, scientific review, or deployment passed without its evidence.

Keep task-specific procedures in versioned docs or future shared skills. See [repository structure](docs/repository-structure.md) for intended boundaries and test layers.
