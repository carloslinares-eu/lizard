from __future__ import annotations

import pytest

from lizard.gui.chart import nice_step, series_color, time_step, value_range
from lizard.utils.formatting import convert, format_interval, format_temperature, to_celsius


@pytest.mark.parametrize(
    ("celsius", "unit", "expected"),
    [(45.25, "C", "45.2 °C"), (45.26, "C", "45.3 °C"), (100, "F", "212.0 °F"), (-40, "F", "-40.0 °F"),
     (None, "C", "—")],
)
def test_format_temperature(celsius, unit, expected):
    assert format_temperature(celsius, unit) == expected


def test_conversion_round_trips():
    assert convert(37, "F") == pytest.approx(98.6)
    assert to_celsius(98.6, "F") == pytest.approx(37)
    assert convert(37, "C") == to_celsius(37, "C") == 37


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(5, "5 s"), (60, "1 min"), (90, "1 min 30 s"), (3600, "1 h"), (3725, "1 h 2 min 5 s"), (0, "0 s")],
)
def test_format_interval(seconds, expected):
    assert format_interval(seconds) == expected


@pytest.mark.parametrize(("span", "step"), [(10, 2), (12, 5), (30, 10), (3, 1), (0.8, 0.2)])
def test_nice_step(span, step):
    assert nice_step(span) == pytest.approx(step)


def test_value_range_is_at_least_ten_degrees_on_round_numbers():
    assert value_range([45.2, 45.6]) == (40, 52, 2)
    assert value_range([31.0, 88.0]) == (20, 100, 20)


@pytest.mark.parametrize(("window", "step"), [(300, 60), (900, 120), (3600, 600)])
def test_time_step(window, step):
    assert time_step(window) == step


def test_series_colors_cycle():
    assert series_color(0) != series_color(1)
    assert series_color(0) == series_color(10)
