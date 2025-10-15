"""Smoke tests for kyledarden.com.

Fast, critical tests that verify core functionality and site availability.
These tests should run quickly and catch major breakages.
"""

import pytest
from playwright.sync_api import Page, expect

from tests.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.mark.smoke
def test_homepage_loads(page: Page, base_url: str) -> None:
    """Test that the homepage loads successfully.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info(f"Testing homepage load: {base_url}")
    
    response = page.goto(base_url)
    assert response is not None, "No response received"
    assert response.ok, f"Response not OK: {response.status}"
    
    logger.info(f"Homepage loaded successfully with status {response.status}")


@pytest.mark.smoke
def test_homepage_title(page: Page, base_url: str) -> None:
    """Test that the homepage has a proper title.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing homepage title")
    
    page.goto(base_url)
    title = page.title()
    
    assert title, "Page title is empty"
    assert len(title) > 0, "Page title has no content"
    
    logger.info(f"Page title: {title}")


@pytest.mark.smoke
def test_no_console_errors(page: Page, base_url: str) -> None:
    """Test that the homepage loads without console errors.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing for console errors")
    
    console_errors: list[str] = []
    
    def handle_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)
            logger.warning(f"Console error: {msg.text}")
    
    page.on("console", handle_console)
    page.goto(base_url)
    
    # Wait a moment for any delayed console errors
    page.wait_for_timeout(1000)
    
    assert len(console_errors) == 0, f"Found {len(console_errors)} console errors: {console_errors}"
    logger.info("No console errors found")


@pytest.mark.smoke
def test_response_time(page: Page, base_url: str) -> None:
    """Test that the homepage loads within acceptable time.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing page load time")
    
    import time
    start_time = time.time()
    
    response = page.goto(base_url, wait_until="load")
    
    load_time = time.time() - start_time
    
    assert response is not None, "No response received"
    assert load_time < 5.0, f"Page took {load_time:.2f}s to load (expected < 5s)"
    
    logger.info(f"Page loaded in {load_time:.2f}s")


@pytest.mark.smoke
def test_main_content_visible(page: Page, base_url: str) -> None:
    """Test that main content is visible on the homepage.

    Args:
        page: Playwright page fixture
        base_url: Base URL fixture
    """
    logger.info("Testing main content visibility")
    
    page.goto(base_url)
    
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
    
    logger.info(f"Successfully redirected to: {final_url}")
