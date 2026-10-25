"""Where temperatures come from.

A source is any object with a ``name`` and a ``read()`` method that returns a
list of :class:`~lizard.core.models.Reading`. ``read()`` may raise ``OSError``
or :class:`SensorError`; the monitor reports the problem and keeps reading the
other sources.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from lizard.core.models import Reading
from lizard.core.sensors.base import SensorError
from lizard.core.sensors.demo import DemoSource
from lizard.core.sensors.nvidia import NvidiaSmiSource
from lizard.core.sensors.sysfs import SYSFS_CLASS, HwmonSource, ThermalZoneSource

log = logging.getLogger(__name__)


class SensorSource(Protocol):
    name: str

    def read(self) -> list[Reading]: ...


def _has_readings(source: SensorSource) -> bool:
    try:
        return bool(source.read())
    except (OSError, SensorError) as exc:
        log.info("Skipping %s: %s", source.name, exc)
        return False


def discover_sources(demo: bool = False, sysfs_root: Path = SYSFS_CLASS) -> list[SensorSource]:
    """The sources that report at least one temperature on this computer.

    The kernel's hwmon drivers are preferred. Thermal zones mostly repeat what
    hwmon reports, so they are only used when hwmon has nothing.
    """
    if demo:
        return [DemoSource()]
    sources: list[SensorSource] = []
    hwmon, thermal = HwmonSource(sysfs_root / "hwmon"), ThermalZoneSource(sysfs_root / "thermal")
    if _has_readings(hwmon):
        sources.append(hwmon)
    elif _has_readings(thermal):
        sources.append(thermal)
    nvidia = NvidiaSmiSource.find()
    if nvidia is not None and _has_readings(nvidia):
        sources.append(nvidia)
    return sources


__all__ = [
    "DemoSource",
    "HwmonSource",
    "NvidiaSmiSource",
    "SensorError",
    "SensorSource",
    "ThermalZoneSource",
    "discover_sources",
]
