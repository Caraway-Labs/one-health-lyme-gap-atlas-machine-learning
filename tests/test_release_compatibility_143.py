import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "docs/eda/143-release-compatibility.md"
SQL = ROOT / "sql/validation/143_release_compatibility.sql"
WRITE_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|GRANT|COPY)\b",
    re.IGNORECASE,
)


def test_compatibility_note_records_the_dated_carry_forward() -> None:
    text = NOTE.read_text(encoding="utf-8")
    assert "Carry forward, dated 2026-10-18" in text
    assert "governed-2026-10-15-january-climate-prod" in text
    assert "53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d" in text
    assert "2026-10-18T10:12:02.959000-07:00" in text
    assert "PRESENTATION.CURRENT_RELEASE_V" in text
    assert "OH_LYME_PROD_READ" in text
    assert "This task writes no production Snowflake object." in text
    assert "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/698" in text
    assert "explicit unavailable state" in text
    assert "does not substitute another class, a zero, or a Tier 1 priority" in text
    assert "A matching release title, or an equal county count, is not the comparison." in text
    assert "does not approve publication" in text


def test_compatibility_sql_is_a_single_release_read() -> None:
    text = SQL.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("--"))
    statements = [item.strip() for item in code.split(";") if item.strip()]
    assert len(statements) == 1
    assert statements[0].upper().startswith("SELECT")
    assert "PRESENTATION.CURRENT_RELEASE_V" in statements[0]
    assert WRITE_SQL.search(code) is None
