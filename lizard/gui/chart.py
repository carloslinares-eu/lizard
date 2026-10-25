"""A line chart of recent temperatures, drawn on a Tk canvas."""

from __future__ import annotations

import math
import time
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Sequence
from dataclasses import dataclass

# Distinguishable colors (Tableau 10); the sensor table shows the same ones as swatches.
PALETTE = ("#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
           "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC")
TIME_STEPS = (15, 30, 60, 120, 300, 600, 900, 1800, 3600)  # seconds between time labels
MAX_TIME_LABELS = 8
MIN_DEGREES_SHOWN = 10.0  # so a steady sensor isn't drawn as wild zig-zags


def series_color(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def nice_step(span: float, target: int = 5) -> float:
    """A round step (1, 2 or 5 times a power of ten) that splits ``span`` into about ``target`` parts."""
    raw = max(span, 1e-9) / target
    magnitude = 10 ** math.floor(math.log10(raw))
    for multiple in (1, 2, 5):
        if multiple * magnitude >= raw:
            return multiple * magnitude
    return 10 * magnitude


def value_range(values: Sequence[float], minimum_span: float = MIN_DEGREES_SHOWN) -> tuple[float, float, float]:
    """Axis limits and gridline step that cover ``values`` with round numbers."""
    low, high = min(values), max(values)
    if high - low < minimum_span:
        middle = (low + high) / 2
        low, high = middle - minimum_span / 2, middle + minimum_span / 2
    step = nice_step(high - low)
    return math.floor(low / step) * step, math.ceil(high / step) * step, step


def time_step(window: float) -> int:
    """Seconds between time labels for a chart spanning ``window`` seconds."""
    return next((step for step in TIME_STEPS if window / step <= MAX_TIME_LABELS), TIME_STEPS[-1])


@dataclass(frozen=True, slots=True)
class Series:
    name: str
    color: str
    points: Sequence[tuple[float, float]]  # (UNIX time, value in the display unit), oldest first


class TemperatureChart(tk.Canvas):
    """Plots :class:`Series` over the last ``window`` seconds, with gridlines and a dashed warning line."""

    BACKGROUND = "#FFFFFF"
    PLOT_BACKGROUND = "#FBFBFB"
    GRID = "#E6E6E6"
    BORDER = "#BDBDBD"
    TEXT = "#5F5F5F"
    WARN = "#E53935"

    def __init__(self, master: tk.Misc, height: int = 220, **kwargs):
        super().__init__(master, height=height, background=self.BACKGROUND, highlightthickness=0, borderwidth=0,
                         **kwargs)
        self._font = tkfont.nametofont("TkDefaultFont")
        self._series: Sequence[Series] = ()
        self._window = 900.0
        self._now: float | None = None
        self._unit = "°C"
        self._threshold: float | None = None
        self._max_gap: float | None = None
        self._message = ""
        self.bind("<Configure>", lambda _event: self.redraw())

    def plot(self, series: Sequence[Series], *, window: float, now: float | None = None, unit: str = "°C",
             threshold: float | None = None, max_gap: float | None = None, message: str = "") -> None:
        """Replace what is shown. Lines break where readings are more than ``max_gap`` seconds apart."""
        self._series, self._window, self._now = series, float(window), now
        self._unit, self._threshold, self._max_gap, self._message = unit, threshold, max_gap, message
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        digit = self._font.measure("0")
        linespace = self._font.metrics("linespace")
        x0, y0 = digit * 7, linespace // 2 + 4
        x1, y1 = width - digit * 2, height - linespace - 8
        if x1 - x0 < 60 or y1 - y0 < 40:
            return

        now = self._now if self._now is not None else time.time()
        start = now - self._window
        visible = [(series, [point for point in series.points if start <= point[0] <= now])
                   for series in self._series]
        values = [value for _series, points in visible for _time, value in points]

        self.create_rectangle(x0, y0, x1, y1, fill=self.PLOT_BACKGROUND, outline="")

        def x_of(when: float) -> float:
            return x0 + (when - start) / self._window * (x1 - x0)

        self._draw_time_axis(start, now, x_of, y0, y1)
        if not values:
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=self._message or "Waiting for the first reading…",
                             fill=self.TEXT, font=self._font, justify="center", width=x1 - x0 - 40, tags=("message",))
            self.create_rectangle(x0, y0, x1, y1, outline=self.BORDER)
            return

        low, high, step = value_range(values)

        def y_of(value: float) -> float:
            return y1 - (value - low) / (high - low) * (y1 - y0)

        for i in range(round((high - low) / step) + 1):
            value = low + i * step
            y = y_of(value)
            if 0 < i < round((high - low) / step):
                self.create_line(x0, y, x1, y, fill=self.GRID)
            self.create_text(x0 - digit, y, text=f"{value:g}{self._unit}", anchor="e", fill=self.TEXT,
                             font=self._font)

        if self._threshold is not None and low <= self._threshold <= high:
            y = y_of(self._threshold)
            self.create_line(x0, y, x1, y, fill=self.WARN, dash=(6, 4), tags=("threshold",))
            self.create_text(x1 - digit, y - 2, text=f"warn {self._threshold:g}{self._unit}", anchor="se",
                             fill=self.WARN, font=self._font, tags=("threshold",))

        for series, points in visible:
            segment: list[float] = []
            previous: float | None = None
            for when, value in points:
                if previous is not None and self._max_gap is not None and when - previous > self._max_gap:
                    self._draw_segment(segment, series.color)
                    segment = []
                segment += (x_of(when), y_of(value))
                previous = when
            self._draw_segment(segment, series.color)

        self.create_rectangle(x0, y0, x1, y1, outline=self.BORDER)

    def _draw_time_axis(self, start: float, now: float, x_of, y0: float, y1: float) -> None:
        """Vertical gridlines on round local times (every minute, 2 minutes, 10 minutes, …)."""
        step = time_step(self._window)
        offset = time.localtime(now).tm_gmtoff
        tick = math.ceil((start + offset) / step) * step - offset
        while tick <= now:
            x = x_of(tick)
            self.create_line(x, y0, x, y1, fill=self.GRID)
            self.create_text(x, y1 + 4, text=time.strftime("%H:%M", time.localtime(tick)), anchor="n",
                             fill=self.TEXT, font=self._font)
            tick += step

    def _draw_segment(self, coords: list[float], color: str) -> None:
        if len(coords) >= 4:
            self.create_line(*coords, fill=color, width=2, joinstyle="round", capstyle="round", tags=("series",))
        elif len(coords) == 2:  # a single reading: draw a dot
            x, y = coords
            self.create_oval(x - 2.5, y - 2.5, x + 2.5, y + 2.5, fill=color, outline=color, tags=("series",))
