"""Canonical schema for a single QA run record.

One RunRecord is the unit the store holds and the dashboard charts: it
joins test outcomes (from junit.xml), timing aggregates (from
durations.json), and the site's measured latency (from navigation.json)
into one row keyed by run_id. The dataclasses here are the documented
contract for that row; SCHEMA_VERSION is bumped whenever a field's
meaning changes so old and new records in the store stay distinguishable.

The dashboard and the aggregate stage read records back as plain JSON
dicts, so only the write direction (to_dict) lives here; the field names
below are the schema those readers depend on.
"""

from dataclasses import asdict, dataclass
from typing import Any

# Bump when a field is renamed, removed, or has its meaning changed, so a
# record written under an old contract is never silently misread. Adding
# an optional field is backwards compatible and does not require a bump.
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TestCase:
    """Outcome and call-phase duration of one test in the run.

    Attributes:
        nodeid: Test identity as classname::name from the junit report
        outcome: One of passed, failed, error, skipped
        duration_s: Call-phase duration in seconds, from the junit time
    """

    nodeid: str
    outcome: str
    duration_s: float


@dataclass(frozen=True)
class TestCounts:
    """Aggregate pass/fail tally for the run.

    pass_rate excludes skips from the denominator: a skipped test made no
    assertion about the site, so counting it as neither pass nor fail
    keeps the rate a statement about tests that actually ran. A run with
    nothing but skips has an undefined rate, reported as None.

    Attributes:
        total: Every testcase in the report, skips included
        passed: Tests that passed
        failed: Tests with a failure (assertion) result
        errors: Tests with an error (collection or fixture crash) result
        skipped: Tests that were skipped
        pass_rate: passed / (passed + failed + errors), or None when that
            denominator is zero
    """

    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    pass_rate: float | None


@dataclass(frozen=True)
class DurationStats:
    """Timing aggregates for the run, in seconds.

    Sourced from durations.json (per-test call-phase durations, worst
    attempt) except wall_s, which is the junit testsuite wall time.

    Attributes:
        max_s: Slowest single test
        median_s: Median test duration
        p95_s: 95th-percentile test duration
        slow_count: Tests over the slow threshold
        retried_count: Tests that took more than one attempt
        wall_s: Total wall-clock time of the run, or None if unknown
    """

    max_s: float | None
    median_s: float | None
    p95_s: float | None
    slow_count: int | None
    retried_count: int | None
    wall_s: float | None


@dataclass(frozen=True)
class NavigationStats:
    """The site's own latency for the session's first navigation.

    Milliseconds from navigation start, measured by the browser via the
    Navigation Timing API (see tests/utils/timing.py). All timings are
    None when the navigation failed; error then carries why.

    Attributes:
        error: Navigation error message, or None when it completed
        ttfb_ms: Time to first byte
        dom_content_loaded_ms: domContentLoaded mark
        load_ms: load mark, all initial subresources done
        connect_ms: TCP + TLS connection established
    """

    error: str | None
    ttfb_ms: float | None
    dom_content_loaded_ms: float | None
    load_ms: float | None
    connect_ms: float | None


@dataclass(frozen=True)
class RunRecord:
    """One QA run, normalized across all of its raw artifacts.

    Attributes:
        schema_version: The SCHEMA_VERSION this record was written under
        run_id: CI run id, the store's dedupe key ("local" off CI)
        run_number: Human-facing CI run number, or None off CI
        timestamp: ISO-8601 UTC instant the run's metrics were written
        trigger: What started the run (schedule, push, workflow_dispatch)
        browser: Engine the run exercised
        commit_sha: Commit the run tested, or None off CI
        counts: Pass/fail tally
        duration: Timing aggregates
        navigation: Site latency for the first navigation
        cases: Per-test outcomes and durations
    """

    schema_version: int
    run_id: str
    run_number: int | None
    timestamp: str
    trigger: str
    browser: str | None
    commit_sha: str | None
    counts: TestCounts
    duration: DurationStats
    navigation: NavigationStats
    cases: list[TestCase]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON-ready dict stored and charted.

        Returns:
            A nested dict mirroring this record's fields, JSON-encodable
        """
        return asdict(self)
