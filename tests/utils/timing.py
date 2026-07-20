"""Shared timing configuration and types for Site Sentry tests.

Lives outside conftest.py so tests can import these without importing a
conftest module, which pytest may load under more than one module name.
"""

from typing import NamedTuple

# Deliberate ceiling on every navigation in the suite, applied by the
# page fixture in conftest.py. Replaces Playwright's implicit 30s
# default, which previously acted as an unchosen performance gate:
# navigations here are consistently sub-second, so 15s is failure
# territory rather than slowness.
PAGE_LOAD_TIMEOUT_MS = 15_000

# Ceiling for the session's first navigation. Deliberately above the
# budget the test asserts, so a slow-but-completing load is reported as
# a measured number instead of a bare timeout.
FIRST_NAVIGATION_TIMEOUT_MS = 20_000


class FirstNavigation(NamedTuple):
    """Outcome of the first navigation performed in a test session.

    Attributes:
        seconds: Wall-clock time spent in the navigation
        error: Playwright error message, or None when it completed
    """

    seconds: float
    error: str | None
