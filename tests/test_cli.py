from __future__ import annotations

import csv

import pytest

from lizard import __version__, cli
from lizard.core.sensors.demo import DEMO_SENSORS


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)


def test_logs_demo_readings(tmp_path, capsys):
    log_file = tmp_path / "temps.csv"
    assert cli.main(["--demo", "--count", "3", "--log-file", str(log_file)]) == 0

    out, err = capsys.readouterr()
    assert len(out.splitlines()) == 3
    assert "Demo CPU Package" in out and "°C" in out
    assert f"Logging every 5 s to {log_file}" in err

    rows = list(csv.reader(log_file.open(encoding="utf-8")))
    assert rows[0] == ["timestamp", "sensor", "temperature_c"]
    assert len(rows) == 1 + 3 * len(DEMO_SENSORS)


def test_no_log_and_quiet(tmp_path, capsys):
    log_file = tmp_path / "temps.csv"
    assert cli.main(["--demo", "--count", "1", "--no-log", "--quiet", "--log-file", str(log_file)]) == 0
    assert capsys.readouterr().out == ""
    assert not log_file.exists()


def test_list(capsys):
    assert cli.main(["--demo", "--list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(DEMO_SENSORS)
    assert lines[0].startswith("Demo CPU Package") and lines[0].endswith("(demo)")


def test_no_sensors(monkeypatch, capsys):
    monkeypatch.setattr(cli, "discover_sources", lambda demo=False: [])
    assert cli.main([]) == 1
    assert "No temperature sensors found" in capsys.readouterr().err


def test_unwritable_log_file(tmp_path, capsys):
    assert cli.main(["--demo", "--count", "1", "--log-file", str(tmp_path)]) == 1
    assert "Can't write to" in capsys.readouterr().err


def test_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"lizard-log {__version__}"
