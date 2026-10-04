"""Bounded #65 read adapter; existing context policy, no stronger-role fallback."""

from __future__ import annotations

import hashlib
import re
from importlib import import_module
from pathlib import Path
from typing import Any

from .connector import ConnectorContextReader
from .context import ExpectedContext, check_context, connection_name_from_environment

ROOT = Path(__file__).resolve().parents[3]
EXPECTED = ExpectedContext(
    role="OH_LYME_DEV_READ",
    database="ONE_HEALTH_LYME_GAP_ATLAS_DEV",
    schema="PRESENTATION",
    warehouse="OH_LYME_DEV_INGEST_XS_WH",
    user="MATTHEWCARAWAY",
)


def open_bounded_connection() -> Any:
    """Named local configuration resolved by the optional approved connector only."""
    connector = import_module("snowflake.connector")
    return connector.connect(
        connection_name=connection_name_from_environment(),
        schema="PRESENTATION",
        session_parameters={
            "STATEMENT_TIMEOUT_IN_SECONDS": 30,
            "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS": 30,
        },
        login_timeout=30,
        network_timeout=30,
    )


def acquire(connection: Any) -> dict[str, Any]:
    """Context then release then sources then counties; stop on any failure."""
    context = check_context(ConnectorContextReader(connection), EXPECTED)
    evidence: list[dict[str, Any]] = []

    def query(name: str, maximum: int, release: str | None = None) -> list[dict[str, Any]]:
        path = ROOT / f"sql/datasets/65_{name}.sql"
        query_text = path.read_text(encoding="utf-8-sig")
        record: dict[str, Any] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "row_limit": maximum,
            "timeout_seconds": 30,
        }
        evidence.append(record)
        with connection.cursor() as cursor:
            try:
                cursor.execute(query_text, (release,) if release else None, timeout=30)
            except Exception as error:
                record.update(
                    status="ACCESS_OR_EXECUTION_BLOCKED",
                    errno=getattr(error, "errno", None),
                    sqlstate=getattr(error, "sqlstate", None),
                    query_id=getattr(error, "sfqid", None),
                )
                raise
            record.update(status="READ", query_id=cursor.sfqid)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(maximum + 1)
        if len(rows) > maximum:
            raise ValueError("query output exceeds row bound")
        record["returned_rows"] = len(rows)
        return [dict(zip(columns, row, strict=True)) for row in rows]

    base = {"context": vars(context), "queries": evidence, "statement_timeout_seconds": 30}
    try:
        release_rows = query("release_identity", 2)
        if len(release_rows) != 1:
            raise ValueError("exactly one published release required")
        release = release_rows[0]
        release_id = release.get("RELEASE_ID")
        digest = release.get("BUNDLE_SHA256")
        if not isinstance(release_id, str) or not release_id:
            raise ValueError("missing release identity")
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("missing release bundle digest")
        sources = query("source_identity", 3, release_id)
        expected_datasets = {
            "tick": "cdc-ixodes-county-status-2025",
            "pathogen": "cdc-ixodes-pathogen-status-2025",
        }
        if len(sources) != 2 or {row.get("SOURCE_KEY") for row in sources} != {"tick", "pathogen"}:
            raise ValueError("distinct tick and pathogen source identities required")
        for source in sources:
            key = str(source["SOURCE_KEY"])
            if (
                source.get("RELEASE_VERSION") != release_id
                or source.get("DATASET_ID") != expected_datasets[key]
                or source.get("SOURCE_ID") != "cdc_arbonet_tick_module"
                or source.get("VINTAGE") != "through 2025-12-31"
            ):
                raise ValueError("source identity or cumulative period mismatch")
        rows = query("county_evidence", 3145, release_id)
        return base | {
            "status": "ACQUIRED",
            "release": release,
            "sources": sources,
            "counties": rows,
        }
    except Exception as error:
        # Never serialize connector messages, connection configuration or credentials.
        return base | {
            "status": "BLOCKED",
            "scientific_estimability": "UNASSESSED",
            "error_type": type(error).__name__,
            "counts": None,
        }
