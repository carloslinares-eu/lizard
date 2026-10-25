"""Human-friendly formatting of temperatures, times and intervals."""

from __future__ import annotations

import time

UNIT_SYMBOLS = {"C": "°C", "F": "°F"}
MISSING = "—"


def convert(celsius: float, unit: str) -> float:
    """Express a Celsius temperature in ``unit`` (``'C'`` or ``'F'``)."""
    return celsius * 9 / 5 + 32 if unit == "F" else celsius


def to_celsius(value: float, unit: str) -> float:
    """The inverse of :func:`convert`."""
    return (value - 32) * 5 / 9 if unit == "F" else value


def format_temperature(celsius: float | None, unit: str = "C", decimals: int = 1) -> str:
    """``format_temperature(45.25)`` -> ``'45.2 °C'``; unknown values give a dash.

    >>> format_temperature(100, "F")
    '212.0 °F'
    """
    if celsius is None:
        return MISSING
    return f"{convert(celsius, unit):.{decimals}f} {UNIT_SYMBOLS[unit]}"


def format_clock(timestamp: float) -> str:
    """Local time of day, e.g. ``'18:55:03'``."""
    return time.strftime("%H:%M:%S", time.localtime(timestamp))


def format_interval(seconds: float) -> str:
    """``5`` -> ``'5 s'``, ``90`` -> ``'1 min 30 s'``, ``3600`` -> ``'1 h'``."""
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    parts = [f"{value} {unit}" for value, unit in ((hours, "h"), (minutes, "min"), (secs, "s")) if value]
    return " ".join(parts) or "0 s"
