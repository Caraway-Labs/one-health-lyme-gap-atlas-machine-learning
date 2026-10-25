# 163: How many counties sit in each surveillance situation class?

- Issue: [ML #163](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/163), part of [ML #155](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/155). Question: in the live feature-store batch, how many county rows fall in each surveillance situation class? This is a live smoke test of PROD read, ML Lab metric write, and Drive chart upload. A class is a stored surveillance-situation assignment from that batch.
- Spec: [analysis specification v1](../methodology/analysis-spec-v1.md). Estimand: the count of county rows in each `MODEL_ID` and `CLASS_ID`. Exploratory description. One prespecified aggregation. Small-cell rule applied before the write (`n < 11` removes both the count and the metric value).
- Data: `ONE_HEALTH_LYME_GAP_ATLAS_PROD.FEATURE_STORE.COUNTY_SURVEILLANCE_SITUATIONS`. Every row carries batch `surveillance-situation-batch`, batch version `v1`, and model version `v1`. Source release recorded on the run: `surveillance-situation-batch-v1`. That batch identity is the version on the table.
- Cohort: all rows in that table. 6,288 rows, 3,144 per model. Geography is the national county assignment. The query time recorded as `INPUT_SNAPSHOT_TS` is 2026-10-25 01:19:59 UTC.

## Method and assumptions

Context check before any data query, from `uv run python scripts/check_ml_agent_context.py`:

```text
role: OH_LYME_ML_AGENT
warehouse: OH_LYME_ML_LAB_XS_WH
database: ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB
prod_select: pass
scratch_write: pass
prod_write_denied: pass
```

The session role is `OH_LYME_ML_AGENT`. PROD stayed read-only. The only PROD object read for the result is the feature-store table above. Columns used for the aggregate are `BATCH_ID`, `BATCH_VERSION`, `MODEL_ID`, `MODEL_VERSION`, and `CLASS_ID`. County FIPS, state, population, and class probabilities stayed in Snowflake.

```sql
SELECT MODEL_ID, MODEL_VERSION, CLASS_ID, COUNT(*) AS N
FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.FEATURE_STORE.COUNTY_SURVEILLANCE_SITUATIONS
GROUP BY MODEL_ID, MODEL_VERSION, CLASS_ID
```

`write_eda_results` inserted one run and one metric row per class. Metric name `class_county_count`, unit `counties`, geography type `national`. Dimensions are `model_id`, `model_version`, and `class_id`. Display names below are the v1 contract names for those class ids in `config/models/138-surveillance-situation-models-v1.json`. The live table stores the class id.

The chart is `artifacts/charts/163/surveillance-situation-class-counts.png`, written with `lyme_gap_atlas_ml.registry.artifacts.save_chart`. That directory is gitignored. The PNG is an aggregate bar chart of the same eight counts.

## Material findings and limits

Eight class cells. Every count is at least 35, so the small-cell rule suppressed 0 cells. Metric rows written: 8. Suppressed metric rows: 0.

### Four-state model (`surveillance-situation-four-state`, v1)

| Class id | Contract name | Counties |
| --- | --- | ---: |
| `surveillance-situation-four-state.v1.class-0` | Established blacklegged tick | 801 |
| `surveillance-situation-four-state.v1.class-1` | Unknown tick and pathogen status | 35 |
| `surveillance-situation-four-state.v1.class-2` | Western blacklegged tick recorded | 112 |
| `surveillance-situation-four-state.v1.class-3` | Pathogen not recorded | 2,196 |

### Tick and pathogen model (`surveillance-situation-tick-pathogen`, v1)

| Class id | Contract name | Counties |
| --- | --- | ---: |
| `surveillance-situation-tick-pathogen.v1.class-0` | Established blacklegged tick | 1,325 |
| `surveillance-situation-tick-pathogen.v1.class-1` | Blacklegged tick not established, pathogen not recorded | 1,687 |
| `surveillance-situation-tick-pathogen.v1.class-2` | Western blacklegged tick established | 97 |
| `surveillance-situation-tick-pathogen.v1.class-3` | Unknown tick and pathogen status | 35 |

Each model sums to 3,144 counties. The two models are separate fits. Each class id includes its model id.

Run id `163-situation-classes-20261025T0120Z` in `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.REGISTRY.RUNS` (`ISSUE_NUMBER` 163, `STATUS` `succeeded`). Eight rows in `EDA.METRICS_LONG` for that run, `IS_SUPPRESSED` false on all eight, `N_UNDERLYING` equal to the counts above.

### Chart and artifact registration

Drive folder `issue-163` (`1s4xTsqmGxzf93Xxv7HnZhNbji8sCf9yX`) inside shared folder `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`.

Chart: [surveillance-situation-class-counts.png](https://drive.google.com/file/d/1JCM9Uoci1j6msOeEl7ikyV0YTTDr3QKe/view?usp=drivesdk)

- Drive file id: `1JCM9Uoci1j6msOeEl7ikyV0YTTDr3QKe`
- SHA-256: `74a4174e78028869d7ceeb94744ddb79161becd75ab752ea6d6a2c86a39800d3`

`register_artifact` did not insert a row. `REGISTRY.ARTIFACTS` has 0 rows for this run id. The helper insert lists `RUN_ID`, `ISSUE`, `FILE_NAME`, `DRIVE_FILE_ID`, `DRIVE_LINK`, `SHA256`, `CREATED_AT`. Snowflake returned `000904 (42000): SQL compilation error: invalid identifier 'ISSUE'`.

Live `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.REGISTRY.ARTIFACTS` columns:

| Column | Type | Nullable | Default |
| --- | --- | --- | --- |
| `ARTIFACT_ID` | TEXT | NO | none |
| `RUN_ID` | TEXT | NO | none |
| `KIND` | TEXT | YES | none |
| `TITLE` | TEXT | YES | none |
| `CAPTION` | TEXT | YES | none |
| `DRIVE_FILE_ID` | TEXT | YES | none |
| `DRIVE_URL` | TEXT | YES | none |
| `SHA256` | TEXT | YES | none |
| `MIME_TYPE` | TEXT | YES | none |
| `BYTES` | NUMBER | YES | none |
| `CREATED_AT` | TIMESTAMP_LTZ | YES | `CURRENT_TIMESTAMP()` |

Columns the helper sends that are absent on the table: `ISSUE`, `FILE_NAME`, `DRIVE_LINK`. Columns on the table that the helper does not send: `ARTIFACT_ID` (required, no default), `KIND`, `TITLE`, `CAPTION`, `DRIVE_URL`, `MIME_TYPE`, `BYTES`. Shared names: `RUN_ID`, `DRIVE_FILE_ID`, `SHA256`, `CREATED_AT`. No DDL was run. The ML Lab tables were left as provisioned.

## Decision

FOLLOW_UP. The class counts are stored and the chart is in Drive. Registration of that chart waits on aligning `register_artifact` with the live `REGISTRY.ARTIFACTS` columns. The owner makes that alignment. This smoke test leaves ML Lab DDL, PROD grants, and model promotion untouched.

## Reproduction and retained evidence

- Run id: `163-situation-classes-20261025T0120Z`
- Git commit recorded on the run: `1a0b7fa7724355a97c420d9afd7f2e11962f0c4a`
- Branch: `cursor/live-eda-smoke-163-4ab5`
- Objects read: `ONE_HEALTH_LYME_GAP_ATLAS_PROD.FEATURE_STORE.COUNTY_SURVEILLANCE_SITUATIONS` (aggregate only); information-schema column lists for that table and for `ML_LAB.REGISTRY.RUNS`, `ML_LAB.EDA.METRICS_LONG`, and `ML_LAB.REGISTRY.ARTIFACTS`
- Objects written: one row in `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.REGISTRY.RUNS`; eight rows in `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.METRICS_LONG`
- Objects not written: `REGISTRY.ARTIFACTS` (insert rejected). PROD writes remain denied.
- Commands: `uv sync --locked --extra dev --extra snowflake`, then `uv run python scripts/check_ml_agent_context.py`, then `uv run python scripts/verify.py`
- Transient outputs left uncommitted: `artifacts/charts/163/surveillance-situation-class-counts.png`, `artifacts/charts/163/index.json`, and the local aggregate JSON under `/tmp`. The chart bytes live in the Drive file above.
