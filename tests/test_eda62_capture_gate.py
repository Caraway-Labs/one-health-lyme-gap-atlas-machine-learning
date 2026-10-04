"""Synthetic gate tests; no fixture supplies real EDA group counts."""

import hashlib
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import eda62_capture_gate as gate  # noqa: E402
from scripts import eda62_detail_probe as probe  # noqa: E402


def test_digest_mismatch_prevents_input_substitution(tmp_path: Path) -> None:
    file = tmp_path / "fixture.json"
    file.write_bytes(b'[{"synthetic":true}]')
    with pytest.raises(ValueError, match="digest"):
        gate.load_pinned(file, "0" * 64)
    assert gate.load_pinned(file, hashlib.sha256(file.read_bytes()).hexdigest()) == [
        {"synthetic": True}
    ]


def test_canonical_set_not_just_shape_or_count() -> None:
    rows = [{"fips": f"{i:05d}"} for i in range(3144)]
    with pytest.raises(ValueError, match="Canonical county set"):
        gate.county_identity(rows, "fips")


def test_duplicate_counties_rejected() -> None:
    rows = [{"fips": "01001"}] * 3144
    with pytest.raises(ValueError, match="duplicate"):
        gate.county_identity(rows, "fips")


def test_combined_status_never_becomes_species_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    # Bypass only county-set validation to isolate field semantics on a tiny fixture.
    monkeypatch.setattr(gate, "county_identity", lambda rows, key: "fictional")
    identity = {"release_id": gate.PROD_RELEASE, "bundle_sha256": gate.PROD_BUNDLE}
    result = gate.gate_prod_summary(
        {
            "release_id": gate.PROD_RELEASE,
            "counties": [{"fips": "01001", "tick_status": "Established"}],
        },
        {"release_before": identity, "release_after": identity},
    )
    assert result["execution_status"] == "SPECIES_OUTCOME_PROJECTION_MISSING"
    assert result["species_group_n"] is None
    assert result["cohort_disposition"] is None
    assert result["selected_taxon"] is None
    assert result["source_authority_verified"] is False


def test_public_release_change_blocks_profile() -> None:
    with pytest.raises(ValueError, match="identity"):
        gate.gate_prod_summary({}, {"release_before": {}, "release_after": {"changed": True}})


def test_dev_release_membership_checked() -> None:
    identity = {"RELEASE_ID": gate.DEV_RELEASE, "BUNDLE_SHA256": gate.DEV_BUNDLE}
    with pytest.raises(ValueError, match="identity"):
        gate.gate_dev([[], [identity], [], [], [], [{**identity, "RELEASE_ID": "changed"}]])


def test_private_detail_output_and_request_bounds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    payload = json.dumps(
        {
            "fips": "01001",
            "scapularis_status": "Unknown",
            "pacificus_status": "Unknown",
            "svi_percentile": 0.123456,
            "release": {"release_id": gate.PROD_RELEASE, "bundle_sha256": gate.PROD_BUNDLE},
        }
    ).encode()
    requests: list[tuple[str, int]] = []

    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def read(self, n: int) -> bytes:
            assert n == probe.MAX_BYTES + 1
            return payload

    def fetch(url: str, timeout: int) -> Response:
        requests.append((url, timeout))
        return Response()

    monkeypatch.setattr(probe, "urlopen", fetch)
    monkeypatch.setattr(probe, "__file__", str(tmp_path / "scripts" / "probe.py"))
    monkeypatch.setattr(sys, "argv", ["probe", "--output", str(tmp_path / "outside.json")])
    with pytest.raises(ValueError, match="ignored outputs"):
        probe.main()
    assert requests == []
    (tmp_path / "outputs").mkdir()
    monkeypatch.setattr(
        sys, "argv", ["probe", "--output", str(tmp_path / "outputs" / "private.json")]
    )
    probe.main()
    assert requests == [(probe.URL, 30)]
    assert "0.123456" not in capsys.readouterr().out
    assert (tmp_path / "outputs" / "private.json").read_bytes() == payload
