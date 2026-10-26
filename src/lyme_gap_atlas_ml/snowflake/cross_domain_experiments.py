"""Insert issue 114 PCA experiment rows. Insert-only, and no new table.

This role cannot DELETE. A run id that already has experiment rows is refused.
No GRANT is issued: the fit uses existing EXPERIMENTS tables.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import cast

from lyme_gap_atlas_ml.cross_domain import EXPERIMENT_METRICS, ExperimentSpec
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError

_EXPERIMENT_INSERT = f"""
INSERT INTO {ML_LAB_DATABASE}.EXPERIMENTS.EXPERIMENTS (
    EXPERIMENT_ID, RUN_ID, HYPOTHESIS, MODEL_FAMILY, CONFIG, SPLIT_DEFINITION, STATUS
)
SELECT %s, %s, %s, %s, PARSE_JSON(%s), PARSE_JSON(%s), %s
""".strip()
_METRIC_INSERT = f"""
INSERT INTO {ML_LAB_DATABASE}.EXPERIMENTS.MODEL_METRICS (
    EXPERIMENT_ID, RUN_ID, SPLIT_NAME, METRIC_NAME, METRIC_VALUE, CI_LOW, CI_HIGH, N
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""".strip()
_EXPERIMENT_COUNT = (
    f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EXPERIMENTS.EXPERIMENTS WHERE RUN_ID = %s"
)


class RunAlreadyWritten(EdaWriteError):
    """This run id already has experiment rows."""


def write_pca_experiments(
    executor: EdaSession,
    run_id: str,
    experiments: Sequence[ExperimentSpec],
) -> int:
    """Insert PCA experiment and metric rows. Refuse a second write for the run."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    if _count(executor, run_id) > 0:
        raise RunAlreadyWritten("run id already has experiment rows")
    written = 0
    try:
        for experiment in experiments:
            executor.execute(
                _EXPERIMENT_INSERT,
                (
                    experiment.experiment_id,
                    run_id,
                    experiment.hypothesis,
                    experiment.model_family,
                    _json(experiment.config),
                    _json(experiment.split_definition),
                    experiment.status,
                ),
            )
            written += 1
            for metric in experiment.metrics:
                if metric.metric_value is None or metric.n is None or metric.n < 11:
                    continue
                executor.execute(
                    _METRIC_INSERT,
                    (
                        experiment.experiment_id,
                        run_id,
                        metric.split_name,
                        metric.metric_name,
                        metric.metric_value,
                        metric.ci_low,
                        metric.ci_high,
                        metric.n,
                    ),
                )
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return written


def _count(executor: EdaSession, run_id: str) -> int:
    query = getattr(executor, "query", None)
    if not callable(query):
        raise EdaWriteError("session cannot query")
    try:
        rows = query(_EXPERIMENT_COUNT, (run_id,))
    except TypeError:
        raise EdaWriteError("session cannot bind parameters") from None
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    if len(rows) != 1 or isinstance(rows[0], (str, bytes)) or len(rows[0]) != 1:
        raise EdaWriteError("experiment count is not usable")
    value = rows[0][0]
    if isinstance(value, bool) or not isinstance(value, int):
        raise EdaWriteError("experiment count is not usable")
    return cast(int, value)


def _json(payload: object) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if "GRANT" in text.upper():
        raise EdaWriteError("experiment payload is not a grant")
    return text


def experiment_metric_names() -> tuple[str, ...]:
    """Names the PCA writer is allowed to store. Tests pin this list."""
    return EXPERIMENT_METRICS
