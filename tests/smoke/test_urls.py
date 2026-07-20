"""Target-derivation tests.

Verifies that the URLs tests contact are derived from the configured
base URL rather than hardcoded. Guards against a reintroduction of
issue #28, where test_https_redirect contacted production regardless of
BASE_URL. Runs offline: no browser, no network.
"""

import pytest

from tests.utils.urls import http_variant, is_local

# The production default. A derived URL may only name this host when the
# base URL did, which is what makes BASE_URL redirection trustworthy.
PRODUCTION_HOST = "kyledarden.com"


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("configured_url", "expected"),
    [
        ("https://kyledarden.com", "http://kyledarden.com/"),
        ("https://staging.example.com", "http://staging.example.com/"),
        ("https://staging.example.com/", "http://staging.example.com/"),
        ("https://staging.example.com/app", "http://staging.example.com/app"),
        ("https://staging.example.com:8443", "http://staging.example.com:8443/"),
        ("https://staging.example.com?debug=1", "http://staging.example.com/"),
    ],
)
def test_http_variant_preserves_target(configured_url: str, expected: str) -> None:
    """Test that only the scheme changes when deriving the HTTP URL.

    Args:
        configured_url: Base URL a run could be pointed at
        expected: The HTTP URL that addresses the same target
    """
    assert http_variant(configured_url) == expected


@pytest.mark.smoke
def test_http_variant_never_reaches_production_for_other_targets() -> None:
    """Test that a non-production base URL yields no production target.

    This is the acceptance criterion of issue #28 stated directly: a run
    pointed at staging must not contact kyledarden.com.
    """
    derived = http_variant("https://staging.example.com")

    assert PRODUCTION_HOST not in derived, f"Derived URL leaks production host: {derived}"


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("configured_url", "expected"),
    [
        ("https://localhost:3000", True),
        ("http://127.0.0.1:8000", True),
        ("https://kyledarden.com", False),
        ("https://localhost.example.com", False),
    ],
)
def test_is_local_identifies_loopback_targets(configured_url: str, expected: bool) -> None:
    """Test that loopback targets are recognized and others are not.

    The suffixed hostname case matters: a substring check would skip the
    redirect test against a real remote host named localhost.example.com.

    Args:
        configured_url: Base URL a run could be pointed at
        expected: Whether the host resolves to the local machine
    """
    assert is_local(configured_url) is expected
