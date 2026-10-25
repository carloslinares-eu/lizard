"""Loading the application icon and other bundled images."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

log = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
WINDOW_ICON_SIZES = ("lizard.png", "lizard-64.png", "lizard-48.png")  # the window manager picks the best fit

_window_icons: list[tk.PhotoImage] = []  # Tk drops images that Python no longer references


def asset_path(name: str) -> Path:
    return ASSETS_DIR / name


def apply_window_icon(root: tk.Tk) -> None:
    """Set the icon used by the title bar, the task switcher and every dialog of the app."""
    try:
        images = [tk.PhotoImage(master=root, file=str(asset_path(name))) for name in WINDOW_ICON_SIZES]
    except tk.TclError:
        log.warning("Could not load the application icon", exc_info=True)
        return
    root.iconphoto(True, *images)
    _window_icons.extend(images)


def load_image(name: str, master: tk.Misc | None = None) -> tk.PhotoImage | None:
    """Load a PNG from the assets folder, or return None if it can't be read."""
    try:
        return tk.PhotoImage(master=master, file=str(asset_path(name)))
    except tk.TclError:
        log.warning("Could not load image %s", name, exc_info=True)
        return None
