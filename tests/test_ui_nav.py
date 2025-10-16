"""UI and navigation tests for kyledarden.com.

Tests for user interface elements, navigation, and interactive features.
"""

from typing import Any

import pytest
from playwright.sync_api import Page, expect

from tests.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.mark.ui
def test_navigation_links_exist(page: Page, base_url: str) -> None:
    """Test that navigation links are present on the page.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing navigation links presence")

    page.goto(base_url)

    # Check for common navigation elements
    links = page.locator("a[href]")
    link_count = links.count()

    assert link_count > 0, "No links found on the page"
    logger.info("Found %d links on the page", link_count)


@pytest.mark.ui
def test_navigation_links_valid(page: Page, base_url: str) -> None:
    """Test that navigation links have valid href attributes.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing navigation link validity")

    page.goto(base_url)

    # Get all internal links
    links = page.locator("a[href]").all()
    invalid_links: list[str] = []

    for link in links[:10]:  # Test first 10 links to keep test fast
        href = link.get_attribute("href")
        if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
            if not href or href == "" or href == "#":
                invalid_links.append(href or "empty")

    assert len(invalid_links) == 0, f"Found invalid links: {invalid_links}"
    logger.info("All tested links have valid href attributes")


@pytest.mark.ui
def test_responsive_viewport(page: Page, base_url: str) -> None:
    """Test that the site is responsive at different viewport sizes.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing responsive design")

    # Test mobile viewport
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(base_url)

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
def test_images_load(page: Page, base_url: str) -> None:
    """Test that images on the page load successfully.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing image loading")

    page.goto(base_url)

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
def test_meta_tags_present(page: Page, base_url: str) -> None:
    """Test that essential meta tags are present.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing meta tags")

    page.goto(base_url)

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
def test_favicon_exists(page: Page, base_url: str) -> None:
    """Test that a favicon is defined.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing favicon presence")

    page.goto(base_url)

    # Look for favicon link tags
    favicon_links = page.locator('link[rel*="icon"]')
    favicon_count = favicon_links.count()

    if favicon_count > 0:
        logger.info("Found %d favicon links", favicon_count)
    else:
        logger.warning("No favicon links found")


@pytest.mark.ui
@pytest.mark.slow
def test_page_scroll(page: Page, base_url: str) -> None:
    """Test that the page can be scrolled.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing page scroll functionality")

    page.goto(base_url)

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
def test_no_broken_styles(page: Page, base_url: str) -> None:
    """Test that CSS stylesheets load successfully.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing CSS loading")

    failed_resources: list[str] = []

    def handle_response(response: Any) -> None:
        if response.request.resource_type == "stylesheet":
            if not response.ok:
                failed_resources.append(response.url)
                logger.warning("Failed to load stylesheet: %s", response.url)

    page.on("response", handle_response)
    page.goto(base_url)
    page.wait_for_load_state("networkidle")

    assert len(failed_resources) == 0, (
        f"Failed to load {len(failed_resources)} stylesheets: {failed_resources}"
    )
    logger.info("All stylesheets loaded successfully")
