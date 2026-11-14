from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from lizard.core.models import Reading


class FakeSource:
    """Returns the next prepared round on every read; an exception in the list is raised instead."""

    def __init__(self, name: str, rounds: Iterable[list[tuple[str, float]] | Exception]):
        self.name = name
        self._rounds = list(rounds)
        self.reads = 0

    def read(self) -> list[Reading]:
        item = self._rounds[min(self.reads, len(self._rounds) - 1)]
        self.reads += 1
        if isinstance(item, Exception):
            raise item
        return [Reading(label, celsius) for label, celsius in item]


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_tree(tmp_path: Path):
    """Create files from a ``{relative_path: text}`` mapping under ``tmp_path / name``.

    A value of ``None`` creates a directory instead, which can't be read like a file.
    """

    def make(name: str, files: dict[str, str | None]) -> Path:
        root = tmp_path / name
        root.mkdir(parents=True, exist_ok=True)
        for relative, content in files.items():
            path = root / relative
            if content is None:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        return root

    return make
