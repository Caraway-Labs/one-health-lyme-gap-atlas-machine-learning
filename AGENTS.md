# Atlas machine learning repository rules

Workspace [AGENTS.md](../AGENTS.md) and the accepted [ML ownership ADR](../docs/adr/0020-machine-learning-owning-repository.md) also apply. These rules are shared by Codex, Cursor, OpenCode, and Cortex Code; do not maintain conflicting harness-specific policy.

## Scope and authority

This repository owns ML feature, model, evaluation, experiment, registry, monitoring integration, and lifecycle-related code. Governed source ingestion and canonical normalization belong to the data repository; public REST contracts belong to the API repository; browser behavior belongs to the web repository. Production secrets belong in approved external secret stores, never here. No issue alone authorizes production Snowflake mutation, autonomous retraining, model promotion, or public release.

For bounded work, use this source-of-truth order: GitHub issue acceptance criteria, this `AGENTS.md` (alongside mandatory workspace rules), versioned architecture/ADR/methodology documents, code and tests, examples, then agent assumptions. Higher-level workspace safety and ownership rules remain mandatory. Resolve contradictions with the owner before implementation; do not treat an example or assumption as approval.

## Agent workflow

Before implementation, read the issue and relevant parent/context, applicable rules and contracts, and the working tree. Identify the owning repository, affected methodology and architecture decisions, approved environment, data/target definitions, acceptance criteria, and out-of-scope work. Stop for a recorded decision when a target, public interpretation, access boundary, or production write scope is ambiguous.

During implementation, keep Snowflake I/O in adapters or integration boundaries and core feature/model/evaluation logic independently testable. Version the dataset snapshot or query, feature definitions, split assignment, and experiment configuration; record code revision and dependencies so results can be reproduced. Set and record deterministic seeds wherever randomness is used, and disclose remaining nondeterminism. Prevent temporal, spatial, and target leakage in feature construction and evaluation. Protect holdout membership and labels from tuning, selection, and repeated exploratory use. Preserve negative and inconclusive findings with their evidence; never turn missing evidence into a positive result.

Use an environment/config-selected, least-privilege Snowflake CLI connection. Validate current user, role, database, and warehouse with a read-only query before any Snowflake action. Keep credentials, PATs, API keys, local connection identifiers, `.env` values, and secrets out of source control, logs, tests, and examples. Do not use an administrative or production connection without explicit authorization. Do not use browser authentication as a fallback. No Snowflake access is required for documentation-only work.

Before declaring completion, review the diff against every issue criterion; run `uv run python scripts/verify.py` for mandatory offline contract, skill, lifecycle, hygiene, Ruff, mypy, and pytest checks, plus relevant focused checks. The underlying `uv` commands remain valid. Report files changed, architecture/methodology decisions, test evidence, Snowflake objects read or written (or none), assumptions, unresolved risks and dependencies. Distinguish local checks from live Snowflake or hosted evidence. Do not claim a lifecycle gate, scientific review, or deployment passed without its evidence.

Keep task-specific procedures in versioned docs or future shared skills. See [repository structure](docs/repository-structure.md) for intended boundaries and test layers.

## Cursor Cloud Agent

Cursor Cloud Agents must treat this repository like CI: after `uv sync --extra dev`
(or the locked bootstrap in `.cursor/environment.json`), run
`uv run python scripts/verify.py` before declaring work complete unless the
issue explicitly requires additional integration proofs.

Live Snowflake access is **opt-in** only (Dashboard Runtime secrets and the
Level B bootstrap in [cursor-cloud-agent runbook](docs/runbooks/cursor-cloud-agent.md)).
Documentation, contracts, and unit tests do not require a warehouse connection.
Follow [Snowflake integration](docs/snowflake-integration.md) for the context
check before any query. DEV reads use the read-only DEV path. The ML agent
identity uses the PROD read and ML Lab write rules below.

Never commit or log credentials, PATs, API keys, local `SNOWFLAKE_CONNECTION_NAME`
selectors, or `.env` values. Cloud configuration belongs in the Cursor Dashboard,
not in git.

Optional DEV Snowflake for Cloud Agents uses Dashboard Runtime secrets and
`scripts/bootstrap_cloud_snowflake_connection.sh` (Level B in
[cursor-cloud-agent runbook](docs/runbooks/cursor-cloud-agent.md)). That path
stays read-only DEV. PROD reads and ML Lab writes use only the identity in
the next section.

## PROD read and ML Lab write

Epic [#155](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/155)
authorizes one cloud agent identity. The same rules are in the
[cursor-cloud-agent runbook](docs/runbooks/cursor-cloud-agent.md) and
[Snowflake integration](docs/snowflake-integration.md). This is the explicit
authorization for that identity. It does not authorize an administrative
connection, a PROD write, or PROD access for any other user.

- PROD is read-only. Writes go only to the ML Lab database
  `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`, schemas `REGISTRY`, `EDA`, `FEATURES`,
  `EXPERIMENTS`, and `SCRATCH`.
- No access to `GOVERNANCE` (personal data), `RAW`, `STAGING`,
  `KNOWLEDGE_GRAPH`, or `RESTRICTED_CDC_*`.
- PROD read is limited to an allow-list of `CONFORMED`, `FEATURE_STORE`, and
  `PRESENTATION` objects granted to role `OH_LYME_PROD_ML_EDA_READ`. A new
  PROD table is invisible until explicitly granted.
- Aggregates only. No record-level extracts leave Snowflake.
- Small-cell rule: suppress `n < 11`.
- Free-text columns (for example `PART_TEXT`, `CONTEXT_LIMITATIONS`) must not
  be exported or quoted at record level.
- EDA conclusions go in `docs/eda/<issue>-<topic>.md`. Extracts stay out of
  git. Charts go to Google Drive.

Identity:

- Snowflake user `OH_LYME_ML_AGENT_SVC`.
- Role `OH_LYME_ML_AGENT`.
- Warehouse `OH_LYME_ML_LAB_XS_WH` (X-Small, 60 s auto-suspend, 20 credits per
  month resource monitor).
- Authentication is a programmatic access token restricted to role
  `OH_LYME_ML_AGENT`, with a 30 day life (rotate before expiry). Owner steps
  are in the [ML Lab operations runbook](docs/runbooks/ml-lab-operations.md).
- No network policy. The per-user authentication policy on
  `OH_LYME_ML_AGENT_SVC` sets
  `NETWORK_POLICY_EVALUATION = ENFORCED_NOT_REQUIRED`, by owner decision on
  [#157](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/157#issuecomment-6391048205).

Cursor Dashboard secret names only, never values: `SNOWFLAKE_PAT` (Runtime
Secret), `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`,
`SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`. Documentation-only work does not
connect to Snowflake.

## Durable EDA and analysis evidence

For material EDA, statistical analysis, feature investigation, or ML experimentation,
persist decision-oriented conclusions in `docs/eda/<issue>-<topic>.md`
(issue number plus a short topic, the same pattern as the EDA guide).
Follow the [EDA guide and template](docs/eda/README.md): record the question,
governed source/release/version, cohort/geography/time window, method/assumptions,
findings and uncertainty, missingness/quality limits, disposition, and exact
reproduction commands. Check in reusable SQL/code/config in the appropriate
source location and reference it; do not depend on notebook-only state.

EDA conclusions go in `docs/eda/<issue>-<topic>.md`. Extracts stay out of git.
Charts go to Google Drive. Published conclusions follow the PROD read and ML
Lab write rules above: aggregates only, suppress `n < 11`, and do not quote
free-text columns at record level. Snowflake extracts, generated CSVs,
temporary query results, notebook outputs, and caches stay out of git. Local
working files, when a story still needs them, stay in ignored `outputs/` or
`data/local/`. A story may still require a small fixture or curated governed
artifact that is not a record-level extract. Never commit credentials, local
machine paths, raw sensitive data, or uncontrolled warehouse exports. Clear notebook
outputs before committing a reusable notebook. Keep durable findings concise.

Analysis PR descriptions and final summaries must state the question, material
conclusion and disposition, link the EDA artifact, give exact verification/replay
commands, identify caveats/follow-ups, and state which transient outputs were not
committed. For work without EDA/analysis, mark this artifact requirement N/A;
normal verification still applies. This evidence supports the existing lifecycle,
lineage and scientific review; it adds no parallel gate or release authority.
