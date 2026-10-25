"""Headless logging: ``lizard-log`` reads the sensors on a timer and appends them to a CSV file.

This is what the original ``lizard.py`` script did. It suits servers without a
display, and running as a systemd service (see ``packaging/linux``).
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from lizard import __version__
from lizard.core import DEFAULT_INTERVAL, MIN_INTERVAL, Monitor, discover_sources
from lizard.core.settings import DEFAULT_LOG_FILE
from lizard.utils.formatting import format_interval, format_temperature

NO_SENSORS = (
    "No temperature sensors found. Lizard reads /sys/class/hwmon, /sys/class/thermal and nvidia-smi;\n"
    "inside virtual machines and containers these are usually empty. Try --demo to see how it works."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lizard-log",
        description="Log the computer's temperature sensors to a CSV file, without opening a window.",
    )
    parser.add_argument("-i", "--interval", type=float, default=DEFAULT_INTERVAL, metavar="SECONDS",
                        help=f"time between readings (default: {DEFAULT_INTERVAL:g}, minimum: {MIN_INTERVAL:g})")
    parser.add_argument("-o", "--log-file", type=Path, default=DEFAULT_LOG_FILE, metavar="PATH",
                        help="CSV file to append to (default: %(default)s)")
    parser.add_argument("--no-log", action="store_true", help="only print the readings")
    parser.add_argument("-n", "--count", type=int, metavar="N", help="stop after N readings (default: until Ctrl+C)")
    parser.add_argument("-q", "--quiet", action="store_true", help="don't print the readings")
    parser.add_argument("--list", action="store_true", help="list the sensors found and exit")
    parser.add_argument("--demo", action="store_true", help="use simulated sensors instead of real ones")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def format_round(when: float, values: Sequence[tuple[str, float]]) -> str:
    """One line per round: ``2026-10-25 18:55:03  CPU Package id 0 52.0 °C  ·  NVMe Composite 38.9 °C``."""
    readings = "  ·  ".join(f"{name} {format_temperature(celsius)}" for name, celsius in values)
    return f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(when))}  {readings or 'no readings'}"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sources = discover_sources(demo=args.demo)
    if not sources:
        print(NO_SENSORS, file=sys.stderr)
        return 1
    monitor = Monitor(sources, interval=args.interval)

    if args.list:
        monitor.sample_once()
        for sensor in monitor.snapshot().sensors:
            print(f"{sensor.name:<36} {format_temperature(sensor.current):>9}   ({sensor.source})")
        return 0

    if not args.no_log:
        try:
            monitor.start_logging(args.log_file)
        except OSError as exc:
            print(f"Can't write to {args.log_file}: {exc.strerror or exc}", file=sys.stderr)
            return 1
        print(f"Logging every {format_interval(monitor.interval)} to {args.log_file.expanduser()}. "
              "Press Ctrl+C to stop.", file=sys.stderr)

    reported_problems: tuple[str, ...] = ()
    taken = 0
    try:
        while True:
            started = time.monotonic()
            values = monitor.sample_once()
            taken += 1
            snapshot = monitor.snapshot()
            if not args.quiet:
                print(format_round(snapshot.last_reading or time.time(), values), flush=True)
            if snapshot.problems != reported_problems:
                for problem in snapshot.problems:
                    print(f"Warning: {problem}", file=sys.stderr)
                reported_problems = snapshot.problems
            if snapshot.log_error:
                print(snapshot.log_error, file=sys.stderr)
                return 1
            if args.count is not None and taken >= args.count:
                break
            time.sleep(max(0.0, monitor.interval - (time.monotonic() - started)))
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop_logging()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
