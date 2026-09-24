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
them; this story does not implement ML datasets, jobs, experiments, registry,
or Feature Store.

## Execution policy

Agent work begins read-only. A write needs explicit story/task authorization,
an approved DEV target schema, and a separately verified appropriate role.
`ExecutionPolicy` records this prerequisite at an adapter call site; it is not
a SQL parser or a guarantee of query safety. No default production writes,
DROP/TRUNCATE/destructive ALTER against shared or production objects,
role/grant administration, or mutation of data-repository governed ingestion
and canonical schemas. Stop and escalate when a write or stronger access is
needed. Repeatable SQL belongs under [sql/](../sql/README.md).

## Optional live DEV proof

Normal `uv run pytest` uses fake sessions and skips the live test. A reviewer
may opt into only the read-only context query after approving a DEV connection:

```powershell
$env:ATLAS_RUN_SNOWFLAKE_DEV_TEST = '1'
$env:ATLAS_EXPECTED_SNOWFLAKE_DEV_ROLE = '<approved DEV role>'
$env:ATLAS_EXPECTED_SNOWFLAKE_DEV_DATABASE = '<approved DEV database>'
$env:ATLAS_EXPECTED_SNOWFLAKE_DEV_SCHEMA = '<approved DEV schema>'
$env:ATLAS_EXPECTED_SNOWFLAKE_DEV_WAREHOUSE = '<approved DEV warehouse>'
uv run --extra snowflake pytest -s tests/test_snowflake_dev_integration.py
```

The test reads no tables or views and mutates no objects. It prints only the
five context fields. Omit opt-in to skip safely in CI.

## Cortex Code and future ML work

Local `cortex` is available; its help lists `exec`, `connections`, `skill`,
`worktree`, and `--connection/-c`. `coco` was not found. Its authenticated
Snowflake behavior and repository skill discovery were not exercised in #40.
Use Cortex Code for approved Snowflake-native analysis/work under the same
repository rules and lifecycle contract as Codex, Cursor, and OpenCode. A CLI
presence check grants no Snowflake authorization.

Future execution extends #26's **single** run/model identity: Git revision
and resolved config → Atlas experiment/run identity → Snowflake execution,
Experiment, or Job reference → Snowflake Model Registry reference. Snowflake
ML Datasets and Feature Store references join the same run lineage only when
approved and justified. #41 owns the broader declarative cross-system
identity contract; #40 defines no second registry or promotion policy.
