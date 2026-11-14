"""NVIDIA GPU temperatures from ``nvidia-smi``; the proprietary driver doesn't report them through hwmon."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

from lizard.core.models import Reading
from lizard.core.sensors.base import SensorError

QUERY = ("--query-gpu=index,name,temperature.gpu", "--format=csv,noheader,nounits")
TIMEOUT = 5.0


def parse_nvidia_smi(output: str) -> list[Reading]:
    """Parse lines like ``0, NVIDIA GeForce RTX 3070 Ti, 45``; GPUs reporting ``[N/A]`` are skipped."""
    readings: list[Reading] = []
    for line in output.splitlines():
        if line.count(",") < 2:
            continue
        _index, rest = line.split(",", 1)
        name, temperature = (part.strip() for part in rest.rsplit(",", 1))
        try:
            readings.append(Reading(name or "NVIDIA GPU", float(temperature)))
        except ValueError:
            continue
    return readings


class NvidiaSmiSource:
    name = "nvidia-smi"

    def __init__(self, executable: str, run: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self.executable = executable
        self._run = run

    @classmethod
    def find(cls) -> NvidiaSmiSource | None:
        """A source for the ``nvidia-smi`` on the PATH, or None if it isn't installed."""
        executable = shutil.which("nvidia-smi")
        return cls(executable) if executable else None

    def read(self) -> list[Reading]:
        try:
            result = self._run([self.executable, *QUERY], capture_output=True, text=True, timeout=TIMEOUT, check=False)
        except subprocess.TimeoutExpired as exc:
            raise SensorError(f"nvidia-smi didn't answer within {TIMEOUT:g} s") from exc
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "").strip().splitlines()
            raise SensorError(message[0] if message else f"nvidia-smi exited with code {result.returncode}")
        return parse_nvidia_smi(result.stdout)
