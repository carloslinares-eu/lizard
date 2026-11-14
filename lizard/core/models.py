"""Plain data types passed between the sensor sources, the monitor and the user interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Reading:
    """One temperature reported by a sensor source."""

    label: str  # as the source names it, e.g. "CPU Package id 0"
    celsius: float


@dataclass(frozen=True, slots=True)
class SensorState:
    """Everything the window shows about one sensor. Statistics cover the time since the last reset."""

    name: str  # unique within a monitor
    source: str
    current: float | None  # None when the latest round of readings didn't include this sensor
    minimum: float | None
    maximum: float | None
    average: float | None
    history: tuple[tuple[float, float], ...]  # (UNIX time, °C), oldest first


@dataclass(frozen=True, slots=True)
class MonitorSnapshot:
    """A consistent copy of the monitor's state, safe to use from the GUI thread."""

    sensors: tuple[SensorState, ...]
    rounds: int  # how many times the sources have been read
    last_reading: float | None  # UNIX time
    interval: float
    log_path: Path | None  # set while logging
    rows_logged: int
    problems: tuple[str, ...]  # sources that failed in the latest round
    log_error: str | None  # why logging stopped by itself, if it did

    @property
    def logging(self) -> bool:
        return self.log_path is not None
