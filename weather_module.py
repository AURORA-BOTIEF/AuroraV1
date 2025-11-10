"""Lightweight weather helper used only for unit tests.

This module provides a deterministic, dependency-free function
that returns a small weather report dict for a given location.
It is intentionally minimal so tests can run in CI/local without
network access or third-party APIs.
"""
from datetime import datetime


def get_current_weather(location: str) -> dict:
    """Return a deterministic fake weather report for the given location.

    Args:
        location: a location name (string)

    Returns:
        dict with keys: location, temperature_c, condition, observed_at, source
    """
    if not location:
        raise ValueError("location must be a non-empty string")

    # deterministic fake data useful for tests
    return {
        "location": location,
        "temperature_c": 20.0,
        "condition": "Sunny",
        "observed_at": datetime.utcnow().isoformat() + "Z",
        "source": "local_stub",
    }
