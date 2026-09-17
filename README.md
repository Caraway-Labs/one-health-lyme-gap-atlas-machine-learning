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

Snowflake access for agent-initiated work uses the installed `snow` CLI and
the local `BVB26657_PAT` named `PROGRAMMATIC_ACCESS_TOKEN` connection. Validate
`CURRENT_USER`, `CURRENT_ROLE`, `CURRENT_DATABASE`, and `CURRENT_WAREHOUSE`
with a read-only query before any Snowflake action. PAT values stay local and
are never committed.
