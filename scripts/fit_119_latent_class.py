"""Fit the story 119 latent class models from a local county extract.

The extract is produced by the read-only SQL after the release check. This
script does not open Snowflake and does not write a warehouse object.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy
import sklearn

from lyme_gap_atlas_ml.latent_class_baseline import assert_baseline_cross_tab
from lyme_gap_atlas_ml.latent_class_fit import (
    FitConfig,
    feature_levels,
    feature_names,
    observations,
    select_class_count,
)
from lyme_gap_atlas_ml.latent_class_inputs import (
    assert_admitted_release,
    build_counties,
    require_national_cohort,
)
from lyme_gap_atlas_ml.latent_class_result import build_result_document, render_selection_note

ROOT = Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counties", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument(
        "--experiment",
        type=Path,
        default=ROOT / "config/experiments/119-latent-class-v1.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--note", type=Path, required=True)
    args = parser.parse_args(argv)
    assert_admitted_release(args.release_id, args.bundle_sha256)
    payload = json.loads(args.counties.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit("county extract must be a JSON list")
    counties = require_national_cohort(build_counties(payload), args.release_id, args.bundle_sha256)
    assert_baseline_cross_tab(counties)
    config = frozen_config(json.loads(args.experiment.read_text(encoding="utf-8")))
    selections = {
        estimand: select_class_count(
            observations(counties, estimand),
            feature_levels(estimand),
            feature_names(estimand),
            config,
        )
        for estimand in ("four-state", "tick-pathogen")
    }
    revision = git_revision()
    document = build_result_document(
        counties,
        selections,
        code_revision=revision,
        numpy_version=numpy.__version__,
        sklearn_version=sklearn.__version__,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    args.note.parent.mkdir(parents=True, exist_ok=True)
    args.note.write_text(render_selection_note(document, code_revision=revision), encoding="utf-8")
    blocked = [name for name, selection in selections.items() if selection.selected_classes is None]
    if blocked:
        print(f"class-count rule blocked: {', '.join(blocked)}", file=sys.stderr)
        return 2
    return 0


def frozen_config(payload: object) -> FitConfig:
    """Return the story config only when it still matches the frozen rule."""
    if not isinstance(payload, Mapping):
        raise SystemExit("experiment config must be a JSON object")
    config = FitConfig(
        class_counts=tuple(_as_int(value) for value in _sequence(payload["class_counts"])),
        primary_seed=_as_int(payload["primary_seed"]),
        alternate_seeds=tuple(_as_int(value) for value in _sequence(payload["alternate_seeds"])),
        random_starts=_as_int(payload["random_starts_per_seed"]),
        minimum_median_ari=_as_float(payload["minimum_median_adjusted_rand_index"]),
        minimum_class_counties=_as_int(payload["minimum_class_counties"]),
        bic_margin=_as_float(payload["bic_margin"]),
    )
    if config != FitConfig():
        raise SystemExit("experiment config does not match the frozen class-count rule")
    return config


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SystemExit("experiment config integer is malformed")
    return value


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SystemExit("experiment config number is malformed")
    return float(value)


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise SystemExit("experiment config list is malformed")
    return value


def git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
