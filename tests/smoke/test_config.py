"""Configuration plumbing tests.

Verifies that browser_context_args from conftest.py actually reach the
browser context. Guards against custom fixtures shadowing the
pytest-playwright built-ins and silently dropping configuration
(issue #26).
"""

import os

import pytest
from playwright.sync_api import Page

from tests.utils.logger import get_logger

logger = get_logger(__name__)


@pytest.mark.smoke
def test_viewport_matches_configuration(page: Page) -> None:
    """Test that the configured viewport is applied to the context.

    Args:
        page: Playwright page fixture
    """
    expected = {
        "width": int(os.getenv("VIEWPORT_WIDTH", "1280")),
        "height": int(os.getenv("VIEWPORT_HEIGHT", "720")),
    }
    logger.info("Expecting viewport: %s", expected)

    assert page.viewport_size == expected, (
        f"Viewport {page.viewport_size} does not match configuration {expected}; "
        "browser_context_args is not reaching the browser context"
    )
    logger.info("Viewport matches configuration")
