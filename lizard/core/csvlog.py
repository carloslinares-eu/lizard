"""Appending readings to a CSV file."""

from __future__ import annotations

import csv
import time
from collections.abc import Iterable
from pathlib import Path

HEADER = ("timestamp", "sensor", "temperature_c")
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class CsvLog:
    """An open log file: one row per sensor per reading, in local time.

    Rows are flushed after every round of readings so nothing is lost if Lizard
    is killed. An existing file is appended to; a new or empty one gets a header.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self.path.exists() or self.path.stat().st_size == 0
        self._file = self.path.open("a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self.rows_written = 0
        if new_file:
            self._writer.writerow(HEADER)
            self._file.flush()

    def write(self, when: float, values: Iterable[tuple[str, float]]) -> int:
        """Append one round of ``(sensor, °C)`` values taken at UNIX time ``when``; returns the rows written."""
        stamp = time.strftime(TIMESTAMP_FORMAT, time.localtime(when))
        rows = [(stamp, name, f"{celsius:.1f}") for name, celsius in values]
        self._writer.writerows(rows)
        self._file.flush()
        self.rows_written += len(rows)
        return len(rows)

    def close(self) -> None:
        self._file.close()
