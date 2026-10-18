from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs/runbooks/138-surveillance-situation-batch-v1.md"
HANDOFF = ROOT / "docs/contracts/138-surveillance-situation-batch-v1.md"


def test_runbook_covers_refresh_replay_failure_and_rollback() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "surveillance-situation-batch" in text
    assert "version `v1`" in text
    assert "carry forward, dated 2026-10-18" in text
    assert "This procedure writes no production Snowflake object." in text
    for section in ("## Refresh", "## Replay", "## Failure", "## Rollback"):
        body = text.split(section, maxsplit=1)[1].split("##", maxsplit=1)[0]
        assert "**Owner:**" in body
        assert "**Stop:**" in body
    assert "uv run python scripts/assemble_138_surveillance_situation_batch.py" in text
    assert "02b62d7a4cb8970b3cd2506f5206a386a9ceed7cb2253baea16299be2d06ec9b" in text
    assert "does not substitute another class, a zero, or a Tier 1 priority" in text
    assert "API and web must not infer a class when this batch is unavailable." in text


def test_runbook_keeps_the_non_risk_limits_with_the_handoff() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    handoff = HANDOFF.read_text(encoding="utf-8")
    for limit in ("disease risk", "incidence", "pathogen absence", "tier 1 priority"):
        assert limit in text
    assert "surveillance-situation-tick-pathogen.v1.class-0" in text
    assert "pathogen present and counties with no pathogen record" in text
    assert "does not measure pathogen presence" in text
    assert "../runbooks/138-surveillance-situation-batch-v1.md" in handoff
