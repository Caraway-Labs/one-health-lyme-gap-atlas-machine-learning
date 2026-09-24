"""Optional Python connector adapter; connection construction stays at this boundary."""

from collections.abc import Mapping, Sequence
from importlib import import_module
from typing import Any

from .context import CONTEXT_SQL


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
