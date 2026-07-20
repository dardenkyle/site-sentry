"""Shared timing configuration and types for Site Sentry tests.

Lives outside conftest.py so tests can import these without importing a
conftest module, which pytest may load under more than one module name.
"""

from typing import NamedTuple

from playwright.sync_api import Page

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

# Reads the Navigation Timing Level 2 entry for the current document.
# Every field is a DOMHighResTimeStamp in milliseconds measured by the
# browser from navigation start, so the numbers are the site's own
# latency: Python/CDP round-trip and CI runner scheduling jitter, which
# make a wall-clock measurement flaky, are excluded by construction.
_NAVIGATION_TIMING_JS = """() => {
  const nav = performance.getEntriesByType('navigation')[0];
  if (!nav) { return null; }
  return {
    ttfb_ms: nav.responseStart,
    dom_content_loaded_ms: nav.domContentLoadedEventEnd,
    load_ms: nav.loadEventEnd,
    connect_ms: nav.connectEnd,
  };
}"""


class NavigationTiming(NamedTuple):
    """Browser-measured timing for a single navigation.

    All values are milliseconds from navigation start, so they capture
    what the site did, not what the harness added on top.

    Attributes:
        ttfb_ms: Time to first byte (responseStart); server plus network
        dom_content_loaded_ms: domContentLoadedEventEnd; DOM ready
        load_ms: loadEventEnd; all subresources of the initial HTML done
        connect_ms: connectEnd; the TCP and TLS connection is established
            (DNS resolution is the separate domainLookup phase)
    """

    ttfb_ms: float
    dom_content_loaded_ms: float
    load_ms: float
    connect_ms: float


def read_navigation_timing(page: Page) -> NavigationTiming | None:
    """Read the current page's Navigation Timing metrics.

    Should be called after the navigation has reached the load state, so
    the load and domContentLoaded marks are populated rather than zero.

    Args:
        page: Playwright page whose navigation to measure

    Returns:
        The browser's timing for the navigation, or None when no
        navigation entry exists (e.g. the navigation never completed)
    """
    raw = page.evaluate(_NAVIGATION_TIMING_JS)
    return NavigationTiming(**raw) if raw is not None else None


class FirstNavigation(NamedTuple):
    """Outcome of the first navigation performed in a test session.

    Attributes:
        timing: Browser-measured navigation timing, or None on failure
        error: Playwright error message, or None when it completed
    """

    timing: NavigationTiming | None
    error: str | None
