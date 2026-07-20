"""Shared timing types for Site Sentry tests.

Lives outside conftest.py so tests can import the type without importing
a conftest module, which pytest may load under more than one module name.
"""

from typing import NamedTuple


class FirstNavigation(NamedTuple):
    """Outcome of the first navigation performed in a test session.

    Attributes:
        seconds: Wall-clock time spent in the navigation
        error: Playwright error message, or None when it completed
    """

    seconds: float
    error: str | None
