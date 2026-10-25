"""The window's options, remembered between runs in ``~/.config/lizard/settings.json``."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from lizard.core.monitor import DEFAULT_INTERVAL, clamp_interval

log = logging.getLogger(__name__)

DEFAULT_LOG_FILE = Path.home() / "temperature_log.csv"
UNITS = ("C", "F")
CHART_MINUTES = (5, 15, 60)
WARN_RANGE = (20.0, 150.0)  # °C


def config_dir() -> Path:
    """``$XDG_CONFIG_HOME/lizard``, which is ``~/.config/lizard`` on most systems."""
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "lizard"


def settings_file() -> Path:
    return config_dir() / "settings.json"


@dataclass(slots=True)
class Settings:
    interval: float = DEFAULT_INTERVAL  # seconds between readings
    unit: str = "C"  # "C" or "F"; only affects display, the log is always in °C
    warn_celsius: float = 80.0  # sensors at or above this are highlighted
    chart_minutes: int = 15
    log_file: str = str(DEFAULT_LOG_FILE)

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        """Read the settings file; anything missing or invalid falls back to its default."""
        path = path or settings_file()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError):
            log.warning("Ignoring unreadable settings file %s", path, exc_info=True)
            return cls()
        if not isinstance(data, dict):
            return cls()

        settings = cls()
        if isinstance(data.get("interval"), (int, float)):
            settings.interval = clamp_interval(data["interval"])
        if data.get("unit") in UNITS:
            settings.unit = data["unit"]
        if isinstance(data.get("warn_celsius"), (int, float)):
            settings.warn_celsius = max(WARN_RANGE[0], min(WARN_RANGE[1], float(data["warn_celsius"])))
        if data.get("chart_minutes") in CHART_MINUTES:
            settings.chart_minutes = data["chart_minutes"]
        if isinstance(data.get("log_file"), str) and data["log_file"].strip():
            settings.log_file = data["log_file"]
        return settings

    def save(self, path: Path | None = None) -> None:
        """Write the settings file (via a temporary file, so a crash can't leave half of it)."""
        path = path or settings_file()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        except OSError:
            log.warning("Could not save settings to %s", path, exc_info=True)
