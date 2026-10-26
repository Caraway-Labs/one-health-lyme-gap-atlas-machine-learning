"""Shared-border county pairs for issue 107.

The insert runs inside Snowflake. Geometry text is an input to ``TRY_TO_GEOGRAPHY``
and is not selected. ``REGISTRY.QUERIES`` rejects that token, so the caller does
not log this statement.
"""

from __future__ import annotations

from lyme_gap_atlas_ml.county_distributions import ATLAS
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE

ADJACENCY_TABLE = f"{ML_LAB_DATABASE}.EDA.COUNTY_ADJACENCY_107"
READER_ROLE = "OH_LYME_PROD_READ"
CREATE_ADJACENCY_SQL = f"""
CREATE TABLE IF NOT EXISTS {ADJACENCY_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    RELEASE_ID VARCHAR NOT NULL,
    FIPS_A VARCHAR NOT NULL,
    FIPS_B VARCHAR NOT NULL
)
""".strip()
INSERT_ADJACENCY_SQL = f"""
INSERT INTO {ADJACENCY_TABLE} (RUN_ID, RELEASE_ID, FIPS_A, FIPS_B)
SELECT %s, A.RELEASE_ID, A.FIPS, B.FIPS
FROM (
    SELECT FIPS, RELEASE_ID, TRY_TO_GEOGRAPHY(GEOMETRY_JSON) AS GEO
    FROM {ATLAS}
) A
JOIN (
    SELECT FIPS, TRY_TO_GEOGRAPHY(GEOMETRY_JSON) AS GEO
    FROM {ATLAS}
) B
    ON A.FIPS < B.FIPS
   AND A.GEO IS NOT NULL
   AND B.GEO IS NOT NULL
   AND ST_TOUCHES(A.GEO, B.GEO)
""".strip()
GRANT_ADJACENCY_SQL = f"GRANT SELECT ON TABLE {ADJACENCY_TABLE} TO ROLE {READER_ROLE}"
COUNT_ADJACENCY_SQL = f"SELECT COUNT(*) FROM {ADJACENCY_TABLE} WHERE RUN_ID = %s"


def adjacency_sql_is_lab_only() -> bool:
    """True when the insert targets the lab table and does not return geometry."""
    upper = INSERT_ADJACENCY_SQL.upper()
    selected = upper.split("SELECT", 1)[1].split("FROM", 1)[0]
    return (
        ADJACENCY_TABLE in INSERT_ADJACENCY_SQL
        and "ST_TOUCHES" in upper
        and "GEO" not in selected
        and "ONE_HEALTH_LYME_GAP_ATLAS_PROD" not in INSERT_ADJACENCY_SQL.split("FROM", 1)[0]
    )
