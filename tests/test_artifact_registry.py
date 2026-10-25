"""Fake-session coverage for ML Lab artifact registration and local charts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lyme_gap_atlas_ml.registry.artifacts import (
    CHART_KIND,
    CHART_MIME_TYPE,
    DRIVE_SHARED_FOLDER_ID,
    DUPLICATE_SQL,
    INSERT_SQL,
    MAX_CHART_BYTES,
    ML_LAB_DATABASE,
    ArtifactRegistration,
    ArtifactRegistrationError,
    ChartSaveError,
    DuplicateArtifactError,
    register_artifact,
    save_chart,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    IDENTITY_SQL,
    REFUSED_ROLE,
    ConfigError,
    CursorStatementExecutor,
    MlAgentConnectionSettings,
)

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "runbooks" / "cursor-cloud-agent.md"
TOKEN = "test-only-pat"
ACCOUNT = "test-account"
FILE_ID = "chartFileId1234567890"
SHA256 = "ab" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"chart"
WHEN = datetime(2026, 10, 25, 1, 2, 3, tzinfo=UTC)


def _env(**overrides: str) -> dict[str, str]:
    values = {
        "SNOWFLAKE_ACCOUNT": ACCOUNT,
        "SNOWFLAKE_USER": "test-user",
        "SNOWFLAKE_ROLE": "OH_LYME_ML_AGENT",
        "SNOWFLAKE_WAREHOUSE": "OH_LYME_ML_LAB_XS_WH",
        "SNOWFLAKE_DATABASE": ML_LAB_DATABASE,
        "SNOWFLAKE_PAT": TOKEN,
    }
    values.update(overrides)
    return values


def _link(file_id: str = FILE_ID) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"


class FakeCursor:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection
        self._rows: list[tuple[object, ...]] = []
        self.description: object = None

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, params: Sequence[object] | None = None) -> None:
        self._connection.calls.append((sql, None if params is None else tuple(params)))
        if sql == IDENTITY_SQL:
            self.description = ("ROLE", "WAREHOUSE", "DATABASE")
            self._rows = [self._connection.identity]
            return
        if sql == DUPLICATE_SQL:
            run_id, title = _pair(params)
            self.description = ("RUN_ID", "TITLE")
            self._rows = [
                (row[1], row[3])
                for row in self._connection.rows
                if row[1] == run_id and row[3] == title
            ]
            return
        if sql == INSERT_SQL:
            if self._connection.fail_insert:
                raise RuntimeError(f"insert failed token={TOKEN}")
            bound = tuple(params or ())
            if len(bound) != 11:
                raise AssertionError(bound)
            if any(row[1] == bound[1] and row[3] == bound[3] for row in self._connection.rows):
                raise AssertionError("second row inserted")
            self._connection.rows.append(bound)
            self.description = None
            self._rows = []
            return
        raise AssertionError(sql)

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._rows)


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []
        self.rows: list[tuple[object, ...]] = []
        self.identity: tuple[object, ...] = (
            "OH_LYME_ML_AGENT",
            "OH_LYME_ML_LAB_XS_WH",
            ML_LAB_DATABASE,
        )
        self.fail_insert = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        self.closed = True


def _pair(params: Sequence[object] | None) -> tuple[object, object]:
    if params is None or len(params) != 2:
        raise AssertionError(params)
    return params[0], params[1]


def _register(
    connection: FakeConnection,
    *,
    environ: dict[str, str] | None = None,
    file_name: str = "counties.png",
    run_id: str = "run-161",
    issue: str | int = 161,
    caption: str | None = None,
    byte_size: int | None = None,
) -> ArtifactRegistration:
    return register_artifact(
        run_id,
        issue,
        file_name,
        FILE_ID,
        _link(),
        SHA256,
        caption=caption,
        byte_size=byte_size,
        connection=connection,
        environ=_env() if environ is None else environ,
        clock=lambda: WHEN,
    )


def _row(
    registration: ArtifactRegistration,
) -> tuple[object, ...]:
    return (
        registration.artifact_id,
        registration.run_id,
        CHART_KIND,
        registration.file_name,
        registration.caption,
        registration.drive_file_id,
        registration.drive_link,
        registration.sha256,
        CHART_MIME_TYPE,
        registration.byte_size,
        registration.created_at,
    )


def test_one_call_inserts_one_row_and_a_duplicate_does_not() -> None:
    connection = FakeConnection()
    registered = _register(connection)
    assert registered.created_at == "2026-10-25 01:02:03"
    assert registered.issue == "161"
    assert registered.kind == CHART_KIND
    assert registered.mime_type == CHART_MIME_TYPE
    assert registered.caption is None
    assert registered.byte_size is None
    assert len(registered.artifact_id) == 36
    expected = _row(registered)
    assert connection.rows == [expected]
    insert_calls = [call for call in connection.calls if call[0] == INSERT_SQL]
    assert insert_calls == [(INSERT_SQL, expected)]
    assert [call[0] for call in connection.calls] == [IDENTITY_SQL, DUPLICATE_SQL, INSERT_SQL]
    assert connection.calls[1][1] == ("run-161", "counties.png")
    assert ML_LAB_DATABASE in INSERT_SQL
    assert "ARTIFACT_ID" in INSERT_SQL
    assert "DRIVE_URL" in INSERT_SQL
    assert "TITLE" in INSERT_SQL
    for absent in ("ISSUE", "FILE_NAME", "DRIVE_LINK"):
        assert absent not in INSERT_SQL
        assert absent not in DUPLICATE_SQL
    assert "PROD" not in INSERT_SQL
    assert TOKEN not in INSERT_SQL

    with pytest.raises(DuplicateArtifactError, match="already registered"):
        _register(connection, caption="different caption", byte_size=12)
    assert connection.rows == [expected]
    assert [call[0] for call in connection.calls].count(INSERT_SQL) == 1
    assert connection.calls[-1][0] == DUPLICATE_SQL
    assert connection.calls[-1][1] == ("run-161", "counties.png")


def test_same_run_can_register_a_different_file() -> None:
    connection = FakeConnection()
    first = _register(connection, file_name="alpha.png", byte_size=20, caption="alpha")
    second = _register(connection, file_name="beta.png", byte_size=30)
    assert [row[3] for row in connection.rows] == ["alpha.png", "beta.png"]
    assert first.artifact_id != second.artifact_id
    assert connection.rows[0][4] == "alpha"
    assert connection.rows[0][9] == 20
    assert connection.rows[1][4] is None
    assert connection.rows[1][9] == 30


def test_registration_reads_environment_and_closes_the_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()
    seen: dict[str, str] = {}

    def opener(settings: MlAgentConnectionSettings) -> FakeConnection:
        seen["role"] = settings.role
        seen["token"] = settings.token
        return connection

    monkeypatch.setattr(
        "lyme_gap_atlas_ml.registry.artifacts.open_ml_agent_connection",
        opener,
    )
    register_artifact(
        "run-161",
        "161",
        "counties.png",
        FILE_ID,
        _link(),
        SHA256,
        environ=_env(),
        clock=lambda: WHEN,
    )
    assert seen == {"role": "OH_LYME_ML_AGENT", "token": TOKEN}
    assert connection.closed is True
    assert all(TOKEN not in sql and TOKEN not in repr(params) for sql, params in connection.calls)


def test_missing_environment_names_variables_and_does_not_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def opener(_settings: MlAgentConnectionSettings) -> object:
        raise AssertionError("connection should not open")

    monkeypatch.setattr(
        "lyme_gap_atlas_ml.registry.artifacts.open_ml_agent_connection",
        opener,
    )
    environ = _env()
    del environ["SNOWFLAKE_PAT"]
    connection = FakeConnection()
    with pytest.raises(ConfigError, match="SNOWFLAKE_PAT") as caught:
        _register(connection, environ=environ)
    assert ACCOUNT not in str(caught.value)
    assert TOKEN not in str(caught.value)
    assert connection.calls == []


def test_wrong_role_database_and_session_do_not_insert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def opener(_settings: MlAgentConnectionSettings) -> object:
        raise AssertionError("connection should not open")

    monkeypatch.setattr(
        "lyme_gap_atlas_ml.registry.artifacts.open_ml_agent_connection",
        opener,
    )
    connection = FakeConnection()
    with pytest.raises(ArtifactRegistrationError, match=REFUSED_ROLE):
        _register(connection, environ=_env(SNOWFLAKE_ROLE="ACCOUNTADMIN"))
    with pytest.raises(ArtifactRegistrationError, match="ML Lab"):
        _register(connection, environ=_env(SNOWFLAKE_DATABASE="ONE_HEALTH_LYME_GAP_ATLAS_DEV"))
    with pytest.raises(ConfigError, match="PROD"):
        _register(connection, environ=_env(SNOWFLAKE_DATABASE="ONE_HEALTH_LYME_GAP_ATLAS_PROD"))
    connection.identity = ("ACCOUNTADMIN", "OH_LYME_ML_LAB_XS_WH", ML_LAB_DATABASE)
    with pytest.raises(ArtifactRegistrationError, match=REFUSED_ROLE):
        _register(connection)
    assert connection.rows == []
    assert all(sql != INSERT_SQL for sql, _params in connection.calls)


def test_failed_insert_does_not_add_a_row() -> None:
    connection = FakeConnection()
    connection.fail_insert = True
    with pytest.raises(ArtifactRegistrationError, match="statement failed"):
        _register(connection)
    assert connection.rows == []
    assert TOKEN not in "statement failed"


def test_invalid_chart_metadata_is_rejected_before_a_query() -> None:
    connection = FakeConnection()
    with pytest.raises(ArtifactRegistrationError, match="file name"):
        _register(connection, file_name="extract.csv")
    with pytest.raises(ArtifactRegistrationError, match="sha256"):
        register_artifact(
            "run-161",
            "161",
            "counties.png",
            FILE_ID,
            _link(),
            "not-a-checksum",
            connection=connection,
            environ=_env(),
            clock=lambda: WHEN,
        )
    with pytest.raises(ArtifactRegistrationError, match="https"):
        register_artifact(
            "run-161",
            "161",
            "counties.png",
            FILE_ID,
            "http://drive.google.com/file/d/" + FILE_ID,
            SHA256,
            connection=connection,
            environ=_env(),
            clock=lambda: WHEN,
        )
    with pytest.raises(ArtifactRegistrationError, match="byte size"):
        _register(connection, byte_size=-1)
    with pytest.raises(ArtifactRegistrationError, match="byte size"):
        _register(connection, byte_size=True)  # type: ignore[arg-type]
    assert connection.calls == []


def test_save_chart_writes_png_and_index(tmp_path: Path) -> None:
    first = save_chart(161, "beta", PNG, root=tmp_path)
    second = save_chart("161", "alpha.png", PNG + b"-2", root=tmp_path)
    assert first.path == tmp_path / "161" / "beta.png"
    assert first.path.read_bytes() == PNG
    assert first.sha256 == hashlib.sha256(PNG).hexdigest()
    index_path = tmp_path / "161" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index == {
        "files": [
            {"file_name": "alpha.png", "sha256": second.sha256},
            {"file_name": "beta.png", "sha256": first.sha256},
        ]
    }
    assert str(tmp_path) not in index_path.read_text(encoding="utf-8")
    updated = save_chart(161, "beta.png", PNG + b"-3", root=tmp_path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert [item["file_name"] for item in index["files"]] == ["alpha.png", "beta.png"]
    assert index["files"][1]["sha256"] == updated.sha256


def test_save_chart_rejects_extracts_and_oversized_pngs(tmp_path: Path) -> None:
    with pytest.raises(ChartSaveError, match="PNG file name"):
        save_chart(161, "extract.csv", PNG, root=tmp_path)
    with pytest.raises(ChartSaveError, match="PNG"):
        save_chart(161, "counties.png", b"county,count\n01001,1\n", root=tmp_path)
    with pytest.raises(ChartSaveError, match="size"):
        save_chart(161, "counties.png", PNG + (b"x" * MAX_CHART_BYTES), root=tmp_path)
    with pytest.raises(ChartSaveError, match="issue"):
        save_chart("../161", "counties.png", PNG, root=tmp_path)
    assert list(tmp_path.rglob("*")) == []


def test_charts_and_csv_files_are_not_tracked() -> None:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    names = [name for name in tracked.decode().split("\0") if name]
    blocked = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".csv"}
    assert [name for name in names if Path(name).suffix.lower() in blocked] == []
    for relative in (
        "artifacts/charts/161/counties.png",
        "artifacts/charts/161/extract.csv",
        "artifacts/charts/161/index.json",
    ):
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=ROOT,
            check=False,
        )
        assert ignored.returncode == 0


def test_runbook_documents_the_drive_mcp_upload() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert DRIVE_SHARED_FOLDER_ID == "1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM"
    for phrase in (
        DRIVE_SHARED_FOLDER_ID,
        "create_file",
        "parentId",
        "base64Content",
        "image/png",
        "disableConversionToGoogleType",
        "application/vnd.google-apps.folder",
        "issue-<number>",
        "register_artifact",
        "artifacts/charts/",
        "index.json",
        "sha256",
        "REGISTRY.ARTIFACTS",
        "ARTIFACT_ID",
        "DRIVE_URL",
        "TITLE",
        "BYTES",
        "REGISTRY.RUNS.ISSUE_NUMBER",
        "record-level",
        "aggregate outputs",
        "no Google service account",
        "no Drive credential",
    ):
        assert phrase in text
    assert "BEGIN PRIVATE KEY" not in text
    assert TOKEN not in text


def test_cursor_executor_forwards_bind_parameters() -> None:
    seen: dict[str, object] = {}

    class Cursor:
        description = None

        def __enter__(self) -> Cursor:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, sql: str, params: Sequence[object] | None = None) -> None:
            seen["sql"] = sql
            seen["params"] = params

        def fetchall(self) -> list[tuple[object, ...]]:
            return []

    class Connection:
        def cursor(self) -> Cursor:
            return Cursor()

    assert CursorStatementExecutor(Connection()).query("SELECT %s", ("x",)) == []
    assert seen == {"sql": "SELECT %s", "params": ("x",)}
