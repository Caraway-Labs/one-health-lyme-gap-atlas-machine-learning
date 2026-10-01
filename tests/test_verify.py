"""Regression checks for the shared offline gate and opt-in boundary."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import verify  # noqa: E402


def test_offline_entrypoint_propagates_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(sys, "argv", ["verify.py"])
    monkeypatch.setattr(verify, "validate_repository", lambda: None)

    def fake_run(label: str, args: list[str], *, offline: bool = False) -> bool:
        calls.append((label, args, offline))
        return label != "mypy"

    monkeypatch.setattr(verify, "run", fake_run)
    assert verify.main() == 1
    assert [label for label, _, _ in calls] == ["ruff", "format", "mypy", "pytest"]
    assert all(args[:2] == ["uv", "run"] and offline for _, args, offline in calls)
    assert "--ignore=tests/test_arize_dev_integration.py" in calls[-1][1]
    assert "--ignore=tests/test_snowflake_dev_integration.py" in calls[-1][1]


def test_offline_subprocess_scrubs_inherited_live_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_RUN_ARIZE_DEV_TEST", "1")
    monkeypatch.setenv("ATLAS_RUN_SNOWFLAKE_DEV_TEST", "1")
    observed = {}

    def fake_subprocess(args: list[str], **kwargs: object) -> object:
        observed.update(kwargs["env"])  # type: ignore[arg-type]
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(verify.subprocess, "run", fake_subprocess)
    assert verify.run("pytest", ["uv", "run", "pytest"], offline=True)
    assert "ATLAS_RUN_ARIZE_DEV_TEST" not in observed
    assert "ATLAS_RUN_SNOWFLAKE_DEV_TEST" not in observed


def test_integration_requires_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["verify.py", "--integration", "arize"])
    monkeypatch.delenv("ATLAS_RUN_ARIZE_DEV_TEST", raising=False)
    with pytest.raises(SystemExit) as error:
        verify.main()
    assert error.value.code == 2


def test_invalid_bundle_secret_fails_closed() -> None:
    source = Path(__file__).resolve().parents[1] / "config/examples/synthetic-lineage-v1.json"
    raw = copy.deepcopy(json.loads(source.read_text(encoding="utf-8")))
    raw["arize"]["api_key"] = "dummy"
    from lyme_gap_atlas_ml.contracts import ContractError, validate_bundle

    with pytest.raises(ContractError, match="prohibited secret"):
        validate_bundle(raw)


def test_nested_schema_and_example_errors_have_paths(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "docs/methodology/lifecycle-state-v1.schema.json").read_text(encoding="utf-8")
    )
    example = json.loads(
        (root / "docs/methodology/lifecycle-state-v1.template.json").read_text(encoding="utf-8")
    )
    schema_path, example_path = tmp_path / "schema.json", tmp_path / "example.json"
    schema["properties"]["project_id"]["type"] = "bogus"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    example_path.write_text(json.dumps(example), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid schema.*project_id/type"):
        verify.validate_schema_example(schema_path, example_path)
    schema["properties"]["project_id"]["type"] = "string"
    example["stages"]["frame"]["evidence"] = []
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    example_path.write_text(json.dumps(example), encoding="utf-8")
    with pytest.raises(ValueError, match="stages/frame/evidence"):
        verify.validate_schema_example(schema_path, example_path)
