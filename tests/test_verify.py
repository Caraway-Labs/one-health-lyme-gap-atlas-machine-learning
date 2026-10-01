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

    def fake_run(label: str, args: list[str]) -> bool:
        calls.append((label, args))
        return label != "mypy"

    monkeypatch.setattr(verify, "run", fake_run)
    assert verify.main() == 1
    assert [label for label, _ in calls] == ["ruff", "format", "mypy", "pytest"]
    assert all(args[:2] == ["uv", "run"] for _, args in calls)


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
