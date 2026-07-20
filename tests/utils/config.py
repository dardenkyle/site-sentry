"""Environment-driven configuration helpers.

Keeps the resolution of documented environment variables in pure
functions so each variable's effect can be pinned offline, without a
browser or a live pytest session. Issue #29: a documented setting that
silently does nothing is worse than none, because users change it and
see no effect.
"""

from collections.abc import Mapping
from pathlib import Path

# Where failure screenshots land when SCREENSHOTS_DIR is unset: a
# subdirectory of the results dir, which is where the hook wrote
# unconditionally before the variable was honored.
DEFAULT_RESULTS_DIR = "test-results"
SCREENSHOTS_SUBDIR = "screenshots"


def resolve_browsers(cli_browsers: list[str], env: Mapping[str, str]) -> list[str] | None:
    """Resolve which browsers to run from the CLI option and BROWSER env.

    A --browser CLI option always wins: when the user passed one,
    cli_browsers is non-empty and BROWSER is ignored, mirroring how
    HEADLESS and SLOWMO defer to their CLI flags. BROWSER fills in only
    when no CLI browser was given. Returning None means "change nothing",
    so pytest-playwright keeps its own default of chromium.

    Args:
        cli_browsers: Browsers from the --browser option (may be empty)
        env: Environment mapping to read BROWSER from

    Returns:
        The browser list to apply, or None to leave the plugin default
    """
    if cli_browsers:
        return None
    browser = env.get("BROWSER")
    return [browser] if browser else None


def screenshots_dir(env: Mapping[str, str]) -> Path:
    """Resolve the directory that failure screenshots are written to.

    Honors SCREENSHOTS_DIR when set; otherwise falls back to the
    screenshots subdirectory of TEST_RESULTS_DIR, preserving the path
    the hook used before SCREENSHOTS_DIR was wired in.

    Args:
        env: Environment mapping to read SCREENSHOTS_DIR/TEST_RESULTS_DIR from

    Returns:
        Directory path for failure screenshots
    """
    explicit = env.get("SCREENSHOTS_DIR")
    if explicit:
        return Path(explicit)
    results = env.get("TEST_RESULTS_DIR", DEFAULT_RESULTS_DIR)
    return Path(results) / SCREENSHOTS_SUBDIR
