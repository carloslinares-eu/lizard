"""The table of sensors with their current, lowest, highest and average temperatures."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable, Mapping, Sequence
from tkinter import ttk

from lizard.core.models import SensorState
from lizard.utils.formatting import format_temperature


class SensorTable(ttk.Frame):
    """One row per sensor, with a color swatch matching its line in the chart.

    Rows at or above the warning temperature turn red; sensors missing from the
    latest reading are greyed out. Ctrl/Shift-click selects several rows.
    """

    COLUMNS = (("now", "Now", 90), ("min", "Lowest", 90), ("max", "Highest", 90), ("avg", "Average", 90),
               ("source", "Source", 110))
    HOT = "#C62828"
    STALE = "#9E9E9E"

    def __init__(self, master: tk.Misc, height: int = 6, on_select: Callable[[], None] | None = None):
        super().__init__(master)
        self._on_select = on_select
        self._swatches: dict[str, tk.PhotoImage] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(self, columns=[key for key, _title, _width in self.COLUMNS], height=height,
                                 selectmode="extended")
        self.tree.heading("#0", text="Sensor", anchor="w")
        self.tree.column("#0", width=260, minwidth=160, stretch=True)
        for key, title, width in self.COLUMNS:
            anchor = "w" if key == "source" else "e"
            self.tree.heading(key, text=title, anchor=anchor)
            self.tree.column(key, width=width, minwidth=60, anchor=anchor, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        self._bold = tkfont.nametofont("TkDefaultFont").copy()
        self._bold.configure(weight="bold")
        self.tree.tag_configure("hot", foreground=self.HOT, font=self._bold)
        self.tree.tag_configure("stale", foreground=self.STALE)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._selection_changed())
        self.tree.bind("<Escape>", lambda _event: self.clear_selection())

    @property
    def selected(self) -> list[str]:
        """Names of the highlighted sensors."""
        return list(self.tree.selection())

    def clear_selection(self) -> None:
        self.tree.selection_remove(*self.tree.selection())

    def update_rows(self, sensors: Sequence[SensorState], colors: Mapping[str, str], unit: str,
                    warn_celsius: float) -> None:
        """Show ``sensors`` in this order, adding and removing rows as needed."""
        wanted = set()
        for sensor in sensors:
            values = (
                format_temperature(sensor.current, unit),
                format_temperature(sensor.minimum, unit),
                format_temperature(sensor.maximum, unit),
                format_temperature(sensor.average, unit),
                sensor.source,
            )
            if sensor.current is None:
                tags: tuple[str, ...] = ("stale",)
            elif sensor.current >= warn_celsius:
                tags = ("hot",)
            else:
                tags = ()
            image = self._swatch(colors.get(sensor.name, self.STALE))
            if self.tree.exists(sensor.name):
                self.tree.item(sensor.name, values=values, tags=tags, image=image)
            else:
                self.tree.insert("", "end", iid=sensor.name, text=f" {sensor.name}", values=values, tags=tags,
                                 image=image)
            wanted.add(sensor.name)
        for iid in self.tree.get_children():
            if iid not in wanted:
                self.tree.delete(iid)

    def _swatch(self, color: str) -> tk.PhotoImage:
        if color not in self._swatches:
            size = max(10, tkfont.nametofont("TkDefaultFont").metrics("linespace") - 4)
            image = tk.PhotoImage(master=self, width=size, height=size)
            image.put(color, to=(1, 1, size - 1, size - 1))  # leave a transparent 1 px border
            self._swatches[color] = image
        return self._swatches[color]

    def _selection_changed(self) -> None:
        if self._on_select is not None:
            self._on_select()
