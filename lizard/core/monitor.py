"""Reads every sensor source on a timer, keeps recent history and statistics, and feeds the CSV log."""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import Counter, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from lizard.core.csvlog import CsvLog
from lizard.core.models import MonitorSnapshot, Reading, SensorState
from lizard.core.sensors.base import SensorError

log = logging.getLogger(__name__)

DEFAULT_INTERVAL = 5.0
MIN_INTERVAL = 1.0
MAX_INTERVAL = 3600.0
HISTORY_SECONDS = 3600.0  # the longest chart window


def clamp_interval(seconds: float) -> float:
    if math.isnan(seconds):
        return DEFAULT_INTERVAL
    return max(MIN_INTERVAL, min(MAX_INTERVAL, float(seconds)))


@dataclass(slots=True)
class _Sensor:
    name: str
    source: str
    history: deque[tuple[float, float]] = field(default_factory=deque)
    current: float | None = None
    count: int = 0
    total: float = 0.0
    minimum: float = math.inf
    maximum: float = -math.inf

    def record(self, when: float, celsius: float, keep_seconds: float) -> None:
        self.current = celsius
        self.count += 1
        self.total += celsius
        self.minimum = min(self.minimum, celsius)
        self.maximum = max(self.maximum, celsius)
        self.history.append((when, celsius))
        while self.history and self.history[0][0] < when - keep_seconds:
            self.history.popleft()

    def reset(self) -> None:
        self.history.clear()
        self.count, self.total = 0, 0.0
        self.minimum, self.maximum = math.inf, -math.inf

    def state(self) -> SensorState:
        has_data = self.count > 0
        return SensorState(
            name=self.name,
            source=self.source,
            current=self.current,
            minimum=self.minimum if has_data else None,
            maximum=self.maximum if has_data else None,
            average=self.total / self.count if has_data else None,
            history=tuple(self.history),
        )


class Monitor:
    """Owns the sensor sources and everything learned from them.

    ``start()`` reads the sources on a background thread every ``interval``
    seconds; ``sample_once()`` does a single round on the calling thread (the
    headless logger and the tests use it directly). The GUI only calls
    ``snapshot()``, ``revision`` and the setters, which are all thread-safe.
    """

    def __init__(self, sources: Iterable, interval: float = DEFAULT_INTERVAL,
                 history_seconds: float = HISTORY_SECONDS, clock: Callable[[], float] = time.time):
        self._sources = list(sources)
        self._interval = clamp_interval(interval)
        self._history_seconds = history_seconds
        self._clock = clock

        self._lock = threading.Lock()
        self._sensors: dict[tuple[str, str, int], _Sensor] = {}  # insertion order is display order
        self._names: set[str] = set()
        self._rounds = 0
        self._revision = 0
        self._last_reading: float | None = None
        self._problems: dict[str, str] = {}
        self._log: CsvLog | None = None
        self._log_error: str | None = None

        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    # -- settings ----------------------------------------------------------

    @property
    def sources(self) -> list:
        return list(self._sources)

    @property
    def interval(self) -> float:
        return self._interval

    def set_interval(self, seconds: float) -> float:
        """Change how often the sensors are read; takes effect at once. Returns the value actually used."""
        with self._lock:
            self._interval = clamp_interval(seconds)
            self._revision += 1
        self._wake.set()
        return self._interval

    @property
    def revision(self) -> int:
        """Changes whenever a snapshot would differ, so the GUI can skip redrawing."""
        return self._revision

    # -- background thread -------------------------------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stopping.clear()
        self._thread = threading.Thread(target=self._run, name="lizard-monitor", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        """Stop the background thread and close the log file."""
        self._stopping.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None
        self.stop_logging()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stopping.is_set():
            started = time.monotonic()
            self._wake.clear()
            try:
                self.sample_once()
            except Exception:  # a bug in one round must not stop monitoring for good
                log.exception("Reading the sensors failed")
            self._wake.wait(max(0.0, self._interval - (time.monotonic() - started)))

    # -- reading -----------------------------------------------------------

    def sample_once(self) -> list[tuple[str, float]]:
        """Read every source once, record the values and log them. Returns ``(sensor name, °C)`` pairs."""
        results: list[tuple[str, list[Reading] | None, str | None]] = []
        for source in self._sources:  # outside the lock: nvidia-smi can take a moment
            try:
                results.append((source.name, list(source.read()), None))
            except (OSError, SensorError, ValueError) as exc:
                results.append((source.name, None, str(exc) or type(exc).__name__))
        now = self._clock()

        with self._lock:
            values: list[tuple[str, float]] = []
            seen: set[tuple[str, str, int]] = set()
            for source_name, readings, problem in results:
                if readings is None:
                    if self._problems.get(source_name) != problem:
                        log.warning("Can't read %s: %s", source_name, problem)
                    self._problems[source_name] = problem
                    continue
                self._problems.pop(source_name, None)
                occurrences: Counter[str] = Counter()
                for reading in readings:
                    key = (source_name, reading.label, occurrences[reading.label])
                    occurrences[reading.label] += 1
                    sensor = self._sensor_for(key)
                    sensor.record(now, reading.celsius, self._history_seconds)
                    values.append((sensor.name, reading.celsius))
                    seen.add(key)
            for key, sensor in self._sensors.items():
                if key not in seen:
                    sensor.current = None
            self._rounds += 1
            self._last_reading = now
            self._revision += 1
            if self._log is not None and values:
                try:
                    self._log.write(now, values)
                except OSError as exc:
                    log.error("Logging stopped: %s", exc)
                    self._log_error = f"Writing to {self._log.path} failed: {exc.strerror or exc}"
                    self._close_log()
        return values

    def _sensor_for(self, key: tuple[str, str, int]) -> _Sensor:
        """The sensor for ``(source, label, occurrence)``, created with a name no other sensor has."""
        sensor = self._sensors.get(key)
        if sensor is None:
            name, number = key[1], 2
            while name in self._names:
                name = f"{key[1]} ({number})"
                number += 1
            self._names.add(name)
            sensor = self._sensors[key] = _Sensor(name=name, source=key[0])
        return sensor

    def reset_statistics(self) -> None:
        """Forget the history, minimums, maximums and averages, e.g. before a stress test."""
        with self._lock:
            for sensor in self._sensors.values():
                sensor.reset()
            self._revision += 1

    # -- logging -----------------------------------------------------------

    def start_logging(self, path: Path | str) -> None:
        """Append every following round to a CSV file. Raises ``OSError`` if the file can't be opened."""
        new_log = CsvLog(path)
        with self._lock:
            self._close_log()
            self._log, self._log_error = new_log, None
            self._revision += 1

    def stop_logging(self) -> None:
        with self._lock:
            self._close_log()

    def _close_log(self) -> None:  # call with the lock held
        if self._log is not None:
            try:
                self._log.close()
            except OSError:
                log.warning("Closing the log file failed", exc_info=True)
            self._log = None
            self._revision += 1

    # -- reading the state -------------------------------------------------

    def snapshot(self) -> MonitorSnapshot:
        with self._lock:
            return MonitorSnapshot(
                sensors=tuple(sensor.state() for sensor in self._sensors.values()),
                rounds=self._rounds,
                last_reading=self._last_reading,
                interval=self._interval,
                log_path=self._log.path if self._log is not None else None,
                rows_logged=self._log.rows_written if self._log is not None else 0,
                problems=tuple(f"{name}: {problem}" for name, problem in self._problems.items()),
                log_error=self._log_error,
            )
