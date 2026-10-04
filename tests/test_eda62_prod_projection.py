"""Fictional capture/commit safety tests, never actual cohort evidence."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import eda62_prod_projection as projection  # noqa: E402


def fixture() -> list[object]:
    identity = {"RELEASE_ID": projection.PROD_RELEASE, "BUNDLE_SHA256": projection.PROD_BUNDLE}
    row = {
        **identity,
        "FIPS": "01001",
        "STATE": "AL",
        "SCAPULARIS_STATUS": "Established",
        "PACIFICUS_STATUS": "Unknown",
        "SVI_PERCENTILE": 0.5,
        "BURGDORFERI_STATUS": "Unknown",
    }
    return [[], [identity], [row], [{"CAPTURE_QUERY_ID": "fictional"}], [dict(identity)]]


def test_published_admission_does_not_claim_private_native_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Tiny fixture bypasses only canonical-universe validation, tested separately.
    monkeypatch.setattr(projection, "county_identity", lambda rows, key: "fictional")
    rows, metadata = projection.validate_capture(fixture())
    assert rows[0]["fips"] == "01001"
    assert metadata["published_projection_descriptive_eda_admitted"] is True
    assert metadata["native_lineage_or_ml_feature_admission_claimed"] is False


def test_changed_pointer_rejected() -> None:
    payload = fixture()
    payload[4] = [{"RELEASE_ID": "changed", "BUNDLE_SHA256": projection.PROD_BUNDLE}]
    with pytest.raises(ValueError, match="Release changed"):
        projection.validate_capture(payload)


def test_species_mapping_is_not_guessed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(projection, "county_identity", lambda rows, key: "fictional")
    payload = fixture()
    payload[2][0]["SCAPULARIS_STATUS"] = "Present"
    with pytest.raises(ValueError, match="Unrecognized"):
        projection.validate_capture(payload)


def test_row_release_mismatch_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(projection, "county_identity", lambda rows, key: "fictional")
    payload = fixture()
    payload[2][0]["RELEASE_ID"] = "another-release"
    with pytest.raises(ValueError, match="membership"):
        projection.validate_capture(payload)


def test_selection_requires_full_commit_and_matching_frozen_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="Full registered"):
        projection.verify_selection_commit("short", "scapularis_status")
    monkeypatch.setattr(
        projection.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="other capture scapularis_status",
        ),
    )
    with pytest.raises(ValueError, match="Committed selection"):
        projection.verify_selection_commit("a" * 40, "scapularis_status")
    monkeypatch.setattr(
        projection.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=f"{projection.CAPTURE_SHA} scapularis_status",
        ),
    )
    projection.verify_selection_commit("a" * 40, "scapularis_status")


def test_wrong_context_never_reaches_analysis(tmp_path: Path) -> None:
    path = tmp_path / "fictional-context.json"
    path.write_text(json.dumps([{"CURRENT_ROLE()": "ADMIN"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="context"):
        projection.verify_context(path)
