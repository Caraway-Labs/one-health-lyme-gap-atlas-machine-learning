# one-health-lyme-gap-atlas-machine-learning

Machine learning workflows for One Health Lyme Gap Atlas data that lives in
Snowflake.

This repository owns model training, evaluation, experiment code, and related
research artifacts. It does not own governed ingestion (`data`), the public
REST contract (`api`), or the browser application (`web`). The browser still
calls the Python REST API only; this repository must never expose Snowflake
credentials or query logic to the frontend.

```powershell
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Run all mandatory offline checks with `uv run python scripts/verify.py` after
`uv sync --extra dev`. It prints a JSON status line per check and returns
nonzero on failure. CI runs this same credential-free path. The mandatory path
excludes live integration tests and clears their opt-in flags even if inherited
from the shell. Configuration,
skills, lifecycle, and contract changes are validated there alongside Ruff,
mypy, and pytest. Live proofs require an approved DEV context and a separate
`--integration snowflake` or `--integration arize` invocation with the matching
`ATLAS_RUN_*_DEV_TEST=1` flag and local settings in the integration guides.

For agent-initiated Snowflake work, select a locally configured `snow` CLI
connection through a task-specific environment variable, for example
`SNOWFLAKE_CONNECTION_NAME`. Choose the least-privilege connection for the
approved environment and operation; routine inspection uses a read-only DEV
role. Verify `CURRENT_USER`, `CURRENT_ROLE`, `CURRENT_DATABASE`, and
`CURRENT_WAREHOUSE` with a read-only query before any Snowflake action. The
[data repository connection inventory](../one-health-lyme-gap-atlas-data/docs/operations/connection-inventory.md)
defines the role mapping. Never commit or log the local connection name,
credentials, PATs, API keys, or `.env` values. No connection is required for
local documentation or unit-test work.

The [repository rules](AGENTS.md) and [structure guide](docs/repository-structure.md)
describe ownership, reproducibility, and intended package boundaries.
The [shared ML skills catalog](docs/skills.md) describes the canonical
`.agents/skills/` procedures and harness discovery boundaries.
The [Snowflake integration guide](docs/snowflake-integration.md) covers the
optional Python connector, live DEV context proof, CLI, Cortex Code, and
read-only execution boundary.
The [declarative ML contracts](docs/architecture/declarative-ml-contracts-v1.md)
define offline model, dataset, experiment, and cross-system lineage identity.
The [Arize integration guide](docs/arize-integration.md) describes optional,
allowlisted traditional ML telemetry through the Atlas observability boundary.
The [cross-signal disagreement draft](docs/contracts/cross-signal-disagreement-v1.md)
defines a transparent baseline and evidence prerequisites without approving
operational signal pairs, thresholds or clinical claims.
