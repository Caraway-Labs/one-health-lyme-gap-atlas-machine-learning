"""Write the story 138 county handoff and check the committed manifest.

The county file stays in outputs/. --write-committed refreshes the dictionary
and manifest after an explicit versioned change. This script does not open
Snowflake.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from lyme_gap_atlas_ml.surveillance_situation_batch import (
    DICTIONARY_PATH,
    MANIFEST_PATH,
    SituationBatchError,
    assemble_repository,
    document_bytes,
)

ROOT = Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    """Replay the pinned assignments into the handoff location."""
    write_committed = "--write-committed" in (sys.argv[1:] if argv is None else argv)
    try:
        batch = assemble_repository(ROOT)
        county_path = batch.write_county(ROOT)
        dictionary_path = ROOT / DICTIONARY_PATH
        manifest_path = ROOT / MANIFEST_PATH
        if write_committed:
            dictionary_path.write_bytes(batch.dictionary_bytes())
            manifest_path.write_bytes(document_bytes(batch.manifest))
        else:
            _match(dictionary_path, batch.dictionary_bytes(), "class dictionary")
            _match(manifest_path, document_bytes(batch.manifest), "manifest")
    except (OSError, SituationBatchError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "county_artifact": str(county_path),
                "county_sha256": batch.manifest["county_sha256"],
                "approval_state": batch.manifest["approval_state"],
                "snowflake_objects_written": [],
            }
        )
    )
    return 0


def _match(path: Path, expected: bytes, label: str) -> None:
    actual = path.read_bytes().replace(b"\r\n", b"\n")
    if actual != expected:
        raise SituationBatchError(f"{label} does not match the replayed handoff")


if __name__ == "__main__":
    raise SystemExit(main())
