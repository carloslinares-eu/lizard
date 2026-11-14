"""Checks that the version, changelog, packaging files and assets agree with each other."""

from __future__ import annotations

import configparser
import re
from pathlib import Path

import pytest

from lizard import __version__
from lizard.gui.icon import ASSETS_DIR, WINDOW_ICON_SIZES

ROOT = Path(__file__).resolve().parent.parent


def test_version_is_semantic():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_changelog_describes_the_current_version():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, flags=re.MULTILINE)
    assert released and released[0] == __version__, "add a CHANGELOG.md entry for the new version"


def test_pyproject_takes_the_version_from_the_package():
    tomllib = pytest.importorskip("tomllib")  # Python 3.11+
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" in project["project"]["dynamic"]
    assert project["tool"]["setuptools"]["dynamic"]["version"]["attr"] == "lizard.__version__"
    assert project["project"]["gui-scripts"]["lizard"] == "lizard.app:main"
    assert project["project"]["scripts"]["lizard-log"] == "lizard.cli:main"


def test_icons_exist():
    for name in (*WINDOW_ICON_SIZES, "lizard-512.png"):
        assert (ASSETS_DIR / name).is_file(), name


def test_desktop_entry():
    entry = configparser.ConfigParser(interpolation=None)
    entry.optionxform = str
    entry.read(ROOT / "packaging" / "linux" / "lizard.desktop", encoding="utf-8")
    desktop = entry["Desktop Entry"]
    assert desktop["Type"] == "Application"
    assert desktop["Exec"].split()[0] == "lizard"
    assert desktop["Icon"] == "lizard"
    assert desktop["StartupWMClass"] == "Lizard"
