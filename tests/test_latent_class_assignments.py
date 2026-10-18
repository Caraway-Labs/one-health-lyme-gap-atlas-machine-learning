import json
from pathlib import Path

from lyme_gap_atlas_ml.latent_class_inputs import NATIONAL_COUNTY_COUNT

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "config/experiments/119-latent-class-v1-result.json"
NOTE = ROOT / "docs/methodology/119-class-count-selection.md"


def test_committed_assignments_cover_the_national_cohort() -> None:
    document = json.loads(RESULT.read_text(encoding="utf-8"))
    note = NOTE.read_text(encoding="utf-8")
    assert "228-county" not in note
    assert "follow-up county list was not an input" in note
    assert document["county_count"] == NATIONAL_COUNTY_COUNT
    assert document["snowflake_objects_written"] == []
    assert document["code_revision"] == "cd936fe345664e606c916b137dd642caa0d6d73b"
    for estimand in ("four-state", "tick-pathogen"):
        payload = document["estimands"][estimand]
        assignments = payload["assignments"]
        assert payload["selected_classes"] == 4
        assert payload["model"]["converged"] is True
        assert len(assignments) == NATIONAL_COUNTY_COUNT
        assert [row["fips"] for row in assignments] == sorted(row["fips"] for row in assignments)
        assert sum(row["state"] == "AK" for row in assignments) == 30
        assert sum(row["state"] == "HI" for row in assignments) == 5
        levels = {feature["name"]: feature["levels"] for feature in payload["model"]["features"]}
        assert "No records" in levels["SCAPULARIS_STATUS"]
        assert "Unknown" in levels["SCAPULARIS_STATUS"]
        for row in assignments:
            probability = row["probability"]
            assert len(probability) == 4
            assert abs(sum(probability) - 1.0) < 1e-6
            assert row["class_id"] == max(range(4), key=probability.__getitem__)
