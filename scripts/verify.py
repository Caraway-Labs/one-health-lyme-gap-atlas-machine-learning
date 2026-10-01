"""One credential-free verification path; live proofs require explicit selection."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lyme_gap_atlas_ml.contracts import validate_bundle  # noqa: E402
from lyme_gap_atlas_ml.lifecycle import validate_state  # noqa: E402
from lyme_gap_atlas_ml.monitoring.policy import validate_policy  # noqa: E402


def load_json(path: Path) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def validate_schema_example(schema_path: Path, example_path: Path) -> object:
    schema = load_json(schema_path)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        location = "/".join(map(str, error.path)) or "root"
        raise ValueError(f"{schema_path}: invalid schema at {location}: {error.message}") from error
    example = load_json(example_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    error = next(validator.iter_errors(example), None)
    if error is not None:
        location = "/".join(map(str, error.path)) or "root"
        raise ValueError(f"{example_path}: invalid at {location}: {error.message}") from error
    return example


def validate_repository(root: Path = ROOT) -> None:
    bundle = validate_bundle(
        validate_schema_example(
            root / "docs/architecture/declarative-ml-contracts-v1.schema.json",
            root / "config/examples/synthetic-lineage-v1.json",
        )
    )
    for path in sorted((root / "config/examples/monitoring").glob("*.json")):
        validate_policy(load_json(path), bundle)
    validate_state(
        validate_schema_example(
            root / "docs/methodology/lifecycle-state-v1.schema.json",
            root / "docs/methodology/lifecycle-state-v1.template.json",
        )
    )
    skills = root / ".agents/skills"
    for path in sorted(skills.glob("*/SKILL.md")):
        body = path.read_text(encoding="utf-8")
        match = re.match(r"\A---\nname: ([a-z][a-z0-9-]*)\ndescription: (.+)\n---\n", body)
        if not match or match.group(1) != path.parent.name:
            raise ValueError(f"{path}: invalid frontmatter or directory/name mismatch")
        for link in re.findall(r"\]\((\.\./[^)#]+)(?:#[^)]*)?\)", body):
            target = (path.parent / link).resolve()
            if target.is_relative_to(root.resolve()) and not target.is_file():
                raise ValueError(f"{path}: broken relative link {link}")
    if not list(skills.glob("*/SKILL.md")):
        raise ValueError("no canonical skills found")
    tracked = (
        subprocess.run(
            ["git", "-c", f"safe.directory={root.as_posix()}", "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .split("\0")
    )
    for name in tracked:
        if name and (
            re.search(r"(^|/)\.env(?:\.|$)", name) or name.endswith((".pem", ".p8", ".key"))
        ):
            raise ValueError(f"tracked secret-like file: {name}")


def run(label: str, args: list[str], *, offline: bool = False) -> bool:
    print(json.dumps({"check": label, "status": "start"}), flush=True)
    environment = os.environ.copy()
    if offline:
        environment.pop("ATLAS_RUN_ARIZE_DEV_TEST", None)
        environment.pop("ATLAS_RUN_SNOWFLAKE_DEV_TEST", None)
    result = subprocess.run(args, cwd=ROOT, env=environment, check=False)
    print(
        json.dumps(
            {
                "check": label,
                "status": "pass" if result.returncode == 0 else "fail",
                "exit_code": result.returncode,
            }
        ),
        flush=True,
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integration", choices=("snowflake", "arize"))
    options = parser.parse_args()
    if options.integration:
        flag = f"ATLAS_RUN_{options.integration.upper()}_DEV_TEST"
        if os.environ.get(flag) != "1":
            parser.error(f"{flag}=1 and an approved DEV context are required")
        required = (
            ("ARIZE_API_KEY", "ATLAS_ARIZE_TEST_SPACE_ID")
            if options.integration == "arize"
            else (
                "SNOWFLAKE_CONNECTION_NAME",
                "ATLAS_EXPECTED_SNOWFLAKE_DEV_ROLE",
                "ATLAS_EXPECTED_SNOWFLAKE_DEV_DATABASE",
                "ATLAS_EXPECTED_SNOWFLAKE_DEV_SCHEMA",
                "ATLAS_EXPECTED_SNOWFLAKE_DEV_WAREHOUSE",
            )
        )
        missing = [key for key in required if not os.environ.get(key, "").strip()]
        if missing:
            parser.error(f"missing approved integration context: {', '.join(missing)}")
        test = f"tests/test_{options.integration}_dev_integration.py"
        return (
            0
            if run(
                options.integration,
                ["uv", "run", "--extra", options.integration, "pytest", "-rs", "-s", test],
            )
            else 1
        )
    try:
        validate_repository()
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(json.dumps({"check": "contracts", "status": "fail", "error": str(error)}))
        return 1
    print(json.dumps({"check": "contracts", "status": "pass"}), flush=True)
    checks = [
        ("ruff", ["uv", "run", "ruff", "check", "."]),
        ("format", ["uv", "run", "ruff", "format", "--check", "."]),
        ("mypy", ["uv", "run", "mypy", "src"]),
        (
            "pytest",
            [
                "uv",
                "run",
                "pytest",
                "-ra",
                "--ignore=tests/test_arize_dev_integration.py",
                "--ignore=tests/test_snowflake_dev_integration.py",
            ],
        ),
    ]
    results = [run(label, args, offline=True) for label, args in checks]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
