"""Target-derivation tests.

Verifies that the URLs tests contact are derived from the configured
base URL rather than hardcoded. Guards against a reintroduction of
issue #28, where test_https_redirect contacted production regardless of
BASE_URL. Runs offline: no browser, no network.
"""

from urllib.parse import urlsplit

import pytest

from tests.utils.urls import http_variant, is_local, same_site

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
@pytest.mark.parametrize(
    "configured_url",
    [
        "https://staging.example.com",
        # A host that merely contains the production name must not be
        # mistaken for it, which a substring check would get wrong
        "https://staging.kyledarden.com",
    ],
)
def test_http_variant_never_reaches_production_for_other_targets(configured_url: str) -> None:
    """Test that a non-production base URL yields no production target.

    This is the acceptance criterion of issue #28 stated directly: a run
    pointed elsewhere must not contact kyledarden.com itself.

    Args:
        configured_url: Base URL a run could be pointed at
    """
    derived_host = urlsplit(http_variant(configured_url)).hostname

    assert derived_host != PRODUCTION_HOST, f"Derived URL leaks production host: {derived_host}"


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("landed_on", "configured_url", "expected"),
    [
        ("https://kyledarden.com/", "https://kyledarden.com", True),
        # kyledarden.com canonicalizes www to the apex, so a run pointed
        # at the www host lands here and must not be called a failure
        ("https://kyledarden.com/", "https://www.kyledarden.com", True),
        # Other sites canonicalize the other way
        ("https://www.example.com/", "https://example.com", True),
        # An unrelated host is still a different site
        ("https://kyledarden.com/", "https://staging.example.com", False),
        ("https://kyledarden.com/", "https://staging.kyledarden.com", False),
    ],
)
def test_same_site_allows_www_hops_only(
    landed_on: str, configured_url: str, expected: bool
) -> None:
    """Test that apex/www counts as one site and unrelated hosts do not.

    This is what keeps the redirect assertion honest: strict enough that
    landing on production is caught, loose enough that a legitimate
    canonicalizing hop is not reported as a failure.

    Args:
        landed_on: URL the redirect finished on
        configured_url: Base URL a run could be pointed at
        expected: Whether the two address the same site
    """
    assert same_site(landed_on, configured_url) is expected


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
