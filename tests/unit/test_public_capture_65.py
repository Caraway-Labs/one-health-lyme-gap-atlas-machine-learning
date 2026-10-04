"""Synthetic public-loader tests; never substitute these counts for PROD evidence."""

import hashlib
import json

import pytest

from lyme_gap_atlas_ml import public_capture_65 as public
from lyme_gap_atlas_ml.evidence_association_65 import analyze_aggregate_counties
from lyme_gap_atlas_ml.shared_capture_65 import SharedInputError


def synthetic_files(tmp_path, monkeypatch, mutate=None):
    counties = [
        {
            "fips": f"{i:05d}",
            "in_contiguous_tick_scope": True,
            "tick_status": "Established" if i % 2 else "No records",
            "burgdorferi_status": "Present" if i % 2 else "No records",
            "score": {"derived_do_not_use": 123},
        }
        for i in range(3144)
    ]
    fips_digest = hashlib.sha256(
        ("\n".join(sorted(row["fips"] for row in counties)) + "\n").encode()
    ).hexdigest()
    monkeypatch.setattr(public, "CANONICAL_FIPS_SHA256", fips_digest)
    metadata = public.EXPECTED_IDENTITY | {
        "scope": "US_COUNTIES",
        "sources": [{"key": key, "vintage": "through 2025-12-31"} for key in public.SOURCE_ANCHORS],
    }
    sources = {
        "data": [
            {
                "source_id": key,
                "lineage_source_id": "cdc_arbonet_tick_module",
                "dataset_id": value["dataset_id"],
                "source_vintage": "through 2025-12-31",
                "release_version": public.PROD_RELEASE,
            }
            for key, value in public.SOURCE_ANCHORS.items()
        ],
        "meta": {"next_page_token": None},
    }
    payloads = {
        "prod-api-metadata-before.json": metadata,
        "prod-api-metadata-after.json": metadata,
        "prod-api-scores.json": {
            "release_id": public.PROD_RELEASE,
            "methodology_version": "semantic-1.0.0",
            "counties": counties,
        },
        "prod-api-sources.json": sources,
        "prod-api-measures.json": {"data": [], "meta": {"next_page_token": None}},
    }
    detail = {
        "release": metadata,
        "fips": "01001",
        "in_contiguous_tick_scope": True,
        "scapularis_status": "Established",
        "pacificus_status": "No records",
        "tick_status": "Established",
        "burgdorferi_status": "Present",
    }
    if mutate:
        mutate(payloads, detail)
    files = {}
    for name, (route, maximum) in public.PUBLIC_FILES.items():
        content = json.dumps(payloads[name]).encode()
        (tmp_path / name).write_bytes(content)
        files[name] = {
            "url": public.PUBLIC_BASE + route,
            "timeout_seconds": 30,
            "max_bytes": maximum,
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }
    manifest = {
        "schema": "ml63-shared-public-consumer-capture/v1",
        "release_before": public.EXPECTED_IDENTITY,
        "release_after": public.EXPECTED_IDENTITY,
        "served_identity_unchanged": True,
        "canonical_fips_normalized_sha256": fips_digest,
        "files": files,
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    detail_path = tmp_path / "detail.json"
    detail_path.write_text(json.dumps(detail), encoding="utf-8")
    return (
        tmp_path,
        manifest_path,
        hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        files["prod-api-scores.json"]["sha256"],
        detail_path,
        hashlib.sha256(detail_path.read_bytes()).hexdigest(),
    )


def test_public_aggregate_is_not_reconstructed_species_and_unknown_is_not_negative(
    tmp_path, monkeypatch
):
    def mutate(payloads, detail):
        payloads["prod-api-scores.json"]["counties"][0]["tick_status"] = "Unknown"
        payloads["prod-api-scores.json"]["counties"][1]["burgdorferi_status"] = "Unknown"

    rows, provenance = public.load_public_capture(*synthetic_files(tmp_path, monkeypatch, mutate))
    assert all("SCAPULARIS_STATUS" not in row and "PACIFICUS_STATUS" not in row for row in rows)
    assert all("score" not in row for row in rows)
    result = analyze_aggregate_counties(rows, public.PROD_RELEASE)
    assert result["primary"]["n"] == 3142  # synthetic only
    assert result["exclusions"]["vector_unknown_in_scope"] == 1
    assert result["exclusions"]["pathogen_unknown_in_scope"] == 1
    assert result["primary"]["v"] == pytest.approx(1)
    assert not any(key.startswith("scapularis:") for key in result["states_all_counties"])
    assert provenance["reviewed_metadata_admission_established"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p, d: p["prod-api-sources.json"]["data"][0].update(dataset_id="wrong"),
        lambda p, d: p["prod-api-metadata-before.json"].update(bundle_sha256="b" * 64),
        lambda p, d: p["prod-api-sources.json"]["meta"].update(next_page_token="more"),
        lambda p, d: p["prod-api-scores.json"]["counties"][0].update(tick_status="Negative"),
        lambda p, d: p["prod-api-scores.json"]["counties"][1].update(fips="00000"),
        lambda p, d: d.update(scapularis_status="Established", pacificus_status="Unknown"),
        lambda p, d: d.update(tick_status="Reported"),
        lambda p, d: d.update(burgdorferi_status="No records"),
    ],
)
def test_gate_failures_prevent_analysis(tmp_path, monkeypatch, mutate):
    with pytest.raises(SharedInputError):
        public.load_public_capture(*synthetic_files(tmp_path, monkeypatch, mutate))


def test_retained_response_tamper_fails_byte_integrity(tmp_path, monkeypatch):
    args = synthetic_files(tmp_path, monkeypatch)
    path = tmp_path / "prod-api-sources.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(SharedInputError, match="digest mismatch"):
        public.load_public_capture(*args)
