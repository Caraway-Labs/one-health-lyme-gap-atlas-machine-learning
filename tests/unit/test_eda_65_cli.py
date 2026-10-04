"""CLI access-blocker regression; synthetic snapshots never stand in for cohorts."""

import hashlib
import json
import sys
from pathlib import Path
from runpy import run_path

import pytest


@pytest.mark.parametrize("mode", ["acquire", "snapshot"])
def test_blocked_dev_input_is_not_scientific_nonestimability(tmp_path, monkeypatch, capsys, mode):
    main = run_path(str(Path(__file__).resolve().parents[2] / "scripts/eda_65.py"))["main"]
    snapshot = {"status": "BLOCKED", "scientific_estimability": "UNASSESSED", "counts": None}
    output = tmp_path / "output"
    if mode == "snapshot":
        path = tmp_path / "blocked.json"
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        arguments = ["--snapshot", str(path), "--expected-sha256", digest]
    else:

        class Connection:
            closed = False

            def close(self):
                self.closed = True

        connection = Connection()
        monkeypatch.setitem(main.__globals__, "open_bounded_connection", lambda: connection)
        monkeypatch.setitem(main.__globals__, "acquire", lambda _: snapshot)
        arguments = ["--acquire"]
    monkeypatch.setattr(sys, "argv", ["eda_65.py", *arguments, "--output", str(output)])
    assert main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["disposition"] == "INPUT_BLOCKED"
    assert result["scientific_estimability"] == "UNASSESSED"
    assert result["counts"] is None
    assert "primary" not in result
    assert json.loads((output / "summary.json").read_text()) == result
    if mode == "acquire":
        assert connection.closed
