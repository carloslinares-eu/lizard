from __future__ import annotations

import json

import pytest

from lizard.core import CsvLog, Settings
from lizard.core.monitor import MAX_INTERVAL
from lizard.core.settings import DEFAULT_LOG_FILE, config_dir


def test_csv_log_writes_the_header_once(tmp_path):
    path = tmp_path / "log.csv"
    first = CsvLog(path)
    assert first.write(1_700_000_000, [("CPU", 40.0)]) == 1
    first.close()
    second = CsvLog(path)
    second.write(1_700_000_005, [("CPU", 41.0), ("GPU", 50.25)])
    assert second.rows_written == 2
    second.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "timestamp,sensor,temperature_c"
    assert len(lines) == 4
    assert lines[-1].endswith(",GPU,50.2")


def test_csv_log_quotes_awkward_sensor_names(tmp_path):
    log = CsvLog(tmp_path / "log.csv")
    log.write(1_700_000_000, [('Drive "A", bay 1', 30.0)])
    log.close()
    assert '"Drive ""A"", bay 1"' in (tmp_path / "log.csv").read_text(encoding="utf-8")


def test_settings_default_when_there_is_no_file(tmp_path):
    settings = Settings.load(tmp_path / "missing.json")
    assert settings == Settings()
    assert settings.log_file == str(DEFAULT_LOG_FILE)


def test_settings_round_trip(tmp_path):
    path = tmp_path / "lizard" / "settings.json"
    Settings(interval=2, unit="F", warn_celsius=90, chart_minutes=60, log_file="/var/log/temps.csv").save(path)
    assert Settings.load(path) == Settings(interval=2, unit="F", warn_celsius=90, chart_minutes=60,
                                           log_file="/var/log/temps.csv")


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", ""])
def test_unreadable_settings_fall_back_to_defaults(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content)
    assert Settings.load(path) == Settings()


def test_invalid_values_fall_back_or_are_clamped(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"interval": 10**9, "unit": "K", "warn_celsius": 999, "chart_minutes": 7,
                                "log_file": "  ", "unknown": True}))
    settings = Settings.load(path)
    assert settings.interval == MAX_INTERVAL
    assert settings.unit == "C"
    assert settings.warn_celsius == 150
    assert settings.chart_minutes == 15
    assert settings.log_file == str(DEFAULT_LOG_FILE)


def test_config_dir_follows_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_dir() == tmp_path / "lizard"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert config_dir().parts[-2:] == (".config", "lizard")
