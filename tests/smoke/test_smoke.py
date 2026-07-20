"""Smoke tests for kyledarden.com.

Fast, critical tests that verify core functionality and site availability.
These tests should run quickly and catch major breakages.
"""

import time
from typing import Any

import pytest
from playwright.sync_api import Page, expect

from tests.utils.logger import get_logger
from tests.utils.timing import FirstNavigation

logger = get_logger(__name__)

# Availability ceiling for a warm navigation. Chosen deliberately to
# replace the implicit 30s Playwright default that previously acted as
# the de facto performance gate: warm loads are consistently sub-second,
# so 15s is failure territory, not slowness.
PAGE_LOAD_TIMEOUT_MS = 15_000

# Latency budget for the session's first navigation, which pays DNS,
# TCP, and TLS setup on top of the request itself. Not a cache-cold
# budget: the CDN edge cache is warm regardless of what the suite does.
FIRST_NAVIGATION_BUDGET_SECONDS = 10.0

# Latency budget once connection state is established by earlier tests.
WARM_LOAD_BUDGET_SECONDS = 5.0


@pytest.mark.smoke
def test_homepage_loads(page: Page) -> None:
    """Test that the homepage is reachable and returns a healthy status.

    This is the availability check, not the performance gate: it asks
    only whether the page loaded. The explicit timeout is a deliberate
    ceiling on "never arrived", and the latency budgets live in the
    response-time tests so a failure names which property broke.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing homepage load")

    response = page.goto("/", timeout=PAGE_LOAD_TIMEOUT_MS)
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

    page.on("console", handle_console)
    page.goto("/")

    # Wait a moment for any delayed console errors
    page.wait_for_timeout(1000)

    assert len(console_errors) == 0, f"Found {len(console_errors)} console errors: {console_errors}"
    logger.info("No console errors found")


@pytest.mark.smoke
def test_first_navigation_response_time(first_navigation: FirstNavigation) -> None:
    """Test the session's first navigation against its latency budget.

    Consumes the session-scoped measurement taken before any other test
    ran, so this is the one navigation that paid connection setup (DNS,
    TCP, TLS) in this process. Every other timing in the suite reuses
    that state, which is what makes this the looser of the two budgets.

    Args:
        first_navigation: Session-scoped first-navigation measurement
    """
    logger.info("First navigation took %.2fs", first_navigation.seconds)

    assert first_navigation.error is None, (
        f"First navigation failed after {first_navigation.seconds:.2f}s: {first_navigation.error}"
    )
    assert first_navigation.seconds < FIRST_NAVIGATION_BUDGET_SECONDS, (
        f"First navigation took {first_navigation.seconds:.2f}s "
        f"(budget {FIRST_NAVIGATION_BUDGET_SECONDS:.0f}s)"
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
    logger.info("Testing warm page load time")

    start_time = time.perf_counter()
    response = page.goto("/", wait_until="load", timeout=PAGE_LOAD_TIMEOUT_MS)
    load_time = time.perf_counter() - start_time

    assert response is not None, "No response received"
    assert load_time < WARM_LOAD_BUDGET_SECONDS, (
        f"Warm navigation took {load_time:.2f}s (budget {WARM_LOAD_BUDGET_SECONDS:.0f}s)"
    )

    logger.info("Page loaded in %.2fs", load_time)


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
def test_https_redirect(page: Page) -> None:
    """Test that HTTP requests redirect to HTTPS.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing HTTPS redirect")

    response = page.goto("http://kyledarden.com")

    assert response is not None, "No response received"

    # Check that we ended up on HTTPS
    final_url = page.url
    assert final_url.startswith("https://"), f"Expected HTTPS, got: {final_url}"

    logger.info("Successfully redirected to: %s", final_url)
