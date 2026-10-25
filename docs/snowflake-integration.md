# Snowflake integration foundation (Story #40)

The ML repository owns the Python context adapter in
`src/lyme_gap_atlas_ml/snowflake/`. It owns no governed ingestion or canonical
schema. The browser reaches Snowflake only through the Python REST API.

## Local connection and context

Set `SNOWFLAKE_CONNECTION_NAME` in the local environment to an already
configured, least-privilege named PAT connection. The name is a local selector,
not a repository constant. For routine DEV inspection, use the role mapping in
the [data connection inventory](../../one-health-lyme-gap-atlas-data/docs/operations/connection-inventory.md).
Do not commit the selector, credential, token, or local connection file. No
connection is required for docs or ordinary unit tests.

The installed Snowflake CLI 3.24.1 supports `snow sql --query/-q` and
`--connection/-c`. After selecting the approved local connection, use:

```powershell
snow sql -c $env:SNOWFLAKE_CONNECTION_NAME -q 'SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE()'
```

Compare every field with the authorized user (when specified), DEV role,
database, schema, and warehouse before proceeding. A missing or unexpected
field blocks work. Report these non-secret context fields, never the connection
selector or credential. `snow` is also the CLI for approved SQL and object or
deployment operations; the command above authorizes no later write.

Python code can install `uv sync --extra dev --extra snowflake`. The optional
group installs only `snowflake-connector-python`, used to open the named local
connection. `ConnectorContextReader` executes only the context query;
`check_context` validates it against explicit expected values. The reader and
validation are independently replaceable with fakes. Connection construction
stays out of ML feature, experiment, and evaluation logic. Snowpark and
`snowflake-ml-python` are deferred until executable Snowflake ML work requires
them; this story adds only the bounded dataset read below, not jobs, experiments,
registry, or Feature Store.

## Execution policy

Agent work begins read-only. PROD is read-only on every path. A write needs
explicit story authorization and a verified role whose target is an approved
DEV schema or the ML Lab schemas in the next section.
`ExecutionPolicy` records this prerequisite at an adapter call site; it is not
a SQL parser or a guarantee of query safety. No default production writes,
DROP/TRUNCATE/destructive ALTER against shared or production objects,
role/grant administration, or mutation of data-repository governed ingestion
and canonical schemas. Stop and escalate when a write or stronger access is
needed. Repeatable SQL belongs under [sql/](../sql/README.md).

## PROD read and ML Lab write

Epic [#155](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/155)
authorizes one cloud agent identity. The same rules are in
[`AGENTS.md`](../AGENTS.md) and the
[cursor-cloud-agent runbook](runbooks/cursor-cloud-agent.md). Local DEV
inspection still uses a named connection selected by `SNOWFLAKE_CONNECTION_NAME`.
That selector is local, is not committed, and is not one of the Dashboard
secret names below. Documentation-only work does not connect to Snowflake.

- PROD is read-only. Writes go only to the ML Lab database
  `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`, schemas `REGISTRY`, `EDA`, `FEATURES`,
  `EXPERIMENTS`, and `SCRATCH`.
- No access to `GOVERNANCE` (personal data), `RAW`, `STAGING`,
  `KNOWLEDGE_GRAPH`, or `RESTRICTED_CDC_*`.
- PROD read is limited to an allow-list of `CONFORMED`, `FEATURE_STORE`, and
  `PRESENTATION` objects granted to role `OH_LYME_PROD_ML_EDA_READ`. A new
  PROD table is invisible until explicitly granted.
- Aggregates only. No record-level extracts leave Snowflake. The fixed DEV
  smoke later in this guide stays inside the session and must not print or
  export row values.
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
  `OH_LYME_ML_AGENT`, with a 30 day life (rotate before expiry).
- No network policy. The per-user authentication policy on
  `OH_LYME_ML_AGENT_SVC` sets
  `NETWORK_POLICY_EVALUATION = ENFORCED_NOT_REQUIRED`, by owner decision on
  [#157](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/157#issuecomment-6391048205).

Cursor Dashboard secret names only, never values: `SNOWFLAKE_PAT` (Runtime
Secret), `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`,
`SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`.

## One governed DEV dataset path

`read_dev_county_sample(connection, expected)` reuses the existing context
check and connector. It requires `OH_LYME_DEV_READ` and
`ONE_HEALTH_LYME_GAP_ATLAS_DEV`; mismatches block the dataset query.
The fixed [sample SQL](../sql/datasets/dev_county_sample.sql) reads only
`PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V`, county `01001`, in stable order,
with `LIMIT 10`. It preserves values, missingness/status literals, period,
release/schema, source/retrieval, method, and limitation fields without filling
unknowns. This smoke helper runs from a repository checkout; no packaged runtime
or new query framework is introduced.

[Data #513](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/513)
and its [current-county contract](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-release/current-county-observations-v1.md)
own the approved view and read grant. It exposes only human status and the
2023 case/incidence floors from the current published release. It has one
annual period, not a historical time series. Missing counts remain unknown,
not zero; the view is not approval of a prediction target, label, experiment,
or public-health interpretation. Do not read internal semantic/raw tables.

Offline fake-session tests cover context-before-data, context mismatch,
unsafe role/database rejection, row bounds, and unmodified source states.
Run `uv run python scripts/verify.py`; no Snowflake dependency or access is
needed. Dataset acquisition, lineage, splits, and scientifically justified
experiments remain with the active model/data contracts.

## Optional live DEV proof

Normal `uv run pytest` uses fake sessions and skips the live test. A reviewer
may opt into the context query and fixed DEV sample above using an approved local
connection and expected context. The smoke test passes the approved schema
as a session-only connector option; it never edits local connection files:

```powershell
$env:ATLAS_RUN_SNOWFLAKE_DEV_TEST = '1'
$env:ATLAS_EXPECTED_SNOWFLAKE_DEV_ROLE = '<approved DEV role>'
$env:ATLAS_EXPECTED_SNOWFLAKE_DEV_DATABASE = '<approved DEV database>'
$env:ATLAS_EXPECTED_SNOWFLAKE_DEV_SCHEMA = '<approved DEV schema>'
$env:ATLAS_EXPECTED_SNOWFLAKE_DEV_WAREHOUSE = '<approved DEV warehouse>'
uv run python scripts/verify.py --integration snowflake
```

The test surfaces the five non-secret context fields before the dataset read;
then reports only row count and governed release ID. It writes no object,
exports no telemetry, and does not print row values or credentials. Missing
configuration blocks live proof; never substitute a stronger connection or
interactive authentication. Mandatory offline CI excludes live tests and clears
their opt-in flags. A skipped live test does not satisfy the live-proof criterion.

Cortex/CoCo, Snowflake ML Jobs, Experiments, Registry and Feature Store are
explicitly deferred. No separate experiment identity or registry is created;
#26/#41 remain their owners when a current model needs those surfaces.

## Recorded DEV proof (2026-10-01)

The opt-in Python proof passed: **2 tests passed**, fixed sample **3 rows**,
release `governed-2026-09-17-unknown-coverage`. Context was user
`MATTHEWCARAWAY`, role `OH_LYME_DEV_READ`, database
`ONE_HEALTH_LYME_GAP_ATLAS_DEV`, schema `PRESENTATION`, warehouse
`OH_LYME_DEV_INGEST_XS_WH`. The existing PAT connection had no default schema;
the connector selected `PRESENTATION` for this session only.
The CLI context check independently matched these five fields before the test.
The only dataset object read was
`ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V`.
No object write, grant, credential creation, persistent configuration change,
training, telemetry export, or deployment occurred. Raw sample values were not
printed. This is live DEV access evidence, not scientific review or target approval.
