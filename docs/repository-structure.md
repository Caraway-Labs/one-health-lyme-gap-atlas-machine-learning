# Repository structure and package boundaries

This guide describes where approved future work belongs. Directories are added when a story has working content; this story creates no placeholder packages or empty directory tree. The current executable package is `src/lyme_gap_atlas_ml`, with package import coverage in `tests/`.

| Location | Intended responsibility |
| --- | --- |
| `config/models/`, `config/experiments/`, `config/environments/` | Versioned, non-secret model, experiment, and environment settings. Record resolved configuration with each run. |
| `docs/architecture/`, `docs/adr/`, `docs/methodology/`, `docs/model-cards/`, `docs/runbooks/` | Architecture and decision records, scientific methods, model evidence, and operations. Cross-repository decisions remain governed by workspace ADRs. |
| `sql/datasets/`, `sql/features/`, `sql/validation/`, `sql/monitoring/` | Reviewed, versioned SQL for ML inputs and checks, within approved Snowflake scope. Source ingestion and canonical normalization remain in the data repository. |
| `scripts/` | Bounded developer/CI entry points that call package code; no separate business logic or embedded credentials. |
| `src/lyme_gap_atlas_ml/snowflake/`, `data/` | Snowflake transport and dataset access adapters; explicit I/O and provenance. |
| `src/lyme_gap_atlas_ml/features/`, `models/`, `evaluation/`, `experiments/` | Testable feature, model, split/evaluation, and experiment logic. Keep transport out of these modules. |
| `src/lyme_gap_atlas_ml/observability/` | Approved telemetry values, protocol, and Arize adapter. Arize calls stay behind this boundary. |
| `src/lyme_gap_atlas_ml/registry/`, `jobs/` | Future approved registry and execution adapters; add packages only when their stories require working code. |
| `tests/unit/`, `tests/integration/`, `tests/contract/` | Pure deterministic behavior; bounded external-system interactions; versioned interface and artifact contracts, respectively. |
| `.agents/skills/` | Canonical shared task procedures for agent harnesses; see [skills catalog](skills.md). |

The lifecycle state and Arize adapter are implemented under Stories #39 and #42. Model targets, training, and Snowflake jobs/registry still require their own approved stories. Keep `uv`, Ruff, mypy, and pytest as the local gates shown in the README. A real integration test must identify its environment and permissions; an offline unit test must not open a Snowflake connection.
