"""Pytest configuration and fixtures for Site Sentry tests.

This module provides shared fixtures for Playwright browser automation,
configuration management, and test utilities.
"""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Browser, BrowserContext, Page

from tests.utils.logger import get_logger

# Create test-results directory immediately when conftest is imported
TEST_RESULTS_DIR = Path(__file__).parent.parent / "test-results"
TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv()

logger = get_logger(__name__)


@pytest.hookimpl(hookwrapper=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> Generator[None, None, None]:
    """Ensure test-results directory exists before HTML report writes.

    The hookwrapper=True makes this run around other sessionfinish hooks,
    and we recreate the directory right before yielding control.
    """
    TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Directory created, now pytest-html can write


@pytest.fixture(scope="session")
def base_url() -> str:
    """Get the base URL for the site under test.

    Returns:
        Base URL from environment or default
    """
    url = os.getenv("BASE_URL", "https://kyledarden.com")
    logger.info("Using base URL: %s", url)
    return url


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict[str, bool | int]:
    """Configure browser launch arguments.

    Returns:
        Dictionary of browser launch arguments
    """
    return {
        "headless": os.getenv("HEADLESS", "true").lower() == "true",
        "slow_mo": int(os.getenv("SLOWMO", "0")),
    }


@pytest.fixture(scope="session")
def browser_context_args(base_url: str) -> dict[str, dict[str, int] | str]:
    """Configure browser context arguments.

    Args:
        base_url: Base URL for the site

    Returns:
        Dictionary of browser context arguments
    """
    viewport: dict[str, int] = {
        "width": int(os.getenv("VIEWPORT_WIDTH", "1280")),
        "height": int(os.getenv("VIEWPORT_HEIGHT", "720")),
    }
    return {
        "viewport": viewport,
        "base_url": base_url,
    }


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Generator[Page, None, None]:
    """Create a new page for each test.

    Args:
        context: Browser context fixture

    Yields:
        New page instance
    """
    page = context.new_page()
    logger.info("Created new page")
    yield page
    logger.info("Closing page")
    page.close()


@pytest.fixture(scope="function")
def context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """Create a new browser context for each test.

    Args:
        browser: Browser fixture

    Yields:
        New browser context
    """
    context = browser.new_context()
    logger.info("Created new browser context")
    yield context
    logger.info("Closing browser context")
    context.close()


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom settings.

    Args:
        config: Pytest configuration object
    """
    # Register custom markers
    config.addinivalue_line("markers", "smoke: Quick smoke tests")
    config.addinivalue_line("markers", "ui: UI interaction tests")
    config.addinivalue_line("markers", "slow: Long-running tests")

    # Create test results directory
    results_dir = os.getenv("TEST_RESULTS_DIR", "test-results")
    os.makedirs(results_dir, exist_ok=True)

    screenshots_dir = os.path.join(results_dir, "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    logger.info("Test results directory: %s", results_dir)


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    """Hook to capture screenshots on test failure.

    Args:
        item: Test item
        call: Test call information
    """
    if call.when == "call" and call.excinfo is not None:
        # Test failed, capture screenshot if page fixture was used
        page = getattr(item, "funcargs", {}).get("page")
        if page:
            screenshot_dir = os.path.join(
                os.getenv("TEST_RESULTS_DIR", "test-results"), "screenshots"
            )
            screenshot_path = os.path.join(screenshot_dir, f"{item.name}.png")
            try:
                page.screenshot(path=screenshot_path)
                logger.info("Screenshot saved: %s", screenshot_path)
            except Exception as e:
                logger.error("Failed to capture screenshot: %s", e)
