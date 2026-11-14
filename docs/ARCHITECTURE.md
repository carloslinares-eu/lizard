# Architecture

Lizard is split into a GUI-free **core** that reads and records temperatures,
a Tkinter **gui** that shows them, and a small **cli** for headless logging.
The core can be used from scripts or tests without a display.

```text
lizard/
├── app.py            main(): parses --demo, loads settings, Tk root, theme, icon, MainWindow
├── cli.py            lizard-log: the same Monitor, driven by a simple loop instead of a thread
├── core/
│   ├── sensors/
│   │   ├── __init__.py   SensorSource protocol, discover_sources()
│   │   ├── sysfs.py      HwmonSource, ThermalZoneSource
│   │   ├── nvidia.py     NvidiaSmiSource
│   │   ├── demo.py       DemoSource
│   │   └── base.py       SensorError
│   ├── monitor.py    Monitor: reading thread, names, history, statistics, logging
│   ├── csvlog.py     CsvLog: appends rows, flushes every round
│   ├── settings.py   Settings: JSON in ~/.config/lizard, validated on load
│   └── models.py     Reading, SensorState, MonitorSnapshot
├── gui/
│   ├── main_window.py    layout, polling the monitor, user actions
│   ├── chart.py          TemperatureChart (Tk canvas) and axis helpers
│   ├── widgets.py        SensorTable (ttk.Treeview with color swatches)
│   └── icon.py           window icon and bundled images
└── utils/
    └── formatting.py  temperatures, units, clock times, intervals
```

## Threads

```text
 GUI thread (Tk mainloop)                monitor thread
 ────────────────────────                ──────────────
 app.main ─► Monitor(sources)
             monitor.start() ──────────► loop:
                                           read every source (outside the lock)
                                           lock: record values, update statistics,
                                                 write the CSV round, revision += 1
                                           wait(interval) on an Event
 every 250 ms:
   monitor.revision changed? ── no ──► nothing to do
   yes: monitor.snapshot() ◄── lock ──
        render table, chart, status
 interval box ─► set_interval() ── Event.set() ──► wakes up, reads at once
 Start logging ─► start_logging(path)  (opens the file here, so errors reach the user)
 close window ─► stop_logging(); after mainloop: monitor.stop()
```

- **The GUI thread** never reads sensors or writes the log. It polls the monitor
  with `after()` and only builds a snapshot when `revision` has changed, so an
  idle window costs almost nothing. Tkinter isn't thread-safe, so nothing else
  calls into Tk.
- **The monitor thread** reads the sources without holding the lock, since
  `nvidia-smi` can take a moment, then records everything in one locked step.
  Its wait is an `Event`, so a new interval or `stop()` takes effect immediately.
  The time spent reading is subtracted from the wait so readings don't drift.
- **`lizard-log`** uses the same `Monitor` but calls `sample_once()` from its own
  loop, so the window and the command can never disagree on names or formats.

## Sensor sources

A source is anything with a `name` and a `read()` method returning
`list[Reading]`. `read()` may raise `OSError` or `SensorError`; the monitor
records the message under the source's name, shows it in the status line, keeps
the other sources going, and clears it once the source reads again.

- **`HwmonSource`** walks `/sys/class/hwmon/hwmon*` in natural order (`hwmon2`
  before `hwmon10`). For every `tempN_input` it reads millidegrees, takes the
  label from `tempN_label` (or uses `tempN`), and prefixes a friendly name for
  the driver from `name` (`coretemp` → `CPU`). Unreadable files are skipped:
  drivers return errors for sensors that are powered down. Values outside
  −60…150 °C are treated as disconnected inputs. Very old drivers keep their
  attributes in `hwmonN/device/`, which is checked too.
- **`ThermalZoneSource`** reads `/sys/class/thermal/thermal_zone*/temp` and
  `type`. `discover_sources()` only uses it when hwmon has no temperatures,
  because the kernel usually exposes the same sensors through both.
- **`NvidiaSmiSource`** runs
  `nvidia-smi --query-gpu=index,name,temperature.gpu --format=csv,noheader,nounits`
  with a 5 s timeout. The proprietary driver doesn't register with hwmon, so this
  is the only way to see those GPUs. GPUs reporting `[N/A]` are skipped.
- **`DemoSource`** produces smooth sine waves with a little noise from a clock and
  a seed, so it is deterministic in tests and screenshots.

`discover_sources()` keeps only sources that return at least one reading at
start-up, so the window never shows an empty source.

### Adding a source

Write a class with `name` and `read()`, add it to `discover_sources()`, and test it
against fake data (see `tests/test_sysfs.py` for building a fake sysfs tree in a
temporary folder, and `tests/test_nvidia_and_demo.py` for faking a command).

## Naming and statistics

Each reading is keyed by `(source, label, occurrence)`, where *occurrence* counts
identical labels within one round. The first time a key is seen it gets a display
name that no other sensor has (`NVMe Composite`, then `NVMe Composite (2)`), and
it keeps that name for the rest of the session. Display order is the order in
which sensors were first seen, which is stable because sources sort what they read.

Every sensor keeps its count, sum, minimum and maximum since the last reset, plus
a `deque` of `(time, °C)` pairs no older than an hour, the longest chart window.
A sensor that is missing from a round keeps its statistics but its `current`
becomes `None`, which the table shows greyed out.

## The chart

`TemperatureChart` is a plain `tk.Canvas` that redraws everything on each update
or resize; even an hour of one-second readings for ten sensors is only a few
thousand points. The vertical range comes from `value_range()`: at least 10 °C,
padded to multiples of a 1-2-5 step. Time gridlines fall on round local times
(the step is the smallest of 15 s … 1 h that gives at most eight labels). Lines
are split where consecutive readings are more than three intervals apart. The
window converts values to the display unit before plotting, so the chart doesn't
know about units beyond the label.

## Logging

`CsvLog` opens the file in append mode and writes the header only when the file
is new or empty. Each round is written with `csv.writer` and flushed at once, so
a crash loses at most the round being written. `Monitor.start_logging()` opens
the file on the caller's thread, so a bad path raises straight into the GUI or
CLI. A write error later on (disk full, drive removed) closes the log and sets
`log_error`, which the window shows once in a dialog and the CLI prints before
exiting with status 1.

## Settings

`Settings.load()` reads `~/.config/lizard/settings.json` (honoring
`XDG_CONFIG_HOME`) and validates every field independently: a wrong type or an
out-of-range value falls back to its default or is clamped, unknown keys are
ignored, and an unreadable file gives the defaults. `save()` writes a temporary
file and renames it, so the settings file is never half-written.

## Tests

`tests/` uses pytest and runs anywhere, including on non-Linux development machines:

- the sysfs sources read fake `/sys/class` trees built in a temporary folder;
- `nvidia-smi` is replaced with a fake runner;
- the monitor tests use a fake clock and fake sources, plus one test of the real
  background thread;
- the CLI tests run `main()` with the demo source;
- the GUI tests build the real window and are skipped when no display is
  available (`xvfb-run -a pytest` provides one on a server);
- `test_project.py` checks that `__version__`, the changelog, `pyproject.toml`, the
  icons and the `.desktop` file agree.

GitHub Actions runs the suite on Ubuntu with Python 3.10, 3.12 and 3.13 under
Xvfb, tries `lizard-log`, and builds the PyInstaller binary.
