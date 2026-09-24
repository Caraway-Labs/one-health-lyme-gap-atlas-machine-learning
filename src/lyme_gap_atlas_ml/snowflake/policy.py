"""Explicit operation authorization; this is not a SQL firewall."""

from dataclasses import dataclass

from .context import ContextError


@dataclass(frozen=True)
class ExecutionPolicy:
    authorized_dev_schema: str | None = None
    write_authorization: str | None = None

    def require_write(self, target_schema: str) -> None:
        if (
            not self.write_authorization
            or not self.authorized_dev_schema
            or target_schema.upper() != self.authorized_dev_schema.upper()
        ):
            raise ContextError("Write requires explicit task authorization and matching DEV schema")
