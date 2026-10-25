"""Temperatures from the Linux kernel's sysfs interface, the same data ``lm-sensors`` reads."""

from __future__ import annotations

import re
from pathlib import Path

from lizard.core.models import Reading

SYSFS_CLASS = Path("/sys/class")

# Readings outside this range (°C) are disconnected inputs or driver glitches, not temperatures.
PLAUSIBLE_RANGE = (-60.0, 150.0)

# Friendlier names for common hwmon drivers and thermal zone types.
CHIP_TITLES = {
    "coretemp": "CPU",
    "k10temp": "CPU",
    "zenpower": "CPU",
    "cpu_thermal": "CPU",
    "cpu-thermal": "CPU",
    "x86_pkg_temp": "CPU package",
    "amdgpu": "GPU",
    "radeon": "GPU",
    "nouveau": "GPU",
    "nvme": "NVMe",
    "drivetemp": "Drive",
    "acpitz": "ACPI",
    "thinkpad": "ThinkPad",
}
CHIP_PREFIXES = (("pch_", "Chipset"), ("iwlwifi", "Wi-Fi"), ("mt7921", "Wi-Fi"), ("ath1", "Wi-Fi"))


def chip_title(chip: str) -> str:
    """``'coretemp'`` -> ``'CPU'``; unknown drivers keep their own name."""
    if chip in CHIP_TITLES:
        return CHIP_TITLES[chip]
    for prefix, title in CHIP_PREFIXES:
        if chip.startswith(prefix):
            return title
    return chip


def natural_key(path: Path) -> list[int | str]:
    """Sort ``hwmon2`` before ``hwmon10`` and ``temp2_input`` before ``temp10_input``."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path.name)]


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip() or None
    except OSError:  # missing, or the driver refuses (e.g. a GPU that is powered down)
        return None


def _read_millidegrees(path: Path) -> float | None:
    text = _read_text(path)
    try:
        celsius = int(text) / 1000 if text is not None else None
    except ValueError:
        return None
    if celsius is None or not PLAUSIBLE_RANGE[0] < celsius < PLAUSIBLE_RANGE[1]:
        return None
    return celsius


class HwmonSource:
    """Every ``temp*_input`` under ``/sys/class/hwmon``, labelled like ``sensors`` does."""

    name = "hwmon"

    def __init__(self, root: Path | str = SYSFS_CLASS / "hwmon"):
        self.root = Path(root)

    def read(self) -> list[Reading]:
        readings: list[Reading] = []
        for chip_dir in sorted(self.root.glob("hwmon*"), key=natural_key):
            # Very old drivers keep their attributes in the device folder instead.
            attr_dir = chip_dir if any(chip_dir.glob("temp*_input")) else chip_dir / "device"
            chip = _read_text(attr_dir / "name") or _read_text(chip_dir / "name") or chip_dir.name
            title = chip_title(chip)
            for input_file in sorted(attr_dir.glob("temp*_input"), key=natural_key):
                celsius = _read_millidegrees(input_file)
                if celsius is None:
                    continue
                channel = input_file.name.removesuffix("_input")  # "temp1"
                label = _read_text(attr_dir / f"{channel}_label") or channel
                readings.append(Reading(f"{title} {label}", celsius))
        return readings


class ThermalZoneSource:
    """``/sys/class/thermal/thermal_zone*``: fewer, coarser sensors, used when hwmon has none."""

    name = "thermal zones"

    def __init__(self, root: Path | str = SYSFS_CLASS / "thermal"):
        self.root = Path(root)

    def read(self) -> list[Reading]:
        readings: list[Reading] = []
        for zone in sorted(self.root.glob("thermal_zone*"), key=natural_key):
            celsius = _read_millidegrees(zone / "temp")
            if celsius is None:
                continue
            zone_type = _read_text(zone / "type") or zone.name
            readings.append(Reading(chip_title(zone_type), celsius))
        return readings
