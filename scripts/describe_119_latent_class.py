"""Describe the finished story 119 classes from the committed assignments.

The county extract is a local read of the pinned release. This script does not
refit and does not write Snowflake.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counties", type=Path, required=True)
    parser.add_argument(
        "--result",
        type=Path,
        default=ROOT / "config/experiments/119-latent-class-v1-result.json",
    )
    args = parser.parse_args()
    counties = {row["FIPS"]: row for row in json.loads(args.counties.read_text(encoding="utf-8"))}
    result = json.loads(args.result.read_text(encoding="utf-8"))
    for estimand, columns in (
        (
            "four-state",
            ("HUMAN_STATUS", "SCAPULARIS_STATUS", "PACIFICUS_STATUS", "BURGDORFERI_STATUS"),
        ),
        ("tick-pathogen", ("SCAPULARIS_STATUS", "PACIFICUS_STATUS", "BURGDORFERI_STATUS")),
    ):
        grouped: dict[int, Counter[tuple[str, ...]]] = {}
        people: dict[int, Counter[tuple[str, ...]]] = {}
        states: dict[int, Counter[str]] = {}
        for assignment in result["estimands"][estimand]["assignments"]:
            county = counties[assignment["fips"]]
            cell = tuple(str(county[column]) for column in columns)
            class_id = int(assignment["class_id"])
            grouped.setdefault(class_id, Counter())[cell] += 1
            people.setdefault(class_id, Counter())[cell] += int(county["POPULATION"])
            states.setdefault(class_id, Counter())[str(county["STATE"])] += 1
        print(estimand)
        for class_id, counts in sorted(grouped.items()):
            print(
                json.dumps(
                    {
                        "class_id": class_id,
                        "counties": sum(counts.values()),
                        "people": sum(people[class_id].values()),
                        "alaska": states[class_id]["AK"],
                        "hawaii": states[class_id]["HI"],
                        "cells": [
                            {"levels": cell, "counties": count, "people": people[class_id][cell]}
                            for cell, count in counts.most_common()
                        ],
                    }
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
