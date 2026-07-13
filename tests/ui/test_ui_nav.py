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

# Generous bound that always includes the injected canary link, which
# sits last in the DOM
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

    page.goto("/")

    # Wait for images to load
    page.wait_for_load_state("networkidle")

    images = page.locator("img").all()
    image_count = len(images)

    if image_count > 0:
        logger.info("Found %d images", image_count)

        # Check that images have src attributes
        for img in images[:5]:  # Test first 5 images
            src = img.get_attribute("src")
            assert src, "Image missing src attribute"
            assert len(src) > 0, "Image has empty src attribute"

        logger.info("Image sources are valid")
    else:
        logger.info("No images found on page")


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

    page.goto("/")

    # Get initial scroll position
    initial_scroll = page.evaluate("window.pageYOffset")

    # Scroll down
    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")

    # Wait a moment for scroll to complete
    page.wait_for_timeout(500)

    # Get new scroll position
    new_scroll = page.evaluate("window.pageYOffset")

    # If page is long enough, scroll position should have changed
    page_height = page.evaluate("document.body.scrollHeight")
    viewport_height = page.evaluate("window.innerHeight")

    if page_height > viewport_height:
        assert new_scroll > initial_scroll, "Page did not scroll"
        logger.info("Page scrolled from %d to %d", initial_scroll, new_scroll)
    else:
        logger.info("Page is too short to scroll")


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

    page.on("response", handle_response)
    page.goto("/")
    page.wait_for_load_state("networkidle")

    assert len(failed_resources) == 0, (
        f"Failed to load {len(failed_resources)} stylesheets: {failed_resources}"
    )
    logger.info("All stylesheets loaded successfully")
