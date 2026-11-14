from __future__ import annotations

from pathlib import Path

import pytest

from lizard.core import sensors
from lizard.core.models import Reading
from lizard.core.sensors.sysfs import HwmonSource, ThermalZoneSource, chip_title, natural_key

HWMON = {
    "hwmon0/name": "acpitz\n",
    "hwmon0/temp1_input": "27800\n",
    "hwmon1/name": "coretemp\n",
    "hwmon1/temp1_input": "52000\n",
    "hwmon1/temp1_label": "Package id 0\n",
    "hwmon1/temp2_input": "49000\n",
    "hwmon1/temp2_label": "Core 0\n",
    "hwmon1/temp10_input": "47000\n",
    "hwmon1/temp10_label": "Core 8\n",
    "hwmon1/temp5_input": None,  # unreadable, like a sensor whose driver returns an I/O error
    "hwmon2/name": "nvme\n",
    "hwmon2/temp1_input": "38850\n",
    "hwmon2/temp1_label": "Composite\n",
    "hwmon3/name": "BAT0\n",
    "hwmon3/in0_input": "12000\n",  # a voltage, not a temperature
    "hwmon4/device/name": "it87\n",  # an old driver with its attributes in device/
    "hwmon4/device/temp1_input": "35000\n",
    "hwmon10/name": "amdgpu\n",
    "hwmon10/temp1_input": "N/A\n",
    "hwmon10/temp2_input": "-273000\n",  # implausible: a disconnected input
    "hwmon10/temp3_input": "61000\n",
    "hwmon10/temp3_label": "junction\n",
}

THERMAL = {
    "thermal_zone0/type": "acpitz\n",
    "thermal_zone0/temp": "27800\n",
    "thermal_zone1/type": "x86_pkg_temp\n",
    "thermal_zone1/temp": "55000\n",
    "thermal_zone2/type": "iwlwifi_1\n",  # no temp file: the zone is switched off
    "cooling_device0/type": "Processor\n",
}


def test_hwmon_reads_every_temperature_in_natural_order(make_tree):
    root = make_tree("hwmon", HWMON)

    assert HwmonSource(root).read() == [
        Reading("ACPI temp1", 27.8),
        Reading("CPU Package id 0", 52.0),
        Reading("CPU Core 0", 49.0),
        Reading("CPU Core 8", 47.0),
        Reading("NVMe Composite", 38.85),
        Reading("it87 temp1", 35.0),
        Reading("GPU junction", 61.0),
    ]


def test_hwmon_without_sensors_reads_nothing(tmp_path):
    assert HwmonSource(tmp_path / "missing").read() == []


def test_thermal_zones(make_tree):
    root = make_tree("thermal", THERMAL)

    assert ThermalZoneSource(root).read() == [Reading("ACPI", 27.8), Reading("CPU package", 55.0)]


@pytest.mark.parametrize(
    ("chip", "title"),
    [("coretemp", "CPU"), ("k10temp", "CPU"), ("nvme", "NVMe"), ("pch_cannonlake", "Chipset"),
     ("iwlwifi_1", "Wi-Fi"), ("something_new", "something_new")],
)
def test_chip_title(chip, title):
    assert chip_title(chip) == title


def test_natural_key_sorts_numbers_by_value():
    names = ["hwmon10", "hwmon2", "hwmon1"]
    assert sorted(names, key=lambda name: natural_key(Path(name))) == ["hwmon1", "hwmon2", "hwmon10"]


def _no_nvidia(monkeypatch):
    monkeypatch.setattr(sensors.NvidiaSmiSource, "find", classmethod(lambda cls: None))


def test_discover_prefers_hwmon_over_thermal_zones(make_tree, tmp_path, monkeypatch):
    _no_nvidia(monkeypatch)
    make_tree("sys/hwmon", HWMON)
    make_tree("sys/thermal", THERMAL)

    found = sensors.discover_sources(sysfs_root=tmp_path / "sys")
    assert [source.name for source in found] == ["hwmon"]


def test_discover_falls_back_to_thermal_zones(make_tree, tmp_path, monkeypatch):
    _no_nvidia(monkeypatch)
    make_tree("sys/thermal", THERMAL)

    found = sensors.discover_sources(sysfs_root=tmp_path / "sys")
    assert [source.name for source in found] == ["thermal zones"]


def test_discover_finds_nothing_in_an_empty_machine(tmp_path, monkeypatch):
    _no_nvidia(monkeypatch)
    assert sensors.discover_sources(sysfs_root=tmp_path) == []


def test_discover_demo():
    assert [source.name for source in sensors.discover_sources(demo=True)] == ["demo"]
