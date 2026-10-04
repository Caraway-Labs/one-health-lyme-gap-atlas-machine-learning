"""Synthetic shared-capture tests only; no actual PROD counts or access."""

import csv
import hashlib
import json
import sys
from pathlib import Path
from runpy import run_path

import pytest

from lyme_gap_atlas_ml.evidence_association_65 import analyze_counties
from lyme_gap_atlas_ml.shared_capture_65 import (
    PROD_BUNDLE,
    PROD_RELEASE,
    RECEIPTS,
    SOURCE_ANCHORS,
    SharedInputError,
    load_shared_capture,
)

main = run_path(str(Path(__file__).resolve().parents[2] / "scripts/eda_65.py"))["main"]


def synthetic_provenance(county_digest):
    return {
        "county_sha256": county_digest,
        "observed_at": "2026-10-04T01:30:00+00:00",
        "release": {
            "release_id": PROD_RELEASE,
            "bundle_sha256": PROD_BUNDLE,
            "schema_version": "1.0.0",
            "methodology_version": "semantic-1.0.0",
            "scope": "US_COUNTIES",
            "status": "PUBLISHED",
        },
        "sources": [
            {
                "source_key": key,
                "source_id": "cdc_arbonet_tick_module",
                "release_version": PROD_RELEASE,
                "vintage": "through 2025-12-31",
                **anchor,
            }
            for key, anchor in SOURCE_ANCHORS.items()
        ],
        "capture": {
            "object": "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
            "query_id": "fixture-query",
            "query_sha256": "a" * 64,
            "row_limit": 3145,
            "timeout_seconds": 30,
            "user": "MATTHEWCARAWAY",
            "role": "OH_LYME_PROD_READ",
            "database": "ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            "schema": "PRESENTATION",
            "warehouse": "OH_LYME_PROD_INGEST_XS_WH",
        },
        "receipts": dict(RECEIPTS),
        "connection_name": "fixture-do-not-print",
    }


def synthetic_rows():
    return [
        {
            "release_id": PROD_RELEASE,
            "fips": f"{i:05d}",
            "in_contiguous_tick_scope": True,
            "scapularis_status": "Established" if i % 2 else "No records",
            "pacificus_status": "No records",
            "burgdorferi_status": "Present" if i % 2 else "No records",
            "population": "ignored-context-value",
        }
        for i in range(3144)
    ]


def write_inputs(tmp_path, rows=None, csv_input=False, change=None):
    rows = synthetic_rows() if rows is None else rows
    county = tmp_path / ("fixture.csv" if csv_input else "fixture.json")
    if csv_input:
        with county.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    else:
        county.write_text(json.dumps(rows), encoding="utf-8")
    county_digest = hashlib.sha256(county.read_bytes()).hexdigest()
    envelope = synthetic_provenance(county_digest)
    if change:
        change(envelope)
    provenance = tmp_path / "fixture-provenance.json"
    provenance.write_text(json.dumps(envelope), encoding="utf-8")
    envelope_digest = hashlib.sha256(provenance.read_bytes()).hexdigest()
    return county, provenance, county_digest, envelope_digest


@pytest.mark.parametrize("csv_input", [False, True])
def test_shared_csv_json_use_same_frozen_rules_and_ignore_context(tmp_path, csv_input):
    rows = synthetic_rows()
    rows[0]["in_contiguous_tick_scope"] = False
    rows[1]["scapularis_status"] = "Unknown"
    rows[2]["burgdorferi_status"] = "Unknown"
    inputs = write_inputs(tmp_path, rows, csv_input)
    accepted, envelope = load_shared_capture(*inputs)
    result = analyze_counties(accepted, PROD_RELEASE)
    assert result["primary"]["n"] == 3141  # synthetic test only
    assert result["exclusions"]["vector_unknown_in_scope"] == 1
    assert result["exclusions"]["pathogen_unknown_in_scope"] == 1
    assert result["primary"]["v"] == pytest.approx(1)
    assert result["sensitivity"]["v"] == pytest.approx(1)
    assert result["source_observation_rows"] is None
    assert "POPULATION" not in accepted[0]
    assert "connection_name" not in envelope


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p["release"].update(bundle_sha256="b" * 64),
        lambda p: p["release"].update(release_id="governed-2026-09-17-unknown-coverage"),
        lambda p: p["sources"][0].update(data_source_version_id="fixture-wrong-version"),
        lambda p: p["sources"][1].update(vintage="annual 2025"),
        lambda p: p["capture"].update(role="ACCOUNTADMIN"),
        lambda p: p["capture"].update(timeout_seconds=31),
        lambda p: p["capture"].update(row_limit=3146),
        lambda p: p["receipts"].update(build_head="f" * 40),
        lambda p: p.update(county_sha256="c" * 64),
        lambda p: p.update(observed_at="2026-10-04T01:30:00"),
    ],
)
def test_provenance_gates_fail_before_statistics(tmp_path, change):
    inputs = write_inputs(tmp_path, change=change)
    with pytest.raises(SharedInputError):
        load_shared_capture(*inputs)


def test_both_byte_digests_and_per_county_release_are_checked(tmp_path):
    inputs = write_inputs(tmp_path)
    inputs[0].write_bytes(inputs[0].read_bytes() + b" ")
    with pytest.raises(SharedInputError, match="digest mismatch"):
        load_shared_capture(*inputs)
    inputs = write_inputs(tmp_path)
    inputs[1].write_bytes(inputs[1].read_bytes() + b" ")
    with pytest.raises(SharedInputError, match="digest mismatch"):
        load_shared_capture(*inputs)
    rows = synthetic_rows()
    rows[0]["release_id"] = "fixture-other-release"
    with pytest.raises(SharedInputError, match="county release"):
        load_shared_capture(*write_inputs(tmp_path, rows))


def test_csv_blank_scope_and_status_stay_missing_and_numeric_boolean_is_rejected(tmp_path):
    rows = synthetic_rows()
    rows[0]["in_contiguous_tick_scope"] = ""
    rows[1]["scapularis_status"] = ""
    accepted, _ = load_shared_capture(*write_inputs(tmp_path, rows, csv_input=True))
    assert accepted[0]["IN_CONTIGUOUS_TICK_SCOPE"] is None
    assert accepted[1]["SCAPULARIS_STATUS"] is None
    result = analyze_counties(accepted, PROD_RELEASE)
    assert result["exclusions"]["missing_scope"] == 1
    assert result["exclusions"]["vector_unknown_in_scope"] == 1
    rows[0]["in_contiguous_tick_scope"] = "0"
    with pytest.raises(SharedInputError, match="boolean"):
        load_shared_capture(*write_inputs(tmp_path, rows, csv_input=True))


def test_local_runner_success_and_invalid_input_are_distinct(tmp_path, monkeypatch, capsys):
    county, provenance, digest, pdigest = write_inputs(tmp_path)
    output = tmp_path / "result"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "eda_65.py",
            "--shared-counties",
            str(county),
            "--provenance",
            str(provenance),
            "--expected-sha256",
            digest,
            "--expected-provenance-sha256",
            pdigest,
            "--output",
            str(output),
        ],
    )
    assert main() == 0
    printed = capsys.readouterr().out
    result = json.loads(printed)
    assert result["release_id"] == PROD_RELEASE
    assert result["scope_amendment"] == "65-prod-scope-amendment/v2"
    assert result["county_sha256"] == digest
    assert "fixture-do-not-print" not in printed
    county.write_bytes(county.read_bytes() + b" ")
    assert main() == 2
    blocked = json.loads(capsys.readouterr().out)
    assert blocked["status"] == "INPUT_BLOCKED"
    assert blocked["scientific_estimability"] == "UNASSESSED"
    assert blocked["counts"] is None
    assert "disposition" not in blocked
