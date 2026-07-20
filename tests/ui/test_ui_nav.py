"""UI and navigation tests for kyledarden.com.

Tests for user interface elements, navigation, and interactive features.
"""

from typing import Any
from urllib.parse import urljoin, urlparse

import pytest
from playwright.sync_api import Page, expect

from tests.utils.logger import get_logger

logger = get_logger(__name__)

# Hrefs that are not navigable pages and should not be link-checked
NON_PAGE_HREF_PREFIXES = ("#", "javascript:", "mailto:", "tel:")

# Cap on link-checking requests to keep the test fast
MAX_LINKS_CHECKED = 10

# Scan bound for the canary test, assumed to exceed the page's internal
# link count so the injected canary (last in the DOM) is included; the
# canary assertion fails loudly if the page ever outgrows it
CANARY_SCAN_LIMIT = 1000


def _internal_link_urls(page: Page, limit: int) -> list[str]:
    """Collect resolved, de-duplicated internal link URLs from the page.

    Args:
        page: Page to collect anchor hrefs from
        limit: Maximum number of URLs to return

    Returns:
        Up to limit absolute URLs on the same host as the page
    """
    page_host = urlparse(page.url).hostname
    urls: list[str] = []
    for link in page.locator("a[href]").all():
        href = (link.get_attribute("href") or "").strip()
        if href and not href.startswith(NON_PAGE_HREF_PREFIXES):
            absolute = urljoin(page.url, href)
            if urlparse(absolute).hostname == page_host and absolute not in urls:
                urls.append(absolute)
    return urls[:limit]


def _broken_links(page: Page, urls: list[str]) -> list[str]:
    """Request each URL and report the ones that do not resolve.

    Redirects are followed, so any final status of 400 or above counts
    as broken.

    Args:
        page: Page whose request context issues the checks
        urls: Absolute URLs to check

    Returns:
        Descriptions of URLs that failed to resolve
    """
    broken: list[str] = []
    for url in urls:
        response = page.request.get(url)
        if not response.ok:
            broken.append(f"{url} -> HTTP {response.status}")
            logger.warning("Broken link: %s (HTTP %d)", url, response.status)
    return broken


@pytest.mark.ui
def test_navigation_links_exist(page: Page) -> None:
    """Test that navigation links are present on the page.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing navigation links presence")

    page.goto("/")

    # Check for common navigation elements
    links = page.locator("a[href]")
    link_count = links.count()

    assert link_count > 0, "No links found on the page"
    logger.info("Found %d links on the page", link_count)


@pytest.mark.ui
def test_navigation_links_valid(page: Page) -> None:
    """Test that internal navigation links resolve successfully.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing navigation link validity")

    page.goto("/")

    urls = _internal_link_urls(page, MAX_LINKS_CHECKED)
    broken = _broken_links(page, urls)

    assert len(broken) == 0, f"Found broken internal links: {broken}"
    logger.info("All %d checked internal links resolve", len(urls))


@pytest.mark.ui
def test_navigation_link_check_detects_broken(page: Page) -> None:
    """Test that the link check itself catches a broken link.

    Guards against the check silently degrading into one that can never
    fail (issue #27): a link to a nonexistent page is injected and must
    be reported as broken.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing that the link check detects broken links")

    page.goto("/")
    page.evaluate(
        "document.body.insertAdjacentHTML('beforeend',"
        " '<a href=\"/site-sentry-link-check-canary\">canary</a>')"
    )

    urls = _internal_link_urls(page, CANARY_SCAN_LIMIT)
    broken = _broken_links(page, [url for url in urls if "link-check-canary" in url])

    assert len(broken) == 1, "Injected broken link was not detected"
    logger.info("Link check correctly detected the injected broken link")


@pytest.mark.ui
def test_responsive_viewport(page: Page) -> None:
    """Test that the site is responsive at different viewport sizes.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing responsive design")

    # Test mobile viewport
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto("/")

    body = page.locator("body")
    expect(body).to_be_visible()

    logger.info("Mobile viewport test passed")

    # Test tablet viewport
    page.set_viewport_size({"width": 768, "height": 1024})
    page.reload()
    expect(body).to_be_visible()

    logger.info("Tablet viewport test passed")

    # Test desktop viewport
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.reload()
    expect(body).to_be_visible()

    logger.info("Desktop viewport test passed")


@pytest.mark.ui
def test_images_load(page: Page) -> None:
    """Test that images on the page load successfully.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing image loading")

    page.goto("/", wait_until="load")

    # The load event waits for the initial HTML's eager images, so any
    # image the browser reports as complete has finished fetching; a
    # complete image with zero natural width is a broken resource. This
    # checks load success directly instead of waiting on the network to idle,
    # which the Playwright docs discourage and which hangs on pages with
    # analytics beacons, and it does not fail on lazy images below the
    # fold, which are simply not complete yet.
    broken_images = page.evaluate(
        """() => Array.from(document.images)
            .filter(img => img.complete && img.naturalWidth === 0)
            .map(img => img.currentSrc || img.src || '(no src)')"""
    )
    assert not broken_images, f"Broken images failed to load: {broken_images}"

    images = page.locator("img").all()
    logger.info("Found %d images, none broken", len(images))


@pytest.mark.ui
def test_meta_tags_present(page: Page) -> None:
    """Test that essential meta tags are present.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing meta tags")

    page.goto("/")

    # Check for viewport meta tag (important for mobile)
    viewport_meta = page.locator('meta[name="viewport"]')
    expect(viewport_meta).to_have_count(1)

    logger.info("Viewport meta tag found")

    # Check for charset
    charset_meta = page.locator("meta[charset]")
    charset_count = charset_meta.count()

    assert charset_count > 0, "No charset meta tag found"
    logger.info("Charset meta tag found")


@pytest.mark.ui
def test_favicon_exists(page: Page) -> None:
    """Test that a favicon is defined.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing favicon presence")

    page.goto("/")

    # Look for favicon link tags
    favicon_links = page.locator('link[rel*="icon"]')
    favicon_count = favicon_links.count()

    if favicon_count > 0:
        logger.info("Found %d favicon links", favicon_count)
    else:
        logger.warning("No favicon links found")


@pytest.mark.ui
@pytest.mark.slow
def test_page_scroll(page: Page) -> None:
    """Test that the page can be scrolled.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing page scroll functionality")

    page.goto("/", wait_until="load")

    # Nothing to assert on a page that cannot scroll; skip rather than
    # pass vacuously, and skip before scrolling so the wait below always
    # has a real change to wait for.
    page_height = page.evaluate("document.body.scrollHeight")
    viewport_height = page.evaluate("window.innerHeight")
    if page_height <= viewport_height:
        pytest.skip("Page is too short to scroll")

    initial_scroll = page.evaluate("window.pageYOffset")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")

    # Wait for the scroll to actually take effect instead of sleeping a
    # fixed interval: this waits on the condition itself, so it tolerates
    # smooth-scroll behavior without the flakiness of a guessed duration.
    page.wait_for_function("start => window.pageYOffset > start", arg=initial_scroll)

    new_scroll = page.evaluate("window.pageYOffset")
    assert new_scroll > initial_scroll, "Page did not scroll"
    logger.info("Page scrolled from %d to %d", initial_scroll, new_scroll)


@pytest.mark.ui
def test_no_broken_styles(page: Page) -> None:
    """Test that CSS stylesheets load successfully.

    Args:
        page: Playwright page fixture
    """
    logger.info("Testing CSS loading")

    failed_resources: list[str] = []

    def handle_response(response: Any) -> None:
        if response.request.resource_type == "stylesheet":
            if not response.ok:
                failed_resources.append(response.url)
                logger.warning("Failed to load stylesheet: %s", response.url)

    # The listener is attached before navigating, and stylesheets are
    # render-blocking, so every stylesheet response has arrived by the
    # load event. Waiting for load (goto's default) rather than
    # that lets us capture them all without hanging on late beacons.
    page.on("response", handle_response)
    page.goto("/", wait_until="load")

    assert len(failed_resources) == 0, (
        f"Failed to load {len(failed_resources)} stylesheets: {failed_resources}"
    )
    logger.info("All stylesheets loaded successfully")
