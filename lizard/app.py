"""Application entry point: ``lizard`` opens the window."""

from __future__ import annotations

import argparse
import logging
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Sequence
from tkinter import ttk

from lizard import __app_name__, __version__
from lizard.core import Monitor, Settings, discover_sources
from lizard.gui.icon import apply_window_icon
from lizard.gui.main_window import MainWindow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lizard", description="Watch, chart and log temperature sensors.")
    parser.add_argument("--demo", action="store_true", help="use simulated sensors instead of real ones")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _apply_style(root: tk.Tk) -> None:
    """Tk's "default" theme looks dated on Linux; "clam" is the cleanest one that ships with it."""
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    linespace = tkfont.nametofont("TkDefaultFont").metrics("linespace")
    style.configure("Treeview", rowheight=linespace + 8)


def create_root() -> tk.Tk:
    root = tk.Tk(className=__app_name__)  # sets WM_CLASS, which the .desktop file's StartupWMClass matches
    root.title(f"{__app_name__} - Temperature Monitor & Logger")
    _apply_style(root)
    apply_window_icon(root)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.load()
    monitor = Monitor(discover_sources(demo=args.demo), interval=settings.interval)
    root = create_root()
    MainWindow(root, monitor, settings, on_close=settings.save)
    monitor.start()
    try:
        root.mainloop()
    finally:
        monitor.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
