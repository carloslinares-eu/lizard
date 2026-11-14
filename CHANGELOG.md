# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-25

First packaged release. The single `lizard.py` script has become the `lizard` package,
with a window for watching the sensors and a command for logging them headless.

### Added

- **Window** (`lizard`) with a table of every sensor showing the current, lowest,
  highest and average temperature, and a live chart of the last 5 minutes, 15
  minutes or hour. Selecting sensors in the table charts only those.
- **Warning temperature**: sensors at or above it turn red, and a dashed line
  marks it on the chart.
- **°C / °F** display. The log file always records °C.
- **Start/Stop logging** buttons, a choice of log file, and an **Open** button.
- **Adjustable reading interval**, from 1 second to 1 hour.
- Settings are remembered in `~/.config/lizard/settings.json`.
- **Version number** shown in the window header, and `--version` on both commands.
- **Application icon** (window, task switcher and application menu), a `.desktop`
  launcher, and a script that adds it to the menu.
- **NVIDIA GPU** temperatures through `nvidia-smi`, which the proprietary driver needs.
- **`lizard-log`** command for headless logging, with `--interval`, `--log-file`,
  `--count`, `--list`, `--no-log` and `--quiet`, plus a systemd user service for it.
- **Demo mode** (`--demo`) with simulated sensors, for trying Lizard in a virtual
  machine or container where no real sensors can be read.
- Problems reading a sensor source are shown in the window instead of stopping it.
- Installable package (`pip install .`) with `lizard` and `lizard-log` commands,
  `python -m lizard`, and a PyInstaller recipe for a standalone binary.
- Documentation (README, user guide, architecture notes), a test suite, and a
  GitHub Actions workflow that runs it on Ubuntu and builds the binary.

### Changed

- Every temperature sensor is read, not only the first CPU core.
- Sensors are read straight from `/sys/class/hwmon` (falling back to
  `/sys/class/thermal`), the same data `lm-sensors` uses, so the `sensors`
  command is no longer needed.
- The log is a CSV file (`timestamp,sensor,temperature_c`), by default
  `~/temperature_log.csv` instead of `~/temperature_log.txt`, written in UTF-8
  and flushed after every reading.
- The default interval is 5 seconds instead of 10.
