"""Smoke tests for kyledarden.com.

Fast, critical tests that verify core functionality and site availability.
These tests should run quickly and catch major breakages.
"""

from typing import Any
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, expect

from tests.utils.logger import get_logger
from tests.utils.timing import PAGE_LOAD_TIMEOUT_MS, FirstNavigation, read_navigation_timing
from tests.utils.urls import http_variant, is_local, same_site

logger = get_logger(__name__)

# Budgets are set on domContentLoaded read from the browser's Navigation
# Timing, not a Python wall clock: the metric is the site's own latency,
# with CDP round-trip and CI runner scheduling jitter excluded, so a
# busy runner no longer produces false alarms unrelated to the site.

# First-navigation budget, deliberately the looser of the two. This
# navigation pays connection setup (DNS, TCP, TLS), visible as non-zero
# connect timing; cold domContentLoaded is ~280ms against the live site,
# so 3000ms is failure territory with wide headroom for a cold CI path.
FIRST_NAVIGATION_DCL_BUDGET_MS = 3000.0

# Warm-navigation budget, deliberately tighter: connection state is
# already established, so this catches steady latency regressions rather
# than one-time setup. Warm domContentLoaded is ~95ms live; 1500ms stays
# failure territory while absorbing CI network variance.
WARM_DCL_BUDGET_MS = 1500.0


@pytest.mark.smoke
def test_homepage_loads(page: Page) -> None:
    """Test that the homepage is reachable and returns a healthy status.

    This is the availability check, not the performance gate: it asks
    only whether the page loaded. The page fixture applies the suite's
    deliberate PAGE_LOAD_TIMEOUT_MS ceiling on "never arrived", and the
    latency budgets live in the response-time tests, so a failure names
    which property broke.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing homepage load (ceiling %dms)", PAGE_LOAD_TIMEOUT_MS)

    response = page.goto("/")
    assert response is not None, "No response received"
    assert response.ok, f"Response not OK: {response.status}"

    logger.info("Homepage loaded successfully with status %s", response.status)


@pytest.mark.smoke
def test_homepage_title(page: Page) -> None:
    """Test that the homepage has a proper title.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing homepage title")

    page.goto("/")
    title = page.title()

    assert title, "Page title is empty"
    assert len(title) > 0, "Page title has no content"

    logger.info("Page title: %s", title)


@pytest.mark.smoke
def test_no_console_errors(page: Page) -> None:
    """Test that the homepage loads without console errors.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing for console errors")

    console_errors: list[str] = []

    def handle_console(msg: Any) -> None:
        if msg.type == "error":
            console_errors.append(msg.text)
            logger.warning("Console error: %s", msg.text)

    # Attach the listener before navigating, then bound the collection
    # window to the load event rather than a fixed sleep: errors from
    # HTML parse, synchronous scripts, and load handlers are all captured
    # by the time goto returns, and the extra second the sleep cost every
    # run is gone.
    page.on("console", handle_console)
    page.goto("/", wait_until="load")

    assert len(console_errors) == 0, f"Found {len(console_errors)} console errors: {console_errors}"
    logger.info("No console errors found")


@pytest.mark.smoke
@pytest.mark.no_rerun
def test_first_navigation_response_time(first_navigation: FirstNavigation) -> None:
    """Test the session's first navigation against its latency budget.

    Consumes the session-scoped measurement taken before any other test
    ran, so this is the one navigation that paid connection setup (DNS,
    TCP, TLS) in this process. Every other timing in the suite reuses
    that state, which is what makes this the looser of the two budgets.

    Exempt from the smoke retry budget: the measurement is taken once
    per session, so a rerun would re-assert the identical cached value
    and only burn the rerun delay.

    Args:
        first_navigation: Session-scoped first-navigation measurement
    """
    assert first_navigation.error is None, f"First navigation failed: {first_navigation.error}"
    timing = first_navigation.timing
    assert timing is not None, "First navigation produced no timing"
    logger.info(
        "First navigation: dcl=%.0fms connect=%.0fms ttfb=%.0fms",
        timing.dom_content_loaded_ms,
        timing.connect_ms,
        timing.ttfb_ms,
    )

    assert timing.dom_content_loaded_ms < FIRST_NAVIGATION_DCL_BUDGET_MS, (
        f"First navigation domContentLoaded {timing.dom_content_loaded_ms:.0f}ms "
        f"(budget {FIRST_NAVIGATION_DCL_BUDGET_MS:.0f}ms)"
    )


@pytest.mark.smoke
def test_warm_response_time(page: Page) -> None:
    """Test that a warm navigation stays within the warm-path budget.

    Runs mid-suite with connection state already established, so this is
    deliberately the tighter budget of the two: it catches steady
    latency regressions, not the one-time connection setup cost.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing warm navigation timing")

    response = page.goto("/", wait_until="load")
    assert response is not None, "No response received"

    timing = read_navigation_timing(page)
    assert timing is not None, "Warm navigation produced no timing"
    logger.info(
        "Warm navigation: dcl=%.0fms ttfb=%.0fms", timing.dom_content_loaded_ms, timing.ttfb_ms
    )

    assert timing.dom_content_loaded_ms < WARM_DCL_BUDGET_MS, (
        f"Warm navigation domContentLoaded {timing.dom_content_loaded_ms:.0f}ms "
        f"(budget {WARM_DCL_BUDGET_MS:.0f}ms)"
    )


@pytest.mark.smoke
def test_main_content_visible(page: Page) -> None:
    """Test that main content is visible on the homepage.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing main content visibility")

    page.goto("/")

    # Check that the page has a body with content
    body = page.locator("body")
    expect(body).to_be_visible()

    # Verify page is not empty
    content = page.content()
    assert len(content) > 100, "Page content is suspiciously short"

    logger.info("Main content is visible")


@pytest.mark.smoke
def test_https_redirect(page: Page, base_url: str) -> None:
    """Test that HTTP requests to the target redirect to HTTPS.

    The URL is derived from base_url rather than hardcoded so that a run
    pointed elsewhere via BASE_URL never contacts production. Targets
    that cannot answer the question are skipped rather than failed: a
    plain-HTTP base has no redirect to assert, and a local dev server
    typically terminates TLS without an HTTP listener to redirect from.

    Args:
        page: Playwright page fixture
        base_url: Base URL of the site under test
    """
    if urlsplit(base_url).scheme != "https":
        pytest.skip(f"Base URL is not HTTPS, no redirect to verify: {base_url}")
    if is_local(base_url):
        pytest.skip(f"Local target does not serve an HTTP redirect: {base_url}")

    http_url = http_variant(base_url)
    logger.info("Testing HTTPS redirect from %s", http_url)

    response = page.goto(http_url)

    assert response is not None, "No response received"

    # Check that we ended up on HTTPS, still on the configured target.
    # The host matters as much as the scheme: a redirect that lands
    # somewhere else (production, a parked domain) would otherwise pass
    # while reporting on a site this run was not asked to test. An
    # apex/www hop is not that, so same_site allows it.
    assert urlsplit(page.url).scheme == "https", f"Expected HTTPS, got: {page.url}"
    assert same_site(page.url, base_url), (
        f"Redirect left the configured target {base_url}, landed on {page.url}"
    )

    logger.info("Successfully redirected to: %s", page.url)
