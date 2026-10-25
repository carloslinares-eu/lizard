"""Shared by the sensor sources."""

from __future__ import annotations


class SensorError(Exception):
    """A source could not be read this time. The message is shown to the user."""
