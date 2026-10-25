from __future__ import annotations

import csv
import math
import time

import pytest

from lizard.core import MAX_INTERVAL, MIN_INTERVAL, Monitor, SensorError
from lizard.core.monitor import DEFAULT_INTERVAL
from tests.conftest import FakeSource


def _wait_for(condition, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_statistics_and_history(clock):
    source = FakeSource("hwmon", [[("CPU", 40.0)], [("CPU", 50.0)], [("CPU", 45.0)]])
    monitor = Monitor([source], clock=clock)
    for _ in range(3):
        monitor.sample_once()
        clock.advance(5)

    snap = monitor.snapshot()
    (cpu,) = snap.sensors
    assert (cpu.name, cpu.source) == ("CPU", "hwmon")
    assert (cpu.current, cpu.minimum, cpu.maximum, cpu.average) == (45.0, 40.0, 50.0, 45.0)
    assert [celsius for _when, celsius in cpu.history] == [40.0, 50.0, 45.0]
    assert cpu.history[1][0] - cpu.history[0][0] == 5
    assert snap.rounds == 3
    assert snap.last_reading == clock.now - 5


def test_sample_once_returns_the_round(clock):
    monitor = Monitor([FakeSource("a", [[("CPU", 41.5), ("GPU", 39.0)]])], clock=clock)
    assert monitor.sample_once() == [("CPU", 41.5), ("GPU", 39.0)]


def test_identical_labels_get_unique_names_that_stay_put(clock):
    drives = FakeSource("hwmon", [[("NVMe Composite", 38.0), ("NVMe Composite", 41.0)]])
    other = FakeSource("other", [[("NVMe Composite", 35.0)]])
    monitor = Monitor([drives, other], clock=clock)
    monitor.sample_once()
    monitor.sample_once()

    sensors = monitor.snapshot().sensors
    assert [(sensor.name, sensor.current) for sensor in sensors] == [
        ("NVMe Composite", 38.0), ("NVMe Composite (2)", 41.0), ("NVMe Composite (3)", 35.0),
    ]
    assert all(len(sensor.history) == 2 for sensor in sensors)


def test_a_failing_source_is_reported_and_the_others_keep_working(clock):
    flaky = FakeSource("nvidia-smi", [SensorError("driver not loaded"), [("GPU", 50.0)]])
    steady = FakeSource("hwmon", [[("CPU", 40.0)]])
    monitor = Monitor([flaky, steady], clock=clock)

    assert monitor.sample_once() == [("CPU", 40.0)]
    assert monitor.snapshot().problems == ("nvidia-smi: driver not loaded",)

    monitor.sample_once()
    snap = monitor.snapshot()
    assert snap.problems == ()
    assert [sensor.name for sensor in snap.sensors] == ["CPU", "GPU"]


def test_a_sensor_missing_from_a_round_is_marked_stale(clock):
    monitor = Monitor([FakeSource("hwmon", [[("CPU", 40.0), ("GPU", 60.0)], [("CPU", 41.0)]])], clock=clock)
    monitor.sample_once()
    monitor.sample_once()

    cpu, gpu = monitor.snapshot().sensors
    assert cpu.current == 41.0
    assert gpu.current is None
    assert gpu.maximum == 60.0


def test_history_only_keeps_the_last_hour(clock):
    monitor = Monitor([FakeSource("a", [[("CPU", 40.0)]])], history_seconds=10, clock=clock)
    for _ in range(5):
        monitor.sample_once()
        clock.advance(4)

    (cpu,) = monitor.snapshot().sensors
    assert len(cpu.history) == 3  # readings at 8, 12 and 16 s; 0 and 4 s are older than 10 s
    assert cpu.minimum == 40.0


def test_reset_statistics(clock):
    monitor = Monitor([FakeSource("a", [[("CPU", 70.0)], [("CPU", 40.0)]])], clock=clock)
    monitor.sample_once()
    monitor.reset_statistics()
    (cpu,) = monitor.snapshot().sensors
    assert (cpu.minimum, cpu.maximum, cpu.average, cpu.history) == (None, None, None, ())

    monitor.sample_once()
    (cpu,) = monitor.snapshot().sensors
    assert (cpu.minimum, cpu.maximum) == (40.0, 40.0)


@pytest.mark.parametrize(
    ("requested", "used"),
    [(0.1, MIN_INTERVAL), (5, 5.0), (10**6, MAX_INTERVAL), (math.nan, DEFAULT_INTERVAL)],
)
def test_interval_is_clamped(requested, used):
    monitor = Monitor([])
    assert monitor.set_interval(requested) == used
    assert monitor.interval == used


def test_logging_appends_csv_rows(clock, tmp_path):
    log_file = tmp_path / "logs" / "temps.csv"
    monitor = Monitor([FakeSource("a", [[("CPU", 40.04), ("GPU", 55.55)]])], clock=clock)
    monitor.sample_once()  # before logging starts: not written
    monitor.start_logging(log_file)
    monitor.sample_once()
    clock.advance(5)
    monitor.sample_once()

    snap = monitor.snapshot()
    assert snap.logging and snap.log_path == log_file and snap.rows_logged == 4
    monitor.stop_logging()
    assert not monitor.snapshot().logging

    rows = list(csv.reader(log_file.open(encoding="utf-8")))
    assert rows[0] == ["timestamp", "sensor", "temperature_c"]
    assert [row[1:] for row in rows[1:]] == [["CPU", "40.0"], ["GPU", "55.5"], ["CPU", "40.0"], ["GPU", "55.5"]]
    assert rows[1][0] == time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(clock.now - 5))


def test_logging_to_an_unwritable_place_raises(tmp_path):
    with pytest.raises(OSError):
        Monitor([]).start_logging(tmp_path)  # a directory, not a file


def test_logging_stops_and_explains_when_a_write_fails(clock, tmp_path):
    monitor = Monitor([FakeSource("a", [[("CPU", 40.0)]])], clock=clock)
    monitor.start_logging(tmp_path / "temps.csv")

    def disk_full(*_args):
        raise OSError(28, "No space left on device")

    monitor._log.write = disk_full
    monitor.sample_once()

    snap = monitor.snapshot()
    assert not snap.logging
    assert "No space left on device" in snap.log_error


def test_revision_changes_with_new_data(clock):
    monitor = Monitor([FakeSource("a", [[("CPU", 40.0)]])], clock=clock)
    before = monitor.revision
    monitor.sample_once()
    assert monitor.revision != before


def test_background_thread_reads_until_stopped():
    source = FakeSource("a", [[("CPU", 40.0)]])
    monitor = Monitor([source], interval=3600)
    monitor.start()
    try:
        assert _wait_for(lambda: monitor.snapshot().rounds == 1)
        monitor.set_interval(1)  # wakes the thread, which reads again straight away
        assert _wait_for(lambda: monitor.snapshot().rounds >= 2)
    finally:
        started = time.monotonic()
        monitor.stop()
    assert not monitor.running
    assert time.monotonic() - started < 2
