# Cursor Cloud Agent runbook (Atlas ML repository)

This runbook supports [Epic #149](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/149).
It separates what belongs in **Git** from what belongs in the **Cursor Dashboard**.

Official Cursor references:

- [Cloud Agent overview](https://cursor.com/docs/cloud-agent.md)
- [Environment setup](https://cursor.com/docs/cloud-agent/setup.md)
- [Secrets and network](https://cursor.com/docs/cloud-agent/security-network.md)

## Level A — Offline bootstrap (required)

Level A matches GitHub Actions (`.github/workflows/verify.yml`): no Snowflake
credentials, no API keys, no `.env` in the repository.

### What is committed in this repo

| Artifact | Purpose |
| --- | --- |
| `.cursor/environment.json` | Tells Cloud Agent how to install and verify |
| `scripts/cloud_agent_bootstrap.sh` | Install pinned `uv` when it is missing, then `uv sync --locked --extra dev` and `scripts/verify.py` |

### PM checklist (Cursor Dashboard)

1. Connect GitHub for org **Caraway-Labs** and grant access to this repository.
2. Open **Dashboard → Cloud Agents** and create an environment for
   `one-health-lyme-gap-atlas-machine-learning`.
3. Point the environment at this repository's committed
   `.cursor/environment.json` (or paste equivalent install steps).
4. Run **Build** and confirm it succeeds. Agents start from the latest
   successful Build only.
5. No Dashboard **secrets** are required for Level A.

### Engineering verification

From a clean Linux checkout (`uv` is installed by the script when it is absent):

```bash
bash scripts/cloud_agent_bootstrap.sh
```

Expect exit code `0` and JSON status lines from `verify.py`.

### Parity with CI

| Step | GitHub Actions `Verify` | Cloud `cloud_agent_bootstrap.sh` |
| --- | --- | --- |
| Dependency install | `uv sync --locked --extra dev` | Same |
| Mandatory checks | `uv run python scripts/verify.py` | Same |
| Live Snowflake | Not run | Not run (Level A) |

### Agent smoke task

After Build succeeds, start an agent with:

> Run `uv run python scripts/verify.py` and report pass or fail.

### If `uv` is missing on the base image

Level A does not assume the Cloud base image provides `uv`. When `command -v uv`
fails, `scripts/cloud_agent_bootstrap.sh` installs pinned uv `0.13.5` with the
standalone installer (`UV_UNMANAGED_INSTALL=$HOME/.local/bin`) and copies `uv`
and `uvx` into `/usr/local/bin`. That directory is on the default `PATH` for
later agent shells. CI still installs uv with `astral-sh/setup-uv`. See Cursor
[environment setup](https://cursor.com/docs/cloud-agent/setup.md).

## Level B — Optional DEV Snowflake (read-only)

Level B is **opt-in**. Most agent tasks should stay on Level A. Enable Level B
only when a GitHub issue explicitly requires live DEV warehouse reads and your
Snowflake admin has approved a dedicated cloud-agent service user.

Policy matches [Snowflake integration](../snowflake-integration.md) and
`AGENTS.md`: read-only by default, context query before data, no browser
authentication fallback, no production writes.

### Dashboard Runtime secrets (names are the contract)

Configure values in **Cursor Dashboard → Cloud Agents → Secrets** as **Runtime
secrets** (never commit values to git).

| Secret name | Purpose |
| --- | --- |
| `SNOWFLAKE_CONNECTION_NAME` | Alias used by `snow sql -c` (admin-chosen; not personal) |
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier for CLI |
| `SNOWFLAKE_USER` | Service user for cloud agents |
| `SNOWFLAKE_PAT` | Programmatic access token (**preferred**) |
| `SNOWFLAKE_PASSWORD` | Password auth only if PAT is unavailable |
| `SNOWFLAKE_ROLE` | Least-privilege DEV read role (e.g. `OH_LYME_DEV_READ`) |
| `SNOWFLAKE_DATABASE` | DEV database (e.g. `ONE_HEALTH_LYME_GAP_ATLAS_DEV`) |
| `SNOWFLAKE_SCHEMA` | e.g. `PRESENTATION` |
| `SNOWFLAKE_WAREHOUSE` | DEV warehouse |

Optional **live proof** variables (expected context — not secrets):

| Variable | Purpose |
| --- | --- |
| `ATLAS_RUN_SNOWFLAKE_DEV_TEST` | Set to `1` to opt into live integration test |
| `ATLAS_EXPECTED_SNOWFLAKE_DEV_ROLE` | Expected `CURRENT_ROLE()` |
| `ATLAS_EXPECTED_SNOWFLAKE_DEV_DATABASE` | Expected database |
| `ATLAS_EXPECTED_SNOWFLAKE_DEV_SCHEMA` | Expected schema |
| `ATLAS_EXPECTED_SNOWFLAKE_DEV_WAREHOUSE` | Expected warehouse |

Live proof command (after Level B secrets are injected at agent start):

```bash
uv sync --locked --extra dev --extra snowflake
bash scripts/bootstrap_cloud_snowflake_connection.sh
uv run python scripts/verify.py --integration snowflake
```

### Bootstrap scripts

| Script | When it runs |
| --- | --- |
| `scripts/bootstrap_cloud_snowflake_connection.sh` | Writes `connections.toml` under `~/.snowflake` from Runtime secrets |
| `scripts/cloud_agent_bootstrap.sh` | Calls Snowflake bootstrap when `SNOWFLAKE_ACCOUNT` is set; otherwise Level A only |

During Cloud **Build**, secrets are usually absent — Build remains Level A.
When an **agent starts**, Dashboard injects secrets; if `SNOWFLAKE_ACCOUNT` is
present, `cloud_agent_bootstrap.sh` configures Snowflake before `verify.py`.

Set `SNOWFLAKE_BOOTSTRAP_SKIP_CONTEXT_CHECK=1` to skip the context query during
install (default during bootstrap). Remove it (or set to `0`) when you want the
script to run the read-only context query immediately after writing the
connection.

### Snowflake CLI on the Cloud VM

Level B requires the [Snowflake CLI](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index) (`snow` 3.x) on the agent VM. If the
default Cloud image lacks it, add a `.cursor/Dockerfile` (example only — adapt
versions):

```dockerfile
FROM cursor/default
RUN curl -fsSL https://github.com/snowflakedb/snowflake-cli/releases/latest/download/snowflake-cli-linux-x86_64.tar.gz \
  | tar -xz -C /usr/local/bin snow
```

Reference Cursor [environment setup](https://cursor.com/docs/cloud-agent/setup.md)
to attach the Dockerfile to the saved environment.

### Agent workflow (Level B)

1. Confirm issue authorization and DEV read-only scope.
2. Ensure Runtime secrets from the table above are configured.
3. Run `bash scripts/bootstrap_cloud_snowflake_connection.sh` (or rely on
   `cloud_agent_bootstrap.sh` when `SNOWFLAKE_ACCOUNT` is set).
4. Verify `CURRENT_USER`, `CURRENT_ROLE`, `CURRENT_DATABASE`, `CURRENT_SCHEMA`,
   and `CURRENT_WAREHOUSE()` match the approved task.
5. Run only reviewed SQL under `sql/` within approved bounds.

### Network

Allow outbound `*.snowflakecomputing.com` if your Cursor environment uses an
egress allowlist. See [Secrets and network](https://cursor.com/docs/cloud-agent/security-network.md).

## Security reminders

- Never commit credentials, PATs, API keys, or personal connection names.
- Agents inherit repository `AGENTS.md` rules: read-only Snowflake by default,
  context query before data access, no browser authentication fallback.
- Production Snowflake mutation and model promotion remain out of scope for
  Cloud Agent bootstrap work.
