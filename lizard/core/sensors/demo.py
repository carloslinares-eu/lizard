"""Simulated sensors for trying Lizard where no real ones can be read, e.g. in a virtual machine (``lizard --demo``)."""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable

from lizard.core.models import Reading

# label, average °C, swing °C, period of the swing in seconds
DEMO_SENSORS = (
    ("Demo CPU Package", 54.0, 11.0, 520.0),
    ("Demo CPU Core 0", 52.0, 12.0, 430.0),
    ("Demo CPU Core 1", 49.0, 10.0, 610.0),
    ("Demo GPU", 46.0, 7.0, 1100.0),
    ("Demo NVMe Composite", 38.0, 2.5, 2400.0),
)


class DemoSource:
    """Smooth, slightly noisy waves. Deterministic for a given clock and seed, which keeps tests stable."""

    name = "demo"

    def __init__(self, clock: Callable[[], float] = time.time, seed: int = 7):
        self._clock = clock
        self._random = random.Random(seed)

    def read(self) -> list[Reading]:
        now = self._clock()
        readings = []
        for label, average, swing, period in DEMO_SENSORS:
            wave = math.sin(2 * math.pi * now / period) + 0.35 * math.sin(2 * math.pi * now / (period / 3.7))
            noise = self._random.uniform(-0.4, 0.4)
            readings.append(Reading(label, round(average + swing * wave / 1.35 + noise, 1)))
        return readings
