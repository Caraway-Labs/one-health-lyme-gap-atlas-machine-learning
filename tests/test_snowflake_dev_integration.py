"""Optional read-only DEV proof; normal pytest always skips it."""

import os

import pytest

from lyme_gap_atlas_ml.snowflake import (
    ExpectedContext,
    check_context,
    connection_name_from_environment,
)
from lyme_gap_atlas_ml.snowflake.connector import (
    ConnectorContextReader,
    open_local_connection,
)


def live_dev_enabled(values: dict[str, str]) -> bool:
    return values.get("ATLAS_RUN_SNOWFLAKE_DEV_TEST") == "1"


def test_live_dev_opt_in_gate() -> None:
    assert not live_dev_enabled({})
    assert not live_dev_enabled({"ATLAS_RUN_SNOWFLAKE_DEV_TEST": "0"})


def test_dev_context_read_only() -> None:
    if not live_dev_enabled(dict(os.environ)):
        pytest.skip("Set ATLAS_RUN_SNOWFLAKE_DEV_TEST=1 for approved DEV context proof")
    name = connection_name_from_environment()
    required = (
        "ATLAS_EXPECTED_SNOWFLAKE_DEV_ROLE",
        "ATLAS_EXPECTED_SNOWFLAKE_DEV_DATABASE",
        "ATLAS_EXPECTED_SNOWFLAKE_DEV_SCHEMA",
        "ATLAS_EXPECTED_SNOWFLAKE_DEV_WAREHOUSE",
    )
    missing = [key for key in required if not os.environ.get(key, "").strip()]
    if missing:
        pytest.fail(f"Missing expected DEV context configuration: {', '.join(missing)}")
    expected = ExpectedContext(
        role=os.environ["ATLAS_EXPECTED_SNOWFLAKE_DEV_ROLE"],
        database=os.environ["ATLAS_EXPECTED_SNOWFLAKE_DEV_DATABASE"],
        schema=os.environ["ATLAS_EXPECTED_SNOWFLAKE_DEV_SCHEMA"],
        warehouse=os.environ["ATLAS_EXPECTED_SNOWFLAKE_DEV_WAREHOUSE"],
    )
    if not expected.role.upper().startswith("OH_LYME_DEV_"):
        pytest.fail("Opt-in test requires an expected DEV role")
    with open_local_connection(name) as connection:
        actual = check_context(ConnectorContextReader(connection), expected)
    print(f"DEV Snowflake context: {actual}")
