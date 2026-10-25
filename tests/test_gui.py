"""Smoke tests for the window. Skipped where no display is available (use ``xvfb-run pytest`` on a server)."""

from __future__ import annotations

import tkinter as tk

import pytest

from lizard import __version__
from lizard.core import Monitor, Settings
from tests.conftest import FakeSource


@pytest.fixture(scope="module")
def tk_root():
    # One Tk interpreter per process: creating a second one can fail to find tk.tcl in some virtualenvs.
    try:
        interpreter = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    interpreter.withdraw()
    yield interpreter
    interpreter.destroy()


@pytest.fixture
def root(tk_root):
    window = tk.Toplevel(tk_root)
    yield window
    window.destroy()


@pytest.fixture
def monitor(clock):
    source = FakeSource("hwmon", [[("CPU Package id 0", 45.0), ("NVMe Composite", 38.0), ("GPU edge", 82.0)],
                                  [("CPU Package id 0", 55.0), ("NVMe Composite", 39.0), ("GPU edge", 84.0)]])
    monitor = Monitor([source], clock=clock)
    for _ in range(2):
        monitor.sample_once()
        clock.advance(5)
    return monitor


def _window(root, monitor, **settings):
    from lizard.gui.main_window import MainWindow

    window = MainWindow(root, monitor, Settings(**settings))
    root.geometry("900x760")
    root.update()
    window.chart.redraw()
    return window


def _row(window, name):
    tree = window.sensor_table.tree
    return tree.item(name, "values"), tree.item(name, "tags")


def test_header_shows_the_version(root, monitor):
    window = _window(root, monitor)
    assert window.version_label.cget("text") == f"v{__version__}"


def test_table_chart_and_status(root, monitor):
    window = _window(root, monitor)

    assert window.sensor_table.tree.get_children() == ("CPU Package id 0", "NVMe Composite", "GPU edge")
    values, tags = _row(window, "CPU Package id 0")
    assert values[:4] == ("55.0 °C", "45.0 °C", "55.0 °C", "50.0 °C")
    assert values[4] == "hwmon"
    assert _row(window, "GPU edge")[1] == ("hot",)  # at or above the default 80 °C
    assert tags == ""

    assert len(window.chart.find_withtag("series")) == 3
    assert window.chart_caption.cget("text") == "All 3 sensors"
    assert window.status_text.get().startswith("Last reading ")
    assert "3 sensors  ·  every 5 s" in window.status_text.get()


def test_selecting_sensors_limits_the_chart(root, monitor):
    window = _window(root, monitor)
    window.sensor_table.tree.selection_set("NVMe Composite")
    root.update()
    assert len(window.chart.find_withtag("series")) == 1
    assert window.chart_caption.cget("text") == "1 of 3 sensors"

    window.sensor_table.clear_selection()
    root.update()
    assert len(window.chart.find_withtag("series")) == 3


def test_fahrenheit(root, monitor):
    window = _window(root, monitor)
    window.unit_var.set("F")
    window._change_unit()

    assert _row(window, "CPU Package id 0")[0][0] == "131.0 °F"
    assert window.warn_var.get() == 176
    assert window.warn_unit_label.cget("text") == "°F"
    assert window.settings.unit == "F"


def test_warning_threshold(root, monitor):
    window = _window(root, monitor)
    window.warn_var.set(50)
    window._apply_warning()
    assert window.settings.warn_celsius == 50
    assert _row(window, "CPU Package id 0")[1] == ("hot",)

    window.warn_var.set(5)  # below the allowed range
    window._apply_warning()
    assert window.settings.warn_celsius == 20


def test_interval_box(root, monitor):
    window = _window(root, monitor)
    window.interval_var.set(0)
    window._apply_interval()
    assert monitor.interval == 1
    assert window.interval_var.get() == 1
    assert window.settings.interval == 1


def test_start_and_stop_logging(root, monitor, tmp_path):
    window = _window(root, monitor)
    log_file = tmp_path / "temps.csv"
    window.log_file.set(str(log_file))

    window._start_logging()
    assert monitor.snapshot().logging
    assert str(window.start_button.cget("state")) == "disabled"
    assert str(window.stop_button.cget("state")) == "normal"

    monitor.sample_once()
    window._refresh()
    assert "3 rows written" in window.log_status.cget("text")

    window._stop_logging()
    assert not monitor.snapshot().logging
    assert str(window.start_button.cget("state")) == "normal"
    assert len(log_file.read_text(encoding="utf-8").splitlines()) == 4


def test_without_sensors(root):
    window = _window(root, Monitor([]))
    assert window.status_text.get() == "No temperature sensors found."
    message = window.chart.find_withtag("message")
    assert message and "--demo" in window.chart.itemcget(message[0], "text")


def test_source_problems_are_shown(root, clock):
    monitor = Monitor([FakeSource("nvidia-smi", [OSError("nvidia-smi vanished")])], clock=clock)
    monitor.sample_once()
    window = _window(root, monitor)
    assert window.problem_text.get() == "⚠ nvidia-smi: nvidia-smi vanished"
