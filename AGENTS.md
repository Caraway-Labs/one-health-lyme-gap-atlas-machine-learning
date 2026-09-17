# one-health-lyme-gap-atlas-machine-learning

Owns machine learning work against Atlas data in Snowflake. Workspace
[AGENTS.md](../AGENTS.md) remains mandatory and is not weakened here.

## Local commands

```powershell
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

## Repository rules

- Do not put Snowflake credentials, PAT files, or `.env` values in source
  control, logs, or tests.
- Do not add a browser client, Next.js route, or public API in this repository.
- Use the lowest-privilege DEV Snowflake connection that satisfies the work.
- Keep trained artifacts, notebook outputs, and local data dumps out of git.
