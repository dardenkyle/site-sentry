"""URL helpers for deriving test targets from the configured base URL.

Every target a test contacts must come from base_url. Hardcoding a host
in a test (issue #28) means a run pointed at staging still hits
production, which makes that test wrong in any non-production run.
"""

from urllib.parse import urlsplit, urlunsplit

# Hostnames that resolve to the developer's own machine, where an HTTPS
# base URL is served directly rather than fronted by a redirecting edge.
LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})


def http_variant(base_url: str) -> str:
    """Return base_url with its scheme swapped to plain HTTP.

    Host, port, and path are preserved so the result addresses the same
    target; query and fragment are dropped because a redirect probe has
    no use for them.

    Args:
        base_url: Base URL of the site under test

    Returns:
        The same target addressed over http
    """
    parsed = urlsplit(base_url)
    return urlunsplit(("http", parsed.netloc, parsed.path or "/", "", ""))


def same_site(url: str, other: str) -> bool:
    """Report whether two URLs address the same site.

    A leading "www." is ignored on either side, because canonicalizing
    between the apex and the www host is a normal redirect and not the
    kind of host change worth failing over. kyledarden.com canonicalizes
    www to the apex; other targets go the other way, and a check that
    fixed a direction would produce false failures on one of them.

    Comparison is otherwise exact, so an unrelated host (production, a
    parked domain) is still reported as a different site.

    Args:
        url: First URL to compare
        other: Second URL to compare

    Returns:
        True when both address the same site
    """
    return _site_host(url) == _site_host(other)


def _site_host(url: str) -> str | None:
    """Return the hostname of url with any leading "www." removed.

    Args:
        url: URL to take the hostname from

    Returns:
        The bare hostname, or None when the URL carries no host
    """
    host = urlsplit(url).hostname
    return host.removeprefix("www.") if host else host


def is_local(base_url: str) -> bool:
    """Report whether base_url points at the local machine.

    Args:
        base_url: Base URL of the site under test

    Returns:
        True when the host is a loopback name or address
    """
    return urlsplit(base_url).hostname in LOCAL_HOSTNAMES
