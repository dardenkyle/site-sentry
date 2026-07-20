"""Pytest configuration and fixtures for Site Sentry tests.

This module provides shared fixtures for Playwright browser automation,
configuration management, and test utilities.
"""

import json
import os
import statistics
import time
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Browser, Page
from playwright.sync_api import Error as PlaywrightError

from tests.utils.config import resolve_browsers, screenshots_dir
from tests.utils.logger import get_logger
from tests.utils.timing import (
    FIRST_NAVIGATION_TIMEOUT_MS,
    PAGE_LOAD_TIMEOUT_MS,
    FirstNavigation,
)

# Create test-results directory immediately when conftest is imported
TEST_RESULTS_DIR = Path(__file__).parent.parent / "test-results"
TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Tests slower than this count toward slow_count in durations.json
SLOW_TEST_THRESHOLD_SECONDS = 5.0

# Retry budget for smoke tests, which run against a live site and can
# lose a request to a transient stall. Scoped to smoke deliberately:
# retries buy noise reduction by discarding evidence, which is only
# worth it for the availability signal that gates incident alerts.
SMOKE_RERUNS = 2
SMOKE_RERUN_DELAY_SECONDS = 5

# Call-phase duration and outcome per attempt, keyed by test nodeid.
# A retried test appends rather than overwrites, so the slow attempt
# that triggered the retry survives into durations.json.
_test_durations: dict[str, list[tuple[float, str]]] = {}

# Load environment variables
load_dotenv()

logger = get_logger(__name__)


@pytest.fixture
def page(page: Page) -> Page:
    """Apply the suite's deliberate navigation timeout to every page.

    Without this, each page.goto inherits Playwright's implicit 30s
    default, which is how an unchosen value became the de facto
    performance gate. Setting it here rather than per call site means a
    new test cannot silently opt back into the default.

    Args:
        page: The plugin's built-in page fixture

    Returns:
        The same page with an explicit navigation timeout applied
    """
    page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)
    return page


@pytest.fixture(scope="session", autouse=True)
def first_navigation(browser: Browser, base_url: str) -> FirstNavigation:
    """Measure the session's first navigation to the site under test.

    Runs before any test (autouse, session scope) in its own context, so
    this is the one navigation taken before the suite has warmed
    anything it can warm: connection setup (DNS, TCP, TLS) has not yet
    happened in this process. Every later timing reuses that state.

    This is deliberately not a cache-cold measurement. The site sits
    behind a CDN whose edge cache is warm regardless of what the suite
    does, and pytest-playwright already gives every test a fresh context
    with an empty browser cache, so cache state is not what sets this
    navigation apart. Connection setup is.

    Navigation failures are captured rather than raised: raising here
    would error every test in the session and misreport a single slow
    request as a total outage. The smoke test that consumes this decides
    what the numbers mean.

    Args:
        browser: Session-scoped Playwright browser from pytest-playwright
        base_url: Base URL of the site under test

    Returns:
        Elapsed seconds and any navigation error
    """
    context = browser.new_context(base_url=base_url)
    error: str | None = None
    start = time.perf_counter()
    try:
        page = context.new_page()
        page.goto("/", wait_until="load", timeout=FIRST_NAVIGATION_TIMEOUT_MS)
    except PlaywrightError as exc:
        error = str(exc)
    finally:
        seconds = time.perf_counter() - start
        context.close()
    logger.info("First navigation took %.2fs (error: %s)", seconds, error)
    return FirstNavigation(seconds=seconds, error=error)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Grant smoke tests a retry budget, and nothing else.

    Retries are applied here rather than via a global --reruns flag so
    they cannot silently extend to the UI suite, where a rerun would
    mask a real regression instead of a transient network stall.

    Tests marked no_rerun still run normally, they just do not receive
    the retry marker: a test whose verdict comes from a session-scoped
    measurement re-reads the same cached value on every attempt, so
    retrying it only burns the rerun delay.

    Args:
        items: Collected test items, mutated in place
    """
    retry = pytest.mark.flaky(reruns=SMOKE_RERUNS, reruns_delay=SMOKE_RERUN_DELAY_SECONDS)
    for item in items:
        if item.get_closest_marker("smoke") and not item.get_closest_marker("no_rerun"):
            item.add_marker(retry)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Record the call-phase duration and outcome of every attempt.

    Setup and teardown phases are excluded so the numbers reflect what
    the test itself did (navigation, requests, assertions), not fixture
    overhead. Attempts append rather than overwrite: a retried test
    would otherwise report only its fast passing attempt, hiding the
    stall that caused the retry. Durations feed durations.json.

    Args:
        report: Per-phase report emitted by pytest for each attempt
    """
    if report.when == "call":
        _test_durations.setdefault(report.nodeid, []).append((report.duration, report.outcome))


def _write_durations_file() -> None:
    """Aggregate collected durations and write test-results/durations.json.

    The 30s-timeout investigation (#58) showed the suite's duration
    distribution drifting toward the Playwright timeout with zero warning,
    because pass/fail discards timing. This persists per-test durations
    plus aggregates every run, so drift shows up as a trend in the
    uploaded artifacts weeks before it trips timeouts. Stdlib only.

    Per-test durations report the slowest attempt, not the last one, so
    a stall that a retry papered over still lands in the file and in the
    aggregates. Every attempt of a retried test is preserved in full
    under "retried".
    """
    worst = {nodeid: max(d for d, _ in attempts) for nodeid, attempts in _test_durations.items()}
    retried = {
        nodeid: [
            {"attempt": i, "duration": round(d, 3), "outcome": outcome}
            for i, (d, outcome) in enumerate(attempts, start=1)
        ]
        for nodeid, attempts in sorted(_test_durations.items())
        if len(attempts) > 1
    }
    durations = sorted(worst.values())
    if len(durations) >= 2:
        # method="inclusive" interpolates within the observed range, so
        # p95 can never exceed max_duration as the default method can
        p95 = statistics.quantiles(durations, n=20, method="inclusive")[-1]
    else:
        p95 = durations[0]
    run_number = os.getenv("GITHUB_RUN_NUMBER")
    payload = {
        "run_id": os.getenv("GITHUB_RUN_ID", "local"),
        "run_number": int(run_number) if run_number else None,
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "durations": {nodeid: round(d, 3) for nodeid, d in sorted(worst.items())},
        "retried": retried,
        "retried_count": len(retried),
        "max_duration": round(durations[-1], 3),
        "median_duration": round(statistics.median(durations), 3),
        "p95_duration": round(p95, 3),
        "slow_count": sum(1 for d in durations if d > SLOW_TEST_THRESHOLD_SECONDS),
    }
    results_dir = Path(os.getenv("TEST_RESULTS_DIR", str(TEST_RESULTS_DIR)))
    results_dir.mkdir(parents=True, exist_ok=True)
    durations_path = results_dir / "durations.json"
    durations_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Duration metrics saved: %s", durations_path)


@pytest.hookimpl(hookwrapper=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> Generator[None, None, None]:
    """Ensure test-results directory exists before HTML report writes.

    The hookwrapper=True makes this run around other sessionfinish hooks,
    and we recreate the directory right before yielding control. Duration
    metrics are written here too, once all test reports are in.
    """
    TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if _test_durations:
        _write_durations_file()
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

    CLI options take precedence over env vars: the plugin only emits
    headless/slow_mo when --headed/--slowmo are passed, and values that
    load_dotenv() picked up from a .env file must not disable them.

    Args:
        browser_type_launch_args: The plugin's built-in launch arguments

    Returns:
        Launch arguments with HEADLESS/SLOWMO overrides applied
    """
    launch_args = dict(browser_type_launch_args)
    if "HEADLESS" in os.environ and "headless" not in launch_args:
        launch_args["headless"] = os.environ["HEADLESS"].lower() == "true"
    if "SLOWMO" in os.environ and "slow_mo" not in launch_args:
        launch_args["slow_mo"] = int(os.environ["SLOWMO"])
    return launch_args


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    """Extend pytest-playwright's context arguments with env overrides.

    The plugin's arguments already carry base_url, --device presets, and
    --video recording. A --device preset supplies its own viewport and
    takes precedence; the env viewport (often loaded from .env) is
    applied only when no preset did, so presets are never clobbered,
    fully or partially.

    Args:
        browser_context_args: The plugin's built-in context arguments

    Returns:
        Context arguments with the configured viewport applied
    """
    context_args = dict(browser_context_args)
    env_viewport = "VIEWPORT_WIDTH" in os.environ or "VIEWPORT_HEIGHT" in os.environ
    if env_viewport and "viewport" not in context_args:
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
    config.addinivalue_line("markers", "no_rerun: Exempt from the smoke retry budget")

    # Honor BROWSER when no --browser was passed. pytest_generate_tests
    # reads config.option.browser (falling back to chromium), and this
    # hook runs before it, so setting it here selects the browser env
    # override with the same CLI-wins semantics as HEADLESS/SLOWMO.
    browsers = resolve_browsers(config.getoption("browser") or [], os.environ)
    if browsers is not None:
        config.option.browser = browsers

    # Create test results and screenshots directories
    results_dir = os.getenv("TEST_RESULTS_DIR", "test-results")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(screenshots_dir(os.environ), exist_ok=True)

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
            screenshot_dir = screenshots_dir(os.environ)
            screenshot_path = str(screenshot_dir / f"{item.name}.png")
            try:
                page.screenshot(path=screenshot_path)
                logger.info("Screenshot saved: %s", screenshot_path)
            except Exception as e:
                logger.error("Failed to capture screenshot: %s", e)
