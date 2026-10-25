![Lizard icon: a gecko basking on a warm background](lizard/assets/lizard-64.png)

# Lizard

Watches the temperature sensors of a Linux computer, charts them live and logs them to a CSV file.

![The Lizard window, here with the simulated demo sensors](docs/images/screenshot.png)

Lizard finds every temperature sensor the kernel knows about (CPU package and
cores, NVMe drives, GPU, chipset, Wi-Fi card…) plus NVIDIA GPUs, and shows them
in one window: what each one reads now, its lowest, highest and average, and a
chart of the last few minutes or hour. Press **Start logging** to record every
reading in a CSV file you can open in a spreadsheet. On a server, `lizard-log`
does the logging without a window.

## Features

- **Every sensor, no setup.** Reads `/sys/class/hwmon` directly, the same data
  `lm-sensors` shows, without needing the `sensors` command. NVIDIA GPUs are
  read through `nvidia-smi`.
- **Live chart** of the last 5 minutes, 15 minutes or hour. Select sensors in
  the table to chart only those.
- **Warning temperature.** Sensors at or above it turn red and a dashed line
  marks it on the chart.
- **CSV logging** with one row per sensor per reading, flushed immediately so
  nothing is lost if the computer crashes.
- **Headless logger** (`lizard-log`) for servers, with a ready-made systemd service.
- **°C or °F**, an adjustable reading interval, and settings that are remembered.
- **Demo mode** (`--demo`) with simulated sensors, for virtual machines and containers.
- **No dependencies.** Pure Python standard library (Tkinter).

## Requirements

- Linux.
- Python **3.10 or newer** with Tkinter. Most distributions package Tkinter separately:
  - Debian/Ubuntu: `sudo apt install python3-tk`
  - Fedora: `sudo dnf install python3-tkinter`
  - Arch: `sudo pacman -S tk`
- Optional: `nvidia-smi` (part of the proprietary NVIDIA driver) for NVIDIA GPU temperatures.

You don't need Python at all if you use a prebuilt `lizard` binary
(see [Building a standalone binary](#building-a-standalone-binary)).

## Installation

Clone or download the project, then create a virtual environment inside it:

```bash
cd lizard
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

`pip install .` adds two commands: `lizard` opens the window and `lizard-log`
logs without one. Use `pip install -e ".[dev]"` instead if you plan to change
the code. [pipx](https://pipx.pypa.io/) works too: `pipx install .` puts both
commands in `~/.local/bin` without a virtual environment to activate.

To add Lizard, with its icon, to your desktop's application menu:

```bash
packaging/linux/install-desktop-entry.sh
```

## Running

```bash
lizard
```

or run the package as a module, which also works straight from a checkout
without installing anything:

```bash
python3 -m lizard
```

Add `--demo` to either one to try Lizard with simulated sensors. In PyCharm,
create a Python run configuration and set **Module name** to `lizard`.

## Quick start

1. Start `lizard`. Monitoring begins at once: the table fills with your sensors
   and the chart starts drawing.
2. Optionally change how often the sensors are read, the warning temperature,
   and °C/°F.
3. Click **Choose…** to pick where the log goes (`~/temperature_log.csv` by default).
4. Click **Start logging**. Every reading is now added to the file until you
   click **Stop logging** or close Lizard.

The [user guide](docs/USER_GUIDE.md) explains every part of the window, which
sensors you can expect, the log format, the headless logger, and troubleshooting.

## Logging without a window

```bash
lizard-log                          # every 5 s to ~/temperature_log.csv, until Ctrl+C
lizard-log -i 60 -o ~/temps.csv     # every minute, to another file
lizard-log --list                   # show the sensors found and exit
```

To log in the background from boot, install the systemd user service:

```bash
mkdir -p ~/.config/systemd/user
cp packaging/linux/lizard-log.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now lizard-log
```

The log is plain CSV, one row per sensor per reading:

```text
timestamp,sensor,temperature_c
2026-10-25 19:15:03,CPU Package id 0,52.0
2026-10-25 19:15:03,CPU Core 0,49.0
2026-10-25 19:15:03,NVMe Composite,38.9
```

## Where the temperatures come from

| Source               | What it covers                                                                                   |
|----------------------|--------------------------------------------------------------------------------------------------|
| `/sys/class/hwmon`   | Every kernel hardware-monitoring driver: CPU (`coretemp`, `k10temp`), NVMe, AMD/Intel GPU, ACPI… |
| `/sys/class/thermal` | Thermal zones; used only when hwmon has no temperatures, e.g. on some ARM boards                 |
| `nvidia-smi`         | NVIDIA GPUs on the proprietary driver, which doesn't report through hwmon                        |

More detail, including the threading model, is in [ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Building a standalone binary

[PyInstaller](https://pyinstaller.org/) can bundle Lizard and Python into a single
program for computers without Python and Tkinter:

```bash
pip install -r requirements-dev.txt
pyinstaller packaging/lizard.spec
```

The result is `dist/lizard`. Build it on the oldest distribution you want to
support, since the binary needs a glibc at least as new as the build machine's.
The GitHub Actions workflow builds one on Ubuntu 22.04 for every push to `main`.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

The GUI tests need a display; on a server, run `xvfb-run -a pytest`. The icon is
drawn by `scripts/generate_icon.py`; run it again after changing the design.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the conventions.

## Project structure

```text
lizard/
├── lizard/                  the application package
│   ├── __main__.py          `python -m lizard`
│   ├── app.py               main(): creates the window (the `lizard` command)
│   ├── cli.py               the headless logger (the `lizard-log` command)
│   ├── core/                reading and recording, no GUI code
│   │   ├── sensors/         hwmon, thermal zones, nvidia-smi and demo sources
│   │   ├── monitor.py       the reading thread, history and statistics
│   │   ├── csvlog.py        writing the CSV log
│   │   ├── settings.py      remembered options
│   │   └── models.py        data passed between the core and the GUI
│   ├── gui/                 Tkinter interface
│   │   ├── main_window.py   the main window
│   │   ├── chart.py         the history chart
│   │   ├── widgets.py       the sensor table
│   │   └── icon.py
│   ├── utils/               formatting helpers
│   └── assets/              icon files
├── tests/                   pytest suite
├── docs/                    user guide, architecture notes, screenshot
├── packaging/               PyInstaller recipe; .desktop file and systemd service in linux/
├── scripts/                 icon generator
├── .github/workflows/       tests on Ubuntu and the binary build
├── pyproject.toml           package metadata
└── requirements*.txt        dependencies
```

## License

Lizard is released under the [MIT License](LICENSE).
