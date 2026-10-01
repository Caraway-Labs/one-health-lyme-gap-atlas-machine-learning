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

Agent work begins read-only. A write needs explicit story/task authorization,
an approved DEV target schema, and a separately verified appropriate role.
`ExecutionPolicy` records this prerequisite at an adapter call site; it is not
a SQL parser or a guarantee of query safety. No default production writes,
DROP/TRUNCATE/destructive ALTER against shared or production objects,
role/grant administration, or mutation of data-repository governed ingestion
and canonical schemas. Stop and escalate when a write or stronger access is
needed. Repeatable SQL belongs under [sql/](../sql/README.md).

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
connection and expected context:

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
