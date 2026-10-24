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
| `scripts/cloud_agent_bootstrap.sh` | `uv sync --locked --extra dev` then `scripts/verify.py` |

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

From a clean Linux checkout with `uv` installed:

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

### If Build fails because `uv` is missing

Document a optional `.cursor/Dockerfile` layer in a follow-up change. Level A
assumes the Cloud base image provides `uv` (same assumption as CI via
`astral-sh/setup-uv`). See Cursor [environment setup](https://cursor.com/docs/cloud-agent/setup.md).

## Level B — Optional DEV Snowflake

Story #151 adds read-only DEV Snowflake bootstrap via Dashboard **Runtime
secrets** and `scripts/bootstrap_cloud_snowflake_connection.sh`. Until that
story is merged, treat Snowflake in Cloud Agents as unsupported.

When Level B is available, see the **Level B** section in this runbook and
[Snowflake integration](../snowflake-integration.md).

## Security reminders

- Never commit credentials, PATs, API keys, or personal connection names.
- Agents inherit repository `AGENTS.md` rules: read-only Snowflake by default,
  context query before data access, no browser authentication fallback.
- Production Snowflake mutation and model promotion remain out of scope for
  Cloud Agent bootstrap work.
