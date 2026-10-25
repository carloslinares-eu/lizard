# Contributing

Thanks for helping improve Lizard!

## Setting up

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Then run the app with `lizard` (or `python -m lizard`, add `--demo` for simulated
sensors) and the tests with `pytest` (`xvfb-run -a pytest` without a display).

## Guidelines

- **Linux only.** Sensors come from `/sys/class` and `nvidia-smi`. Keep paths
  injectable (like `HwmonSource(root)`) so the tests can use fake trees.
- **Keep the core free of GUI code.** Anything under `lizard/core/` must work
  without Tkinter, so it can be tested and reused by `lizard-log`.
- **Only the GUI thread touches Tk.** The monitor thread records readings; the
  window polls `Monitor.snapshot()`.
- **No runtime dependencies.** Lizard runs on the standard library alone.
  Development tools belong in `requirements-dev.txt` and the `dev` extra in
  `pyproject.toml`.
- **Read-only towards the hardware.** Lizard reads sensors and never needs root.
- Add or update tests in `tests/` for behavior changes, and run `pytest` before
  sending a change.
- Follow the style of the surrounding code: type hints, short docstrings,
  4-space indentation, lines up to about 120 characters.
- Note user-visible changes in `CHANGELOG.md` under an "Unreleased" heading.

## Releasing

1. Bump `__version__` in `lizard/__init__.py` and move the changelog entries
   under the new version (`tests/test_project.py` checks that they match).
2. Build the binary with `pyinstaller packaging/lizard.spec` and try it, or take
   the one built by GitHub Actions.
3. Tag the release, e.g. `git tag v1.0.0`.
