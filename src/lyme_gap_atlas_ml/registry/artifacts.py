"""Register one Drive chart in the ML Lab artifact table.

The live ``ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.REGISTRY.ARTIFACTS`` columns are
``ARTIFACT_ID``, ``RUN_ID``, ``KIND``, ``TITLE``, ``CAPTION``, ``DRIVE_FILE_ID``,
``DRIVE_URL``, ``SHA256``, ``MIME_TYPE``, ``BYTES``, and ``CREATED_AT``.
``ARTIFACT_ID`` is generated here because the column has no default. The issue
number stays on ``REGISTRY.RUNS.ISSUE_NUMBER``; this table has no issue column.
The admin DDL is not in this repository.

The Google Drive upload is not in this package. A cloud agent uploads with the
Drive MCP ``create_file`` tool, then passes the returned id and link here.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    IDENTITY_SQL,
    ML_AGENT_ROLE,
    REFUSED_INCOMPLETE,
    REFUSED_ROLE,
    CursorStatementExecutor,
    MlAgentConnectionSettings,
    StatementError,
    load_ml_agent_request,
    open_ml_agent_connection,
)

ML_LAB_DATABASE = "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB"
ARTIFACTS_RELATION = f"{ML_LAB_DATABASE}.REGISTRY.ARTIFACTS"
DRIVE_SHARED_FOLDER_ID = "1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM"
# create_file base64Content is capped at 1_000_000 characters (750_000 bytes).
MAX_CHART_BYTES = 750_000
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CHARTS_ROOT = REPO_ROOT / "artifacts" / "charts"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_ISSUE = re.compile(r"[1-9][0-9]{0,5}")
_PNG_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.png")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_DRIVE_FILE_ID = re.compile(r"[A-Za-z0-9_-]{10,128}")
_ARTIFACT_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_DRIVE_HOSTS = frozenset({"drive.google.com", "docs.google.com"})
CHART_KIND = "chart"
CHART_MIME_TYPE = "image/png"
_MAX_CAPTION_CHARS = 2000
DUPLICATE_SQL = f"SELECT RUN_ID, TITLE FROM {ARTIFACTS_RELATION} WHERE RUN_ID = %s AND TITLE = %s"
INSERT_SQL = (
    f"INSERT INTO {ARTIFACTS_RELATION} ("
    "ARTIFACT_ID, RUN_ID, KIND, TITLE, CAPTION, DRIVE_FILE_ID, DRIVE_URL, "
    "SHA256, MIME_TYPE, BYTES, CREATED_AT"
    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


class ArtifactRegistrationError(Exception):
    """Registration did not insert a row."""


class DuplicateArtifactError(ArtifactRegistrationError):
    """This run id and file name already have a registry row."""


class ChartSaveError(ValueError):
    """The chart file was not written."""


@dataclass(frozen=True)
class ArtifactRegistration:
    artifact_id: str
    run_id: str
    issue: str
    file_name: str
    drive_file_id: str
    drive_link: str
    sha256: str
    created_at: str
    kind: str
    caption: str | None
    mime_type: str
    byte_size: int | None


@dataclass(frozen=True)
class SavedChart:
    issue: str
    file_name: str
    path: Path
    sha256: str


def register_artifact(
    run_id: str,
    issue: str | int,
    file_name: str,
    drive_file_id: str,
    drive_link: str,
    sha256: str,
    *,
    caption: str | None = None,
    byte_size: int | None = None,
    connection: object | None = None,
    environ: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ArtifactRegistration:
    """Insert one artifact row. Reject a duplicate run id and file name.

    ``issue`` is validated and returned. It is not inserted: ``REGISTRY.ARTIFACTS``
    has no issue column. ``file_name`` is stored as ``TITLE``. ``drive_link`` is
    stored as ``DRIVE_URL``. ``byte_size`` is stored as ``BYTES`` and may be null
    when the file size is unknown.
    """
    settings = _ml_lab_settings(os.environ if environ is None else environ)
    registration = _registration(
        run_id,
        issue,
        file_name,
        drive_file_id,
        drive_link,
        sha256,
        _created_at(clock),
        caption,
        byte_size,
        str(uuid4()),
    )
    opened = connection is None
    session = open_ml_agent_connection(settings) if opened else connection
    try:
        executor = CursorStatementExecutor(session)
        try:
            _require_session(executor)
            existing = executor.query(DUPLICATE_SQL, (registration.run_id, registration.file_name))
            if existing:
                raise DuplicateArtifactError(
                    "artifact already registered for this run id and file name"
                )
            executor.query(INSERT_SQL, _insert_params(registration))
        except StatementError as error:
            raise ArtifactRegistrationError("artifact registration statement failed") from error
    finally:
        if opened:
            _close(session)
    return registration


def save_chart(
    issue: str | int,
    name: str,
    content: bytes,
    *,
    root: Path | None = None,
) -> SavedChart:
    """Write ``artifacts/charts/<issue>/<name>.png`` and update ``index.json``."""
    try:
        issue_text = _issue(issue)
    except ArtifactRegistrationError as error:
        raise ChartSaveError("issue must be a GitHub issue number") from error
    file_name = _chart_file_name(name)
    if not content.startswith(_PNG_MAGIC):
        raise ChartSaveError("chart content must be a PNG")
    if len(content) > MAX_CHART_BYTES:
        raise ChartSaveError("chart exceeds the Drive upload size limit")
    chart_root = (DEFAULT_CHARTS_ROOT if root is None else root).resolve()
    issue_dir = (chart_root / issue_text).resolve()
    if not issue_dir.is_relative_to(chart_root):
        raise ChartSaveError("chart path must stay under artifacts/charts")
    destination = (issue_dir / file_name).resolve()
    if destination.parent != issue_dir:
        raise ChartSaveError("chart file name must be a single PNG file name")
    digest = hashlib.sha256(content).hexdigest()
    entries = _load_index(issue_dir / "index.json")
    entries = [entry for entry in entries if entry["file_name"] != file_name]
    entries.append({"file_name": file_name, "sha256": digest})
    issue_dir.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    _write_index(issue_dir / "index.json", entries)
    return SavedChart(issue=issue_text, file_name=file_name, path=destination, sha256=digest)


def _ml_lab_settings(environ: Mapping[str, str]) -> MlAgentConnectionSettings:
    settings, _config = load_ml_agent_request(environ)
    if settings.role.upper() != ML_AGENT_ROLE:
        raise ArtifactRegistrationError(REFUSED_ROLE)
    if settings.database != ML_LAB_DATABASE:
        raise ArtifactRegistrationError("artifact registry writes require the ML Lab database")
    return settings


def _require_session(executor: CursorStatementExecutor) -> None:
    try:
        rows = executor.query(IDENTITY_SQL)
    except StatementError as error:
        raise ArtifactRegistrationError(REFUSED_INCOMPLETE) from error
    if len(rows) != 1:
        raise ArtifactRegistrationError(REFUSED_INCOMPLETE)
    role, _warehouse, database = _identity(rows[0])
    if role.upper() != ML_AGENT_ROLE:
        raise ArtifactRegistrationError(REFUSED_ROLE)
    if database != ML_LAB_DATABASE:
        raise ArtifactRegistrationError("artifact registry writes require the ML Lab database")


def _identity(row: Sequence[object]) -> tuple[str, str, str]:
    if isinstance(row, (str, bytes)) or len(row) != 3:
        raise ArtifactRegistrationError(REFUSED_INCOMPLETE)
    values: list[str] = []
    for value in row:
        if not isinstance(value, str) or not value.strip():
            raise ArtifactRegistrationError(REFUSED_INCOMPLETE)
        values.append(value.strip())
    return values[0], values[1], values[2]


def _registration(
    run_id: str,
    issue: str | int,
    file_name: str,
    drive_file_id: str,
    drive_link: str,
    sha256: str,
    created_at: str,
    caption: str | None,
    byte_size: int | None,
    artifact_id: str,
) -> ArtifactRegistration:
    file_id = _drive_file_id(drive_file_id)
    return ArtifactRegistration(
        artifact_id=_match(artifact_id, _ARTIFACT_ID, "artifact id"),
        run_id=_match(run_id, _RUN_ID, "run id"),
        issue=_issue(issue),
        file_name=_png_file_name(file_name),
        drive_file_id=file_id,
        drive_link=_drive_link(drive_link, file_id),
        sha256=_match(sha256, _SHA256, "sha256"),
        created_at=created_at,
        kind=CHART_KIND,
        caption=_caption(caption),
        mime_type=CHART_MIME_TYPE,
        byte_size=_byte_size(byte_size),
    )


def _issue(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ArtifactRegistrationError("issue must be a GitHub issue number")
    return _match(str(value), _ISSUE, "issue")


def _match(value: str, pattern: re.Pattern[str], label: str) -> str:
    if pattern.fullmatch(value) is None:
        raise ArtifactRegistrationError(f"invalid {label}")
    return value


def _drive_file_id(value: str) -> str:
    if _DRIVE_FILE_ID.fullmatch(value) is None:
        raise ArtifactRegistrationError("invalid drive file id")
    return value


def _drive_link(value: str, drive_file_id: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc not in _DRIVE_HOSTS
        or parsed.username
        or parsed.password
        or not parsed.path.startswith("/")
        or len(value) > 500
        or drive_file_id not in value
    ):
        raise ArtifactRegistrationError("drive link must be an https Google Drive link")
    return value


def _created_at(clock: Callable[[], datetime] | None) -> str:
    moment = datetime.now(UTC) if clock is None else clock()
    if moment.tzinfo is None:
        raise ArtifactRegistrationError("created at requires a timezone")
    # The offset keeps TIMESTAMP_LTZ from reading the clock in the session time zone.
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S +0000")


def _caption(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ArtifactRegistrationError("invalid caption")
    text = value.strip()
    if not text:
        return None
    if len(text) > _MAX_CAPTION_CHARS or "\x00" in text:
        raise ArtifactRegistrationError("invalid caption")
    return text


def _byte_size(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ArtifactRegistrationError("invalid byte size")
    return value


def _insert_params(
    registration: ArtifactRegistration,
) -> tuple[str, str, str, str, str | None, str, str, str, str, int | None, str]:
    return (
        registration.artifact_id,
        registration.run_id,
        registration.kind,
        registration.file_name,
        registration.caption,
        registration.drive_file_id,
        registration.drive_link,
        registration.sha256,
        registration.mime_type,
        registration.byte_size,
        registration.created_at,
    )


def _png_file_name(value: str) -> str:
    if "/" in value or "\\" in value or ".csv" in value.lower():
        raise ArtifactRegistrationError("invalid file name")
    return _match(value, _PNG_NAME, "file name")


def _chart_file_name(name: str) -> str:
    candidate = name.strip()
    if "/" in candidate or "\\" in candidate or ".csv" in candidate.lower():
        raise ChartSaveError("chart file name must be a single PNG file name")
    if not candidate.lower().endswith(".png"):
        candidate = f"{candidate}.png"
    if _PNG_NAME.fullmatch(candidate) is None:
        raise ChartSaveError("chart file name must be a single PNG file name")
    return candidate


def _load_index(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ChartSaveError("chart index is not valid JSON") from error
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list):
        raise ChartSaveError("chart index is not valid JSON")
    entries: list[dict[str, str]] = []
    for item in files:
        if not isinstance(item, dict):
            raise ChartSaveError("chart index is not valid JSON")
        file_name = item.get("file_name")
        digest = item.get("sha256")
        if (
            set(item) != {"file_name", "sha256"}
            or not isinstance(file_name, str)
            or not isinstance(digest, str)
        ):
            raise ChartSaveError("chart index is not valid JSON")
        entries.append({"file_name": file_name, "sha256": digest})
    return entries


def _write_index(path: Path, entries: Sequence[Mapping[str, str]]) -> None:
    ordered = sorted(entries, key=lambda item: item["file_name"])
    text = json.dumps({"files": ordered}, indent=2) + "\n"
    temporary = path.with_name(".index.json.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _close(session: object) -> None:
    close = getattr(session, "close", None)
    if callable(close):
        with contextlib.suppress(Exception):
            close()
