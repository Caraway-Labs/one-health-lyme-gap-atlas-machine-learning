"""Reject known UTF-8 decoding regressions in ML #86's review artifacts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAD_SEQUENCES = ("\u0393\u00c7", "\u251c\u00f9", "\ufffd", "\u00e2\u20ac", "\u00c3\u2014")

if __name__ == "__main__":
    for name in ("86-phase1-label-feasibility.md", "86-result-comment-draft.md"):
        path = ROOT / "docs" / "eda" / name
        content = path.read_text(encoding="utf-8-sig", errors="strict")
        for token in BAD_SEQUENCES:
            if token in content:
                raise ValueError(f"encoding regression in {name}: {ascii(token)}")
        print(f"UTF-8 content check passed: {name}")
