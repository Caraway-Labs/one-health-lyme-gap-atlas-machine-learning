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

The first `register_artifact` call did not insert a row. Snowflake returned `000904 (42000): SQL compilation error: invalid identifier 'ISSUE'`. The live table columns are `ARTIFACT_ID`, `RUN_ID`, `KIND`, `TITLE`, `CAPTION`, `DRIVE_FILE_ID`, `DRIVE_URL`, `SHA256`, `MIME_TYPE`, `BYTES`, and `CREATED_AT`. There is no `ISSUE`, `FILE_NAME`, or `DRIVE_LINK` column. No DDL was run.

The helper now inserts those live columns. A later call, still as `OH_LYME_ML_AGENT` on `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`, registered this chart. Context immediately before that insert:

```text
user: OH_LYME_ML_AGENT_SVC
role: OH_LYME_ML_AGENT
database: ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB
schema: SCRATCH
warehouse: OH_LYME_ML_LAB_XS_WH
```

The PNG was not on this machine, and this follow-up did not read Google Drive. `BYTES` is null because the file size was not available here.

`SELECT` of `REGISTRY.ARTIFACTS` for this run id and title returned one row:

| Column | Value |
| --- | --- |
| `ARTIFACT_ID` | `3844029d-2cac-4e66-853b-56b085233eef` |
| `RUN_ID` | `163-situation-classes-20261025T0120Z` |
| `KIND` | `chart` |
| `TITLE` | `surveillance-situation-class-counts.png` |
| `CAPTION` | null |
| `DRIVE_FILE_ID` | `1JCM9Uoci1j6msOeEl7ikyV0YTTDr3QKe` |
| `DRIVE_URL` | `https://drive.google.com/file/d/1JCM9Uoci1j6msOeEl7ikyV0YTTDr3QKe/view?usp=drivesdk` |
| `SHA256` | `74a4174e78028869d7ceeb94744ddb79161becd75ab752ea6d6a2c86a39800d3` |
| `MIME_TYPE` | `image/png` |
| `BYTES` | null |
| `CREATED_AT` | `2026-10-25 01:55:24-07:00` |

That `CREATED_AT` is the session rendering of the value the helper sent as a naive clock `2026-10-25 01:55:24`. Session `TIMEZONE` was `America/Los_Angeles`, so Snowflake stored that wall time as Pacific local. `CONVERT_TIMEZONE('UTC', CREATED_AT)` for this row is `2026-10-25 08:55:24+00:00`. `CURRENT_TIMESTAMP()` just after the insert was `2026-10-25 01:56:30+00:00`. The helper in this follow-up now binds `CREATED_AT` with an explicit `+0000` offset. This already written row was not updated.

## Decision

The class counts stand, and the chart row is registered in `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.REGISTRY.ARTIFACTS` as selected above. `BYTES` is null. Owner confirmation of smoke test #163 remains open. This follow-up did not run DDL, did not change PROD grants, and did not promote a model.

## Reproduction and retained evidence

- Run id: `163-situation-classes-20261025T0120Z`
- Git commit recorded on the run: `1a0b7fa7724355a97c420d9afd7f2e11962f0c4a`
- Registration helper revision that performed the insert: `d611e71ba7a679bbcd12c4661b7cac3d551939f4` (naive `CREATED_AT` clock). The explicit `+0000` offset is `4ce0af3301aea3b7c94a1575d67e3ded44f047f7`. The inserted row was not rewritten.
- Branch for the original smoke test: `cursor/live-eda-smoke-163-4ab5`
- Objects read: `ONE_HEALTH_LYME_GAP_ATLAS_PROD.FEATURE_STORE.COUNTY_SURVEILLANCE_SITUATIONS` (aggregate only); information-schema column lists for that table and for `ML_LAB.REGISTRY.RUNS`, `ML_LAB.EDA.METRICS_LONG`, and `ML_LAB.REGISTRY.ARTIFACTS`. The registration follow-up read session context, the inserted artifact row, and `CONVERT_TIMEZONE('UTC', CREATED_AT)`.
- Objects written: one row in `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.REGISTRY.RUNS`; eight rows in `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.METRICS_LONG`; one row in `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.REGISTRY.ARTIFACTS` (`ARTIFACT_ID` `3844029d-2cac-4e66-853b-56b085233eef`)
- Objects not written: no PROD writes. The artifact row was not updated after insert.
- Commands: `uv sync --locked --extra dev --extra snowflake`, then `uv run python scripts/check_ml_agent_context.py`, then `uv run python scripts/verify.py`. The registration follow-up repeated `uv run python scripts/verify.py` and called `register_artifact` for run `163-situation-classes-20261025T0120Z`.
- Transient outputs left uncommitted: `artifacts/charts/163/surveillance-situation-class-counts.png`, `artifacts/charts/163/index.json`, and the local aggregate JSON under `/tmp`. The chart bytes live in the Drive file above. This follow-up did not have the PNG locally and did not download it.
