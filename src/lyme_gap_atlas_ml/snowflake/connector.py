"""Optional Python connector adapter; connection construction stays at this boundary."""

from collections.abc import Mapping, Sequence
from importlib import import_module
from pathlib import Path
from typing import Any

from .context import CONTEXT_SQL, ContextError, ExpectedContext, check_context


class ConnectorContextReader:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def fetch_context_row(self) -> Mapping[str, object] | Sequence[object]:
        with self._connection.cursor() as cursor:
            cursor.execute(CONTEXT_SQL)
            row: Sequence[object] | None = cursor.fetchone()
        if row is None:
            return ()
        return row


def open_local_connection(connection_name: str) -> Any:
    """Open an already configured local connection; callers must close it."""
    try:
        connector = import_module("snowflake.connector")
    except ImportError as error:
        raise RuntimeError("Install the optional snowflake dependency group") from error
    return connector.connect(connection_name=connection_name)


def read_dev_county_sample(connection: Any, expected: ExpectedContext) -> list[tuple[object, ...]]:
    """Read the fixed governed DEV smoke sample from a repository checkout."""
    if (
        expected.role.upper() != "OH_LYME_DEV_READ"
        or expected.database.upper() != "ONE_HEALTH_LYME_GAP_ATLAS_DEV"
    ):
        raise ContextError("Dataset smoke proof requires the approved DEV read context")
    check_context(ConnectorContextReader(connection), expected)
    query = (Path(__file__).resolve().parents[3] / "sql/datasets/dev_county_sample.sql").read_text(
        encoding="utf-8-sig"
    )
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = [tuple(row) for row in cursor.fetchall()]
    if len(rows) > 10:
        raise ContextError("Dataset smoke query exceeded its fixed row bound")
    return rows
