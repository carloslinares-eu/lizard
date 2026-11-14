"""The Lizard main window."""

from __future__ import annotations

import logging
import os
import subprocess
import time
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from lizard import __app_name__, __version__
from lizard.core import MAX_INTERVAL, MIN_INTERVAL, Monitor, MonitorSnapshot, Settings
from lizard.core.monitor import clamp_interval
from lizard.core.settings import WARN_RANGE
from lizard.gui.chart import Series, TemperatureChart, series_color
from lizard.gui.icon import load_image
from lizard.gui.widgets import SensorTable
from lizard.utils.formatting import UNIT_SYMBOLS, convert, format_clock, format_interval, to_celsius

log = logging.getLogger(__name__)

POLL_INTERVAL_MS = 250

CHART_LABELS = {5: "Last 5 minutes", 15: "Last 15 minutes", 60: "Last hour"}
NO_SENSORS_MESSAGE = (
    "No temperature sensors found.\n\n"
    "Lizard reads /sys/class/hwmon, /sys/class/thermal and nvidia-smi. Inside virtual machines and containers "
    "these are usually empty. Start Lizard with --demo to try it with simulated sensors."
)

START_COLORS = {"background": "#4CAF50", "activebackground": "#43A047"}
STOP_COLORS = {"background": "#E53935", "activebackground": "#C62828"}
DISABLED_BACKGROUND = "#BDBDBD"
MUTED = "#5F5F5F"
LOGGING = "#2E7D32"
WARNING = "#B26A00"


class MainWindow(ttk.Frame):
    """Sensor table, history chart, options, log file and the Start/Stop logging buttons."""

    def __init__(self, root: tk.Tk | tk.Toplevel, monitor: Monitor, settings: Settings | None = None,
                 on_close: Callable[[], None] | None = None):
        super().__init__(root, padding=(16, 12, 16, 16))
        self.root = root
        self.monitor = monitor
        self.settings = settings or Settings()
        self._on_close_callback = on_close
        self.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=2)

        unit = self.settings.unit
        self.interval_var = tk.IntVar(value=round(self.monitor.interval))
        self.unit_var = tk.StringVar(value=unit)
        self.warn_var = tk.IntVar(value=round(convert(self.settings.warn_celsius, unit)))
        self.chart_var = tk.StringVar(value=CHART_LABELS[self.settings.chart_minutes])
        self.log_file = tk.StringVar(value=self.settings.log_file)

        self._colors: dict[str, str] = {}
        self._rendered_revision = -1
        self._logging_since: float | None = None
        self._log_error_shown: str | None = None
        self._poll_job: str | None = None

        base_font = tkfont.nametofont("TkDefaultFont")
        self._title_font = base_font.copy()
        self._title_font.configure(size=base_font.cget("size") + 6, weight="bold")
        self._bold_font = base_font.copy()
        self._bold_font.configure(weight="bold")

        self._build_header(row=0)
        self._build_sensors(row=1)
        self._build_chart(row=2)
        self._build_options(row=3)
        self._build_log_file(row=4)
        self._build_actions(row=5)

        self._set_logging(False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.update_idletasks()
        root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())
        self._poll()

    # -- layout ------------------------------------------------------------------

    def _build_header(self, row: int) -> None:
        header = ttk.Frame(self)
        header.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(1, weight=1)

        large = self.root.winfo_fpixels("1i") >= 120  # pick the sharper logo on high-DPI screens
        self._logo = load_image("lizard-64.png" if large else "lizard-48.png", master=self.root)
        if self._logo is not None:
            ttk.Label(header, image=self._logo).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ttk.Label(header, text=__app_name__, font=self._title_font).grid(row=0, column=1, sticky="sw")
        self.version_label = ttk.Label(header, text=f"v{__version__}", foreground=MUTED)
        self.version_label.grid(row=0, column=2, sticky="ne")
        ttk.Label(
            header,
            text="Watches your computer's temperature sensors, charts them live and logs them to a CSV file.",
            foreground=MUTED,
        ).grid(row=1, column=1, columnspan=2, sticky="nw")

    def _build_sensors(self, row: int) -> None:
        box = ttk.LabelFrame(self, text="Sensors", padding=10)
        box.grid(row=row, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        self.sensor_table = SensorTable(box, height=5, on_select=self._refresh)
        self.sensor_table.grid(row=0, column=0, sticky="nsew")

        bar = ttk.Frame(box)
        bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(bar, text="Select sensors to chart only those; Esc shows all of them again.",
                  foreground=MUTED).pack(side="left")
        self.reset_button = ttk.Button(bar, text="Reset statistics", command=self._reset_statistics)
        self.reset_button.pack(side="right")

    def _build_chart(self, row: int) -> None:
        box = ttk.LabelFrame(self, text="History", padding=10)
        box.grid(row=row, column=0, sticky="nsew", pady=(10, 0))
        box.columnconfigure(0, weight=1)
        box.rowconfigure(1, weight=1)

        bar = ttk.Frame(box)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.chart_caption = ttk.Label(bar, foreground=MUTED)
        self.chart_caption.pack(side="left")
        self.chart_choice = ttk.Combobox(bar, textvariable=self.chart_var, values=list(CHART_LABELS.values()),
                                         state="readonly", width=16)
        self.chart_choice.pack(side="right")
        self.chart_choice.bind("<<ComboboxSelected>>", self._change_chart_window)
        ttk.Label(bar, text="Show:").pack(side="right", padx=(0, 6))

        self.chart = TemperatureChart(box, height=220)
        self.chart.grid(row=1, column=0, sticky="nsew")

    def _build_options(self, row: int) -> None:
        box = ttk.Frame(self)
        box.grid(row=row, column=0, sticky="ew", pady=(10, 0))

        ttk.Label(box, text="Read every").pack(side="left")
        self.interval_spinbox = ttk.Spinbox(box, from_=MIN_INTERVAL, to=MAX_INTERVAL, increment=1, width=5,
                                            textvariable=self.interval_var, command=self._apply_interval)
        self.interval_spinbox.pack(side="left", padx=(6, 4))
        ttk.Label(box, text="seconds").pack(side="left", padx=(0, 18))

        ttk.Label(box, text="Warn at").pack(side="left")
        self.warn_spinbox = ttk.Spinbox(box, increment=1, width=5, textvariable=self.warn_var,
                                        command=self._apply_warning)
        self.warn_spinbox.pack(side="left", padx=(6, 4))
        self.warn_unit_label = ttk.Label(box, text=UNIT_SYMBOLS[self.unit_var.get()])
        self.warn_unit_label.pack(side="left", padx=(0, 18))

        ttk.Label(box, text="Units:").pack(side="left")
        for unit in UNIT_SYMBOLS:
            ttk.Radiobutton(box, text=UNIT_SYMBOLS[unit], value=unit, variable=self.unit_var,
                            command=self._change_unit).pack(side="left", padx=(6, 0))

        for spinbox, apply in ((self.interval_spinbox, self._apply_interval), (self.warn_spinbox, self._apply_warning)):
            spinbox.bind("<Return>", apply)
            spinbox.bind("<FocusOut>", apply)
        self._configure_warning_range()

    def _build_log_file(self, row: int) -> None:
        box = ttk.LabelFrame(self, text="Log file", padding=10)
        box.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        box.columnconfigure(0, weight=1)
        ttk.Entry(box, textvariable=self.log_file, state="readonly").grid(row=0, column=0, sticky="ew")
        self.choose_button = ttk.Button(box, text="Choose…", command=self._choose_log_file)
        self.choose_button.grid(row=0, column=1, padx=(6, 0))
        self.open_button = ttk.Button(box, text="Open", command=self._open_log_file)
        self.open_button.grid(row=0, column=2, padx=(6, 0))
        # width=1 stops long text from widening the window; the grid stretches the label instead.
        self.log_status = ttk.Label(box, width=1)
        self.log_status.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    def _build_actions(self, row: int) -> None:
        bar = ttk.Frame(self)
        bar.grid(row=row, column=0, sticky="ew", pady=(12, 0))
        bar.columnconfigure(0, weight=1)

        self.status_text = tk.StringVar()
        self.problem_text = tk.StringVar()
        ttk.Label(bar, textvariable=self.status_text, width=1).grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, textvariable=self.problem_text, foreground=WARNING, width=1).grid(row=1, column=0, sticky="ew")

        button_style = {
            "foreground": "white",
            "disabledforeground": "#F5F5F5",
            "activeforeground": "white",
            "font": self._bold_font,
            "relief": "flat",
            "borderwidth": 0,
            "highlightthickness": 0,
            "padx": 16,
            "pady": 6,
            "cursor": "hand2",
        }
        self.start_button = tk.Button(bar, text="Start logging", command=self._start_logging, **button_style)
        self.start_button.grid(row=0, column=1, rowspan=2, padx=(12, 0))
        self.stop_button = tk.Button(bar, text="Stop logging", command=self._stop_logging, **button_style)
        self.stop_button.grid(row=0, column=2, rowspan=2, padx=(8, 0))

    # -- showing the monitor's state ---------------------------------------------

    def _poll(self) -> None:
        if self.monitor.revision != self._rendered_revision:
            self._refresh()
        self._poll_job = self.after(POLL_INTERVAL_MS, self._poll)

    def _refresh(self) -> None:
        self._rendered_revision = self.monitor.revision
        self.render(self.monitor.snapshot())

    def render(self, snap: MonitorSnapshot) -> None:
        unit = self.unit_var.get()
        for sensor in snap.sensors:
            if sensor.name not in self._colors:
                self._colors[sensor.name] = series_color(len(self._colors))
        self.sensor_table.update_rows(snap.sensors, self._colors, unit, self.settings.warn_celsius)

        selected = set(self.sensor_table.selected)
        charted = [sensor for sensor in snap.sensors if not selected or sensor.name in selected]
        self.chart.plot(
            [Series(sensor.name, self._colors[sensor.name], [(when, convert(celsius, unit))
                                                             for when, celsius in sensor.history])
             for sensor in charted],
            window=self.settings.chart_minutes * 60,
            now=snap.last_reading,
            unit=UNIT_SYMBOLS[unit],
            threshold=convert(self.settings.warn_celsius, unit),
            max_gap=snap.interval * 3 + 1,
            message="" if self.monitor.sources else NO_SENSORS_MESSAGE,
        )
        total = len(snap.sensors)
        if not total:
            caption = ""
        elif selected:
            caption = f"{len(charted)} of {total} sensors"
        else:
            caption = "1 sensor" if total == 1 else f"All {total} sensors"
        self.chart_caption.configure(text=caption)

        if not self.monitor.sources:
            status = "No temperature sensors found."
        elif snap.last_reading is None:
            status = "Reading the sensors…"
        else:
            status = (f"Last reading {format_clock(snap.last_reading)}  ·  {total} sensor{'s' if total != 1 else ''}"
                      f"  ·  every {format_interval(snap.interval)}")
        self.status_text.set(status)
        self.problem_text.set(f"⚠ {'   '.join(snap.problems)}" if snap.problems else "")

        if snap.log_error and snap.log_error != self._log_error_shown:
            self._log_error_shown = snap.log_error
            self._set_logging(False)
            messagebox.showerror("Logging stopped", snap.log_error, parent=self.root)
        if snap.logging:
            since = f" since {format_clock(self._logging_since)}" if self._logging_since else ""
            self.log_status.configure(text=f"Logging{since}  ·  {snap.rows_logged:,} rows written",
                                      foreground=LOGGING)
        else:
            self.log_status.configure(text="Not logging. While logging is on, every reading is added to this file.",
                                      foreground=MUTED)

    # -- user actions ------------------------------------------------------------

    def _apply_interval(self, _event: tk.Event | None = None) -> None:
        try:
            seconds = clamp_interval(float(self.interval_var.get()))
        except (tk.TclError, ValueError):
            seconds = self.monitor.interval
        if seconds != self.monitor.interval:
            self.monitor.set_interval(seconds)
        self.interval_var.set(round(seconds))
        self.settings.interval = seconds

    def _apply_warning(self, _event: tk.Event | None = None) -> None:
        unit = self.unit_var.get()
        try:
            celsius = to_celsius(float(self.warn_var.get()), unit)
        except (tk.TclError, ValueError):
            celsius = self.settings.warn_celsius
        self.settings.warn_celsius = max(WARN_RANGE[0], min(WARN_RANGE[1], celsius))
        self.warn_var.set(round(convert(self.settings.warn_celsius, unit)))
        self._refresh()

    def _change_unit(self) -> None:
        unit = self.unit_var.get()
        self.settings.unit = unit
        self.warn_unit_label.configure(text=UNIT_SYMBOLS[unit])
        self._configure_warning_range()
        self.warn_var.set(round(convert(self.settings.warn_celsius, unit)))
        self._refresh()

    def _configure_warning_range(self) -> None:
        unit = self.unit_var.get()
        self.warn_spinbox.configure(from_=round(convert(WARN_RANGE[0], unit)), to=round(convert(WARN_RANGE[1], unit)))

    def _change_chart_window(self, _event: tk.Event | None = None) -> None:
        label = self.chart_var.get()
        self.settings.chart_minutes = next(minutes for minutes, text in CHART_LABELS.items() if text == label)
        self.chart_choice.selection_clear()
        self._refresh()

    def _reset_statistics(self) -> None:
        self.monitor.reset_statistics()
        self._refresh()

    def _choose_log_file(self) -> None:
        current = Path(self.log_file.get()).expanduser()
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Choose the log file", initialdir=str(current.parent), initialfile=current.name,
            defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*")],
            confirmoverwrite=False,  # new readings are appended, nothing is overwritten
        )
        if path:
            self.log_file.set(os.path.normpath(path))
            self.settings.log_file = self.log_file.get()

    def _open_log_file(self) -> None:
        path = Path(self.log_file.get()).expanduser()
        if not path.exists():
            messagebox.showinfo("Nothing logged yet", f"{path}\n\ndoesn't exist yet. Start logging to create it.",
                                parent=self.root)
            return
        try:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError as exc:
            messagebox.showerror("Can't open the log file", f"{path}\n\n{exc.strerror or exc}", parent=self.root)

    def _start_logging(self) -> None:
        path = self.log_file.get()
        try:
            self.monitor.start_logging(path)
        except OSError as exc:
            messagebox.showerror("Can't start logging", f"Lizard can't write to\n{path}\n\n{exc.strerror or exc}",
                                 parent=self.root)
            return
        self._logging_since = time.time()
        self._set_logging(True)
        self._refresh()

    def _stop_logging(self) -> None:
        self.monitor.stop_logging()
        self._set_logging(False)
        self._refresh()

    def _on_close(self) -> None:
        snap = self.monitor.snapshot()
        if snap.logging and not messagebox.askyesno(
            f"Quit {__app_name__}?",
            f"Lizard is logging temperatures to\n{snap.log_path}\n\nStop logging and quit?",
            parent=self.root,
        ):
            return
        self.monitor.stop_logging()
        if self._on_close_callback is not None:
            self._on_close_callback()
        self.root.destroy()

    def destroy(self) -> None:
        if self._poll_job is not None:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        super().destroy()

    # -- state -------------------------------------------------------------------

    def _set_logging(self, logging_on: bool) -> None:
        self.start_button.configure(
            state="disabled" if logging_on else "normal",
            background=DISABLED_BACKGROUND if logging_on else START_COLORS["background"],
            activebackground=START_COLORS["activebackground"],
        )
        self.stop_button.configure(
            state="normal" if logging_on else "disabled",
            background=STOP_COLORS["background"] if logging_on else DISABLED_BACKGROUND,
            activebackground=STOP_COLORS["activebackground"],
        )
        self.choose_button.configure(state="disabled" if logging_on else "normal")
        if not logging_on:
            self._logging_since = None
