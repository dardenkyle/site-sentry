"""Pytest configuration and fixtures for Site Sentry tests.

This module provides shared fixtures for Playwright browser automation,
configuration management, and test utilities.
"""

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

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
def base_url(request: pytest.FixtureRequest) -> str:
    """Get the base URL for the site under test.

    Overrides pytest-base-url's fixture so BASE_URL from the environment
    is honored. The --base-url CLI option still wins when passed, and
    pytest-playwright applies the result to every browser context, so
    tests can navigate relatively via page.goto("/").

    Args:
        request: Pytest fixture request, used to read the CLI option

    Returns:
        Base URL from CLI option, environment, or default
    """
    cli_url: str | None = request.config.getoption("--base-url")
    url = cli_url if cli_url else os.getenv("BASE_URL", "https://kyledarden.com")
    logger.info("Using base URL: %s", url)
    return url


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict[str, Any]) -> dict[str, Any]:
    """Extend pytest-playwright's launch arguments with env overrides.

    Env vars are applied only when explicitly set, so the plugin's CLI
    options (--headed, --slowmo, --browser-channel) keep working.

    Args:
        browser_type_launch_args: The plugin's built-in launch arguments

    Returns:
        Launch arguments with HEADLESS/SLOWMO overrides applied
    """
    launch_args = dict(browser_type_launch_args)
    if "HEADLESS" in os.environ:
        launch_args["headless"] = os.environ["HEADLESS"].lower() == "true"
    if "SLOWMO" in os.environ:
        launch_args["slow_mo"] = int(os.environ["SLOWMO"])
    return launch_args


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    """Extend pytest-playwright's context arguments with env overrides.

    The plugin's arguments already carry base_url, --device presets, and
    --video recording; the viewport is only overridden when configured,
    so device presets are not clobbered by defaults.

    Args:
        browser_context_args: The plugin's built-in context arguments

    Returns:
        Context arguments with the configured viewport applied
    """
    context_args = dict(browser_context_args)
    if "VIEWPORT_WIDTH" in os.environ or "VIEWPORT_HEIGHT" in os.environ:
        context_args["viewport"] = {
            "width": int(os.getenv("VIEWPORT_WIDTH", "1280")),
            "height": int(os.getenv("VIEWPORT_HEIGHT", "720")),
        }
    return context_args


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
