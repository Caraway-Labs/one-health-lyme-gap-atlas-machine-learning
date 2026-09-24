"""Generate the structural JSON Schema from the reviewed synthetic v1 shape.

Cross-reference and safety rules are enforced by contracts.validate_bundle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config/examples/synthetic-lineage-v1.json"
OUTPUT = ROOT / "docs/architecture/declarative-ml-contracts-v1.schema.json"


def shape(value: Any, key: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "type": "object",
            "required": list(value),
            "properties": {name: shape(child, name) for name, child in value.items()},
            "additionalProperties": False,
        }
    if isinstance(value, list):
        if key == "seeds":
            item: dict[str, Any] = {"type": "integer", "minimum": 0}
        else:
            item = {"type": "string", "minLength": 1}
        return {"type": "array", "items": item, "uniqueItems": True}
    if isinstance(value, bool):
        return {"const": True} if key == "protected" else {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if key == "schema":
        return {"const": value}
    if key == "id" or key in {"run_id", "inference_run_id", "holdout_id"}:
        return {"type": "string", "pattern": "^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"}
    if key in {"version", "output_contract_version"}:
        return {"type": "string", "pattern": "^v[1-9][0-9]*(?:\\.[0-9]+){0,2}$"}
    if key == "git_sha":
        return {"type": "string", "pattern": "^[0-9a-f]{40}$"}
    if key in {"time_start", "time_end", "data_cutoff", "label_as_of", "prediction_cutoff"}:
        return {"type": "string", "format": "date"}
    if key in {"strategy", "validation_strategy"}:
        return {"enum": ["iid", "stratified", "temporal", "grouped_spatial", "spatiotemporal"]}
    if key == "environment":
        return {"enum": ["training", "validation", "production"]}
    if key in {"monitoring_status", "evaluation_status"}:
        return {"enum": ["not_collected", "available"]}
    return {"type": "string", "minLength": 1}


def main() -> None:
    schema = shape(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    schema.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/blob/main/docs/architecture/declarative-ml-contracts-v1.schema.json",
            "title": "Atlas ML declarative lineage bundle v1",
            "$comment": (
                "Structural shape only. Use validate_bundle for cross-reference "
                "and secret-key rules."
            ),
        }
    )
    # These mapping entries may be absent until a later approved integration.
    optional = {
        "experiment": {"parent_run_ref": {"type": "string", "minLength": 1}},
        "snowflake": {"feature_store_ref": {"type": "string", "minLength": 1}},
        "evidence": {
            "monitoring_evidence_ref": {"type": "string", "minLength": 1},
            "evaluation_evidence_ref": {"type": "string", "minLength": 1},
        },
    }
    for component, properties in optional.items():
        schema["properties"][component]["properties"].update(properties)
    OUTPUT.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
