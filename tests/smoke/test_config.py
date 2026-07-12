"""Configuration plumbing tests.

Verifies that browser_context_args from conftest.py actually reach the
browser context. Guards against custom fixtures shadowing the
pytest-playwright built-ins and silently dropping configuration
(issue #26).
"""

from typing import Any

import pytest
from playwright.sync_api import Page

from tests.utils.logger import get_logger

logger = get_logger(__name__)

# Playwright's built-in default, used when no viewport is configured
PLAYWRIGHT_DEFAULT_VIEWPORT = {"width": 1280, "height": 720}


@pytest.mark.smoke
def test_viewport_matches_configuration(page: Page, browser_context_args: dict[str, Any]) -> None:
    """Test that the configured viewport is applied to the context.

    The expectation is derived from the resolved browser_context_args,
    so it holds for env overrides, --device presets, and the plugin
    default alike.

    Args:
        page: Playwright page fixture
        browser_context_args: Resolved browser context arguments
    """
    expected = browser_context_args.get("viewport", PLAYWRIGHT_DEFAULT_VIEWPORT)
    logger.info("Expecting viewport: %s", expected)

    assert page.viewport_size == expected, (
        f"Viewport {page.viewport_size} does not match configuration {expected}; "
        "browser_context_args is not reaching the browser context"
    )
    logger.info("Viewport matches configuration")
