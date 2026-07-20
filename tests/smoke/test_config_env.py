"""Configuration-resolution tests.

Pins the env-to-setting helpers that back the documented BROWSER and
SCREENSHOTS_DIR variables, so a documented setting cannot silently
regress to doing nothing (issue #29). The resolution runs offline; a
separate live check confirms BROWSER actually selects the running
browser.
"""

import os
from pathlib import Path

import pytest

from tests.utils.config import resolve_browsers, screenshots_dir


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("cli_browsers", "env", "expected"),
    [
        # BROWSER fills in when no --browser was passed
        ([], {"BROWSER": "firefox"}, ["firefox"]),
        # A --browser CLI option wins; BROWSER is ignored
        (["webkit"], {"BROWSER": "firefox"}, None),
        # Nothing configured: leave the plugin default untouched
        ([], {}, None),
    ],
)
def test_resolve_browsers(
    cli_browsers: list[str], env: dict[str, str], expected: list[str] | None
) -> None:
    """Test that BROWSER is honored only when no CLI browser was given.

    Args:
        cli_browsers: Browsers from the --browser option
        env: Environment mapping under test
        expected: The browser list to apply, or None to change nothing
    """
    assert resolve_browsers(cli_browsers, env) == expected


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("env", "expected"),
    [
        # SCREENSHOTS_DIR, when set, is used verbatim
        ({"SCREENSHOTS_DIR": "/tmp/shots"}, Path("/tmp/shots")),
        # otherwise it falls back under TEST_RESULTS_DIR
        ({"TEST_RESULTS_DIR": "out"}, Path("out/screenshots")),
        # and to the default results dir when neither is set
        ({}, Path("test-results/screenshots")),
        # SCREENSHOTS_DIR wins even when TEST_RESULTS_DIR is also set
        (
            {"SCREENSHOTS_DIR": "shots", "TEST_RESULTS_DIR": "out"},
            Path("shots"),
        ),
    ],
)
def test_screenshots_dir(env: dict[str, str], expected: Path) -> None:
    """Test that the screenshots directory honors its variables.

    Args:
        env: Environment mapping under test
        expected: The directory failure screenshots should land in
    """
    assert screenshots_dir(env) == expected


@pytest.mark.smoke
def test_browser_env_selects_running_browser(
    browser_name: str, pytestconfig: pytest.Config
) -> None:
    """Test that BROWSER selects the browser the session actually runs.

    This closes the loop the offline test cannot: it proves the resolved
    value reached pytest-playwright and drove browser selection, not just
    that the helper computed it. Skipped unless BROWSER is the setting in
    effect, which means it is set and no --browser CLI option overrode
    it, matching resolve_browsers' precedence.

    Args:
        browser_name: The running browser, from pytest-playwright
        pytestconfig: Session config, used to detect a --browser option
    """
    # config.option.browser cannot answer this: pytest_configure already
    # overwrote it with the env value, erasing the CLI-vs-env distinction.
    # The raw invocation args still carry what the user actually typed.
    raw_args = pytestconfig.invocation_params.args
    if any(arg == "--browser" or arg.startswith("--browser=") for arg in raw_args):
        pytest.skip("--browser CLI option overrides BROWSER; env has no effect here")
    if not os.getenv("BROWSER"):
        pytest.skip("BROWSER not set; nothing to prove about its effect")

    assert browser_name == os.environ["BROWSER"], (
        f"BROWSER={os.environ['BROWSER']} did not select the running browser ({browser_name})"
    )
