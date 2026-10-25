# Cursor Cloud Agent runbook (Atlas ML repository)

This runbook supports [Epic #149](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/149)
(Level A and Level B) and [Epic #155](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/155)
(ML agent PROD read and ML Lab write). It separates what belongs in **Git**
from what belongs in the **Cursor Dashboard**.

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
`AGENTS.md`. Level B is read-only DEV: context query before data, no browser
authentication fallback, and no writes. PROD read and ML Lab writes use the
ML agent identity below. PROD stays read-only on every path. One Cursor
environment has one value per secret name; do not point the shared
`SNOWFLAKE_*` names at a DEV user and the ML agent user at the same time.

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

## ML agent PROD read and ML Lab write

Epic [#155](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/155)
authorizes one cloud agent identity. The same rules are in
[`AGENTS.md`](../../AGENTS.md) and
[Snowflake integration](../snowflake-integration.md). This section records the
boundary. Documentation-only work does not connect to Snowflake. A live
session still needs an issue that authorizes it, a context check, and that
issue's bootstrap. Level A and Level B above do not grant this identity.

- PROD is read-only. Writes go only to the ML Lab database
  `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`, schemas `REGISTRY`, `EDA`, `FEATURES`,
  `EXPERIMENTS`, and `SCRATCH`.
- No access to `GOVERNANCE` (personal data), `RAW`, `STAGING`,
  `KNOWLEDGE_GRAPH`, or `RESTRICTED_CDC_*`.
- PROD read is limited to an allow-list of `CONFORMED`, `FEATURE_STORE`, and
  `PRESENTATION` objects granted to role `OH_LYME_PROD_ML_EDA_READ`. A new
  PROD table is invisible until explicitly granted.
- Aggregates only. No record-level extracts leave Snowflake.
- Small-cell rule: suppress `n < 11` in Lab aggregate tables, files and charts.
- Comments exception (Matthew Caraway, 2026-10-25): GitHub issue comments, PR
  bodies and `docs/eda/` write-ups MAY name counties and give county-level
  numbers, including small counts. The rules above still apply to files, git
  extracts, Drive charts and Lab aggregate tables.
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
  for rotation, the monthly credit review, and `SCRATCH` cleanup are in the
  [ML Lab operations runbook](ml-lab-operations.md). The ML agent path does
  not use password authentication.
- No network policy. The per-user authentication policy on
  `OH_LYME_ML_AGENT_SVC` sets
  `NETWORK_POLICY_EVALUATION = ENFORCED_NOT_REQUIRED`, by owner decision on
  [#157](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/157#issuecomment-6391048205).

Cursor Dashboard secret names only, never values:

| Secret name | Purpose |
| --- | --- |
| `SNOWFLAKE_PAT` | Programmatic access token. Runtime Secret. |
| `SNOWFLAKE_ACCOUNT` | Account identifier for this user. |
| `SNOWFLAKE_USER` | Service user name. |
| `SNOWFLAKE_ROLE` | Role name. |
| `SNOWFLAKE_WAREHOUSE` | Warehouse name. |
| `SNOWFLAKE_DATABASE` | ML Lab database name. |

Store values only in the Cursor Dashboard. Do not print, log, or commit them.

## EDA charts in Google Drive

Issue [#161](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/161)
stores chart bytes in Google Drive and one row per chart in
`ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.REGISTRY.ARTIFACTS`.
There is no Google service account and no Drive credential in this
repository or in Cursor secrets. The folder id is not a secret.

Shared folder: `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM` ("Atlas Lyme ML EDA
Artifacts").

Upload only charts and aggregate outputs. Never upload record-level data, row
extracts, CSV extracts, or free-text fields such as `PART_TEXT` and
`CONTEXT_LIMITATIONS`. Aggregates still follow the small-cell rule: suppress
`n < 11`. This repository does not contain Drive upload code. A future cloud
agent uploads with the Google Drive MCP `create_file` tool, then registers the
returned id and link.

1. Save the chart from the repository root with
   `lyme_gap_atlas_ml.registry.artifacts.save_chart`. That writes
   `artifacts/charts/<issue>/<name>.png` and `artifacts/charts/<issue>/index.json`.
   The index lists file names and sha256 only. `artifacts/charts/` is
   git-ignored. Do not commit the PNG, the index, or any CSV.
2. Create one Drive subfolder per issue when it does not already exist. Call
   `create_file` with `title` `issue-<number>`, `parentId`
   `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`, and `contentMimeType`
   `application/vnd.google-apps.folder`. Omit `textContent` and
   `base64Content`. Keep the returned folder `id` and reuse it for later
   charts from the same issue.
3. Upload the PNG with `create_file`:
   - `title`: the chart file name, ending in `.png`
   - `parentId`: the issue subfolder id from the previous step
   - `contentMimeType`: `image/png`
   - `base64Content`: the base64 encoding of the PNG bytes (the tool accepts
     at most 1,000,000 characters, about 750,000 bytes)
   - `disableConversionToGoogleType`: `true`, so Drive stores the PNG bytes
4. Read the returned Drive JSON. Pass its file `id` and link (`webViewLink`
   when present) to `register_artifact(run_id, issue, file_name, drive_file_id,
   drive_link, sha256)`. Pass `byte_size` when the PNG size is known, and
   `caption` only for a short aggregate description. Keep only that id and
   link. Do not commit the upload response or the chart bytes.
5. `register_artifact` reads `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
   `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, and
   `SNOWFLAKE_PAT` through the ML agent connection in
   `src/lyme_gap_atlas_ml/snowflake/ml_agent_access.py`. It opens that session,
   checks `CURRENT_ROLE()` and `CURRENT_DATABASE()`, and inserts exactly one
   row into `REGISTRY.ARTIFACTS`. The inserted columns are `ARTIFACT_ID` (a
   uuid4 string generated in code), `RUN_ID`, `KIND` (`chart`), `TITLE` (the
   file name), `CAPTION` (optional), `DRIVE_FILE_ID`, `DRIVE_URL` (the Drive
   link), `SHA256`, `MIME_TYPE` (`image/png`), `BYTES` (the file size, null
   when the size is unknown), and `CREATED_AT` (UTC, with an explicit
   `+0000` offset). A second call with the same
   run id and file name is rejected after a `SELECT` on `RUN_ID` and `TITLE`
   and does not insert another row. The issue number is not an artifact
   column; it stays on `REGISTRY.RUNS.ISSUE_NUMBER`. The role must be
   `OH_LYME_ML_AGENT` and the database must be
   `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`. Parameters are bound. The helper does
   not run DDL.

The live column list was verified on
[#163](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/163).
The provisioning DDL lives outside this repository.

## Security reminders

- Never commit credentials, PATs, API keys, secret values, or personal connection names.
- PROD is read-only. Writes go only to `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`.
- Agents inherit repository `AGENTS.md`: context query before data access, no
  browser authentication fallback, aggregates only in files and Drive (issue
  and PR comments and `docs/eda/` write-ups may name counties and give
  county-level numbers), suppress `n < 11` in Lab tables and charts, and no
  record-level extracts.
- Production Snowflake mutation and model promotion remain out of scope.
