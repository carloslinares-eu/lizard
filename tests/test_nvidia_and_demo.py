from __future__ import annotations

import subprocess

import pytest

from lizard.core.models import Reading
from lizard.core.sensors import DemoSource, NvidiaSmiSource, SensorError
from lizard.core.sensors.demo import DEMO_SENSORS
from lizard.core.sensors.nvidia import parse_nvidia_smi


def test_parse_nvidia_smi():
    output = "0, NVIDIA GeForce RTX 3070 Ti, 45\n1, Tesla T4, [N/A]\n2, NVIDIA A100-SXM4-40GB, 61\n\n"
    assert parse_nvidia_smi(output) == [Reading("NVIDIA GeForce RTX 3070 Ti", 45.0),
                                        Reading("NVIDIA A100-SXM4-40GB", 61.0)]


def _runner(returncode=0, stdout="", stderr="", raises: Exception | None = None):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    return run, calls


def test_nvidia_source_runs_the_query():
    run, calls = _runner(stdout="0, NVIDIA GeForce RTX 4090, 52\n")
    assert NvidiaSmiSource("/usr/bin/nvidia-smi", run=run).read() == [Reading("NVIDIA GeForce RTX 4090", 52.0)]
    command, options = calls[0]
    assert command[0] == "/usr/bin/nvidia-smi"
    assert "--query-gpu=index,name,temperature.gpu" in command
    assert options["timeout"] > 0


def test_nvidia_source_reports_driver_errors():
    run, _calls = _runner(returncode=9, stdout="NVIDIA-SMI has failed because it couldn't communicate with the "
                                               "NVIDIA driver.\nMake sure that the latest driver is installed.\n")
    with pytest.raises(SensorError, match="couldn't communicate"):
        NvidiaSmiSource("nvidia-smi", run=run).read()


def test_nvidia_source_reports_timeouts():
    run, _calls = _runner(raises=subprocess.TimeoutExpired("nvidia-smi", 5))
    with pytest.raises(SensorError, match="didn't answer"):
        NvidiaSmiSource("nvidia-smi", run=run).read()


def test_demo_source_is_plausible_and_repeatable(clock):
    first = DemoSource(clock=clock).read()
    assert [reading.label for reading in first] == [label for label, *_rest in DEMO_SENSORS]
    assert all(20 < reading.celsius < 80 for reading in first)
    assert DemoSource(clock=clock).read() == first

    clock.advance(60)
    assert DemoSource(clock=clock).read() != first
