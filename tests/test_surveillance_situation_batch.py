import json
import math
import subprocess
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from lyme_gap_atlas_ml.surveillance_situation_batch import (
    COUNTY_ARTIFACT,
    DICTIONARY_PATH,
    MANIFEST_PATH,
    assemble_repository,
    document_bytes,
    sha256_hex,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "docs/contracts/138-surveillance-situation-batch-v1.schema.json"
FOUR_STATE_COUNTS = {
    "surveillance-situation-four-state.v1.class-0": 801,
    "surveillance-situation-four-state.v1.class-1": 35,
    "surveillance-situation-four-state.v1.class-2": 112,
    "surveillance-situation-four-state.v1.class-3": 2196,
}
TICK_PATHOGEN_COUNTS = {
    "surveillance-situation-tick-pathogen.v1.class-0": 1325,
    "surveillance-situation-tick-pathogen.v1.class-1": 1687,
    "surveillance-situation-tick-pathogen.v1.class-2": 97,
    "surveillance-situation-tick-pathogen.v1.class-3": 35,
}


def test_replay_reproduces_the_pinned_class_counts() -> None:
    batch = assemble_repository(ROOT)
    models = batch.county_document["models"]
    assert isinstance(models, list)
    assert [model["model_id"] for model in models] == [
        "surveillance-situation-four-state",
        "surveillance-situation-tick-pathogen",
    ]
    expected = (FOUR_STATE_COUNTS, TICK_PATHOGEN_COUNTS)
    unknown_ids = (
        "surveillance-situation-four-state.v1.class-1",
        "surveillance-situation-tick-pathogen.v1.class-3",
    )
    seen: list[set[str]] = []
    for model, counts, unknown_id in zip(models, expected, unknown_ids, strict=True):
        rows = model["rows"]
        assert isinstance(rows, list)
        fips = [row["county_fips"] for row in rows]
        assert len(rows) == 3144
        assert fips == sorted(set(fips))
        assert Counter(row["class_id"] for row in rows) == counts
        unknown = [row for row in rows if row["class_id"] == unknown_id]
        assert Counter(row["state"] for row in unknown) == {"AK": 30, "HI": 5}
        assert {row["county_fips"][:2] for row in unknown} == {"02", "15"}
        assert all(row["class_id"] == unknown_id for row in rows if row["state"] in {"AK", "HI"})
        for row in rows:
            assert set(row) == {"county_fips", "state", "population", "class_id", "probabilities"}
            probabilities = row["probabilities"]
            assert [item["class_id"] for item in probabilities] == list(counts)
            values = [item["probability"] for item in probabilities]
            assert len(values) == 4
            assert all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values)
            assert abs(sum(values) - 1.0) <= 1e-6
        seen.append(set(fips))
    assert seen[0] == seen[1]
    assert batch.manifest["approval_state"] == "approved_for_data_handoff"
    assert batch.manifest["snowflake_objects_written"] == []
    assert batch.manifest["git_sha"] == "cd936fe345664e606c916b137dd642caa0d6d73b"
    assert batch.manifest["result_commit"] == "a2f9bad41f1ddb793e364399afbdd5fbad008b7a"
    assert batch.manifest["population_scope"] == {
        "county_count": 3144,
        "geography": "US counties and county equivalents, including Alaska and Hawaii",
        "population": 331097593,
        "population_role": "reporting denominator",
    }


def test_manifest_checksum_matches_the_handoff_file(tmp_path: Path) -> None:
    batch = assemble_repository(ROOT)
    county_path = batch.write_county(tmp_path)
    assert sha256_hex(county_path.read_bytes()) == batch.manifest["county_sha256"]
    dictionary = (ROOT / DICTIONARY_PATH).read_bytes().replace(b"\r\n", b"\n")
    manifest = json.loads((ROOT / MANIFEST_PATH).read_text(encoding="utf-8"))
    assert dictionary == batch.dictionary_bytes()
    assert sha256_hex(dictionary) == manifest["class_dictionary_sha256"]
    assert manifest["county_sha256"] == batch.manifest["county_sha256"]
    assert manifest == batch.manifest
    assert "county_fips" not in dictionary.decode("utf-8")
    assert "Established blacklegged tick" in dictionary.decode("utf-8")


def test_county_extract_is_not_committed() -> None:
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    assert "county-assignments.json" not in tracked
    assert COUNTY_ARTIFACT not in tracked.splitlines()
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", COUNTY_ARTIFACT],
        cwd=ROOT,
        check=False,
    )
    assert ignored.returncode == 0
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert f"{DICTIONARY_PATH} text eol=lf" in attributes
    assert f"{MANIFEST_PATH} text eol=lf" in attributes


def test_handoff_documents_match_the_schema() -> None:
    batch = assemble_repository(ROOT)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for document in (
        batch.county_document,
        batch.dictionary_document,
        json.loads(document_bytes(batch.manifest)),
    ):
        errors = list(validator.iter_errors(document))
        assert errors == []
