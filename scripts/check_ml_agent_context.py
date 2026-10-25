#!/usr/bin/env python3
"""Print ML agent role, warehouse, database, and three access-boundary results.

Reads SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE,
SNOWFLAKE_DATABASE, and SNOWFLAKE_PAT. Refuses to run unless the role is
OH_LYME_ML_AGENT. Does not print the token or other secret values.

Optional non-secret overrides:
  ATLAS_ML_AGENT_PROD_READ_OBJECT
  ATLAS_ML_AGENT_PROD_WRITE_SCHEMA
  ATLAS_ML_AGENT_SCRATCH_SCHEMA
"""

from __future__ import annotations

from lyme_gap_atlas_ml.snowflake.ml_agent_access import main

if __name__ == "__main__":
    raise SystemExit(main())
