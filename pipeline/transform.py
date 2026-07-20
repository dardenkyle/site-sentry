"""Transform a run's raw artifacts into one canonical run record.

Reads the three artifacts a QA run leaves in test-results/ - junit.xml
(test outcomes), durations.json (timing aggregates), navigation.json
(site latency) - and normalizes them into a RunRecord keyed by run_id.
The record is written to a partitioned path (runs/dt=YYYY-MM-DD/run-<id>)
so the load stage can commit it to the store without collisions, and the
run_id filename makes a re-run overwrite in place rather than duplicate.

Each input is optional: a run that died before pytest wrote junit.xml
still yields a record (with empty counts) rather than nothing, so an
outage is visible in the history instead of being a gap. Stdlib only.
"""

import argparse
import json
import os
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.schema import (
    SCHEMA_VERSION,
    DurationStats,
    NavigationStats,
    RunRecord,
    TestCase,
    TestCounts,
)

DEFAULT_RESULTS_DIR = "test-results"
JUNIT_NAME = "junit.xml"
DURATIONS_NAME = "durations.json"
NAVIGATION_NAME = "navigation.json"


def load_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON object from disk, tolerating absence and corruption.

    A missing or malformed artifact means the run died before writing it,
    which is a data point (an incomplete run), not a crash for the
    pipeline. Both cases return None so the caller records what it has.

    Args:
        path: Path to a JSON file expected to hold an object

    Returns:
        The parsed object, or None when the file is missing or unreadable
    """
    result: dict[str, Any] | None = None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        loaded = None
    if isinstance(loaded, dict):
        result = loaded
    return result


def parse_junit(root: ET.Element) -> tuple[TestCounts, list[TestCase], float | None]:
    """Extract counts, per-test cases, and wall time from a junit tree.

    Counts are derived from the testcases themselves rather than the
    testsuite attributes, so they can never disagree with the per-test
    list the record also carries. Wall time sums every testsuite's time
    attribute to stay correct if pytest ever emits more than one suite.

    Args:
        root: Parsed junit root, a <testsuites> or bare <testsuite>

    Returns:
        The pass/fail counts, the per-test cases, and total wall seconds
        (None when no testsuite carried a time attribute)
    """
    cases: list[TestCase] = []
    for case in root.iter("testcase"):
        classname = case.get("classname") or ""
        name = case.get("name") or ""
        nodeid = f"{classname}::{name}" if classname else name
        if case.find("failure") is not None:
            outcome = "failed"
        elif case.find("error") is not None:
            outcome = "error"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        cases.append(TestCase(nodeid, outcome, round(float(case.get("time") or 0.0), 3)))
    passed = sum(1 for c in cases if c.outcome == "passed")
    failed = sum(1 for c in cases if c.outcome == "failed")
    errors = sum(1 for c in cases if c.outcome == "error")
    skipped = sum(1 for c in cases if c.outcome == "skipped")
    ran = passed + failed + errors
    counts = TestCounts(
        total=len(cases),
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        pass_rate=round(passed / ran, 4) if ran else None,
    )
    suite_times = [float(t) for s in root.iter("testsuite") if (t := s.get("time"))]
    wall_s = round(sum(suite_times), 3) if suite_times else None
    return counts, cases, wall_s


def duration_stats(durations: dict[str, Any] | None, wall_s: float | None) -> DurationStats:
    """Map durations.json aggregates onto DurationStats.

    Args:
        durations: Parsed durations.json, or None when it is absent
        wall_s: Wall time from the junit report, carried in here

    Returns:
        The run's timing aggregates, all None when durations is absent
    """
    data = durations or {}
    return DurationStats(
        max_s=data.get("max_duration"),
        median_s=data.get("median_duration"),
        p95_s=data.get("p95_duration"),
        slow_count=data.get("slow_count"),
        retried_count=data.get("retried_count"),
        wall_s=wall_s,
    )


def navigation_stats(navigation: dict[str, Any] | None) -> NavigationStats:
    """Map navigation.json onto NavigationStats.

    Args:
        navigation: Parsed navigation.json, or None when it is absent

    Returns:
        The site's first-navigation latency, all timings None on a failed
        or absent navigation
    """
    nav = (navigation or {}).get("navigation") or {}
    timing = nav.get("timing") or {}
    return NavigationStats(
        error=nav.get("error"),
        ttfb_ms=timing.get("ttfb_ms"),
        dom_content_loaded_ms=timing.get("dom_content_loaded_ms"),
        load_ms=timing.get("load_ms"),
        connect_ms=timing.get("connect_ms"),
    )


def _run_identity(
    durations: dict[str, Any] | None, navigation: dict[str, Any] | None
) -> tuple[str, int | None, str]:
    """Resolve run_id, run_number, and timestamp from whichever artifact has them.

    Both metrics files carry the same identity block (conftest writes it
    from one helper), so either answers; durations is preferred and
    navigation is the fallback for a run that wrote only one. A run that
    wrote neither is stamped now with a local id so it still records.

    Args:
        durations: Parsed durations.json, or None
        navigation: Parsed navigation.json, or None

    Returns:
        The run id, run number (or None), and ISO-8601 UTC timestamp
    """
    for src in (durations, navigation):
        if src and src.get("run_id") and src.get("timestamp"):
            return src["run_id"], src.get("run_number"), src["timestamp"]
    return "local", None, datetime.now(UTC).isoformat(timespec="seconds")


def build_run_record(
    durations: dict[str, Any] | None,
    navigation: dict[str, Any] | None,
    junit_root: ET.Element | None,
    env: Mapping[str, str],
) -> RunRecord:
    """Assemble one RunRecord from a run's parsed artifacts.

    Pure over its inputs (env is passed in, not read from the process) so
    a run's normalization can be pinned in a test without CI or a live
    site. trigger and commit come from the CI environment; everything
    else comes from the artifacts.

    Args:
        durations: Parsed durations.json, or None when absent
        navigation: Parsed navigation.json, or None when absent
        junit_root: Parsed junit root, or None when the report is unusable
        env: Environment mapping, read for GITHUB_EVENT_NAME/GITHUB_SHA

    Returns:
        The normalized record for the run
    """
    if junit_root is not None:
        counts, cases, wall_s = parse_junit(junit_root)
    else:
        counts, cases, wall_s = TestCounts(0, 0, 0, 0, 0, None), [], None
    run_id, run_number, timestamp = _run_identity(durations, navigation)
    return RunRecord(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        run_number=run_number,
        timestamp=timestamp,
        trigger=env.get("GITHUB_EVENT_NAME", "local"),
        browser=(navigation or {}).get("browser"),
        commit_sha=env.get("GITHUB_SHA") or None,
        counts=counts,
        duration=duration_stats(durations, wall_s),
        navigation=navigation_stats(navigation),
        cases=cases,
    )


def partition_path(record: RunRecord) -> Path:
    """Compute the store-relative path a record is written to.

    Partitioned by run date (dt=YYYY-MM-DD) so the store stays scannable
    as it grows, and named by run_id so a re-run of the same workflow
    overwrites its own record instead of appending a duplicate - the
    idempotency the pipeline promises.

    Args:
        record: The record whose partition path to compute

    Returns:
        A relative path like runs/dt=2026-07-20/run-12345.json
    """
    date = record.timestamp[:10] or "unknown"
    return Path("runs") / f"dt={date}" / f"run-{record.run_id}.json"


def write_record(record: RunRecord, store_dir: Path) -> Path:
    """Write a record to its partition under store_dir.

    Args:
        record: The record to serialize
        store_dir: Root of the store the partition path is resolved under

    Returns:
        The absolute path the record was written to
    """
    out_path = store_dir / partition_path(record)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8")
    return out_path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the transform CLI arguments.

    Args:
        argv: Argument list, or None to read from sys.argv

    Returns:
        Parsed arguments with results_dir and store_dir
    """
    parser = argparse.ArgumentParser(description="Normalize a QA run's artifacts into a record.")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path(os.getenv("TEST_RESULTS_DIR", DEFAULT_RESULTS_DIR)),
        help="Directory holding junit.xml, durations.json, navigation.json",
    )
    parser.add_argument(
        "--store-dir",
        type=Path,
        default=Path(DEFAULT_RESULTS_DIR),
        help="Root the partitioned record is written under",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Build a record from test-results/ and write it to the store.

    Prints the written path to stdout so the workflow's load step can
    stage exactly that file.

    Args:
        argv: Argument list, or None to read from sys.argv
    """
    args = _parse_args(argv)
    results_dir: Path = args.results_dir
    try:
        junit_root: ET.Element | None = ET.parse(results_dir / JUNIT_NAME).getroot()
    except (OSError, ET.ParseError):
        junit_root = None
    record = build_run_record(
        durations=load_json(results_dir / DURATIONS_NAME),
        navigation=load_json(results_dir / NAVIGATION_NAME),
        junit_root=junit_root,
        env=os.environ,
    )
    out_path = write_record(record, args.store_dir)
    print(out_path)


if __name__ == "__main__":
    main()
