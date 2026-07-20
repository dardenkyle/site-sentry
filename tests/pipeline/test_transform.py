"""Tests for the run-record transform stage.

These pin the normalization offline: no browser, no network, no CI. Each
raw artifact is fed in as the exact dict or XML a real run would write,
so a schema drift in conftest or a mis-mapped field fails here rather
than silently producing a wrong record in production.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from pipeline.schema import SCHEMA_VERSION
from pipeline.transform import (
    build_run_record,
    duration_stats,
    load_json,
    navigation_stats,
    parse_junit,
    partition_path,
    write_record,
)

# A junit report with one of every outcome, mirroring pytest's xunit2
# output: a bare <testcase> passed, and failure/error/skipped children.
JUNIT_MIXED = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="4" failures="1" errors="1" skipped="1" time="12.5">
    <testcase classname="tests.smoke.test_smoke" name="test_homepage_loads" time="1.20"/>
    <testcase classname="tests.smoke.test_smoke" name="test_warm" time="0.50">
      <failure message="boom">assert 1 == 2</failure>
    </testcase>
    <testcase classname="tests.ui.test_ui_nav" name="test_nav" time="0.10">
      <error message="fixture crash">Traceback</error>
    </testcase>
    <testcase classname="tests.smoke.test_smoke" name="test_redirect" time="0.00">
      <skipped message="not https"/>
    </testcase>
  </testsuite>
</testsuites>
"""

DURATIONS = {
    "run_id": "12345",
    "run_number": 42,
    "timestamp": "2026-07-20T22:51:42+00:00",
    "durations": {"tests/smoke/test_smoke.py::test_homepage_loads": 1.2},
    "retried": {},
    "retried_count": 0,
    "max_duration": 1.2,
    "median_duration": 0.5,
    "p95_duration": 1.14,
    "slow_count": 0,
}

NAVIGATION = {
    "run_id": "12345",
    "run_number": 42,
    "timestamp": "2026-07-20T22:51:42+00:00",
    "browser": "chromium",
    "navigation": {
        "error": None,
        "timing": {
            "ttfb_ms": 50,
            "dom_content_loaded_ms": 148.3,
            "load_ms": 357.2,
            "connect_ms": 36,
        },
    },
}


def test_parse_junit_counts_and_outcomes() -> None:
    counts, cases, wall_s = parse_junit(ET.fromstring(JUNIT_MIXED))
    assert (counts.total, counts.passed, counts.failed, counts.errors, counts.skipped) == (
        4,
        1,
        1,
        1,
        1,
    )
    assert wall_s == 12.5
    outcomes = {c.nodeid.split("::")[-1]: c.outcome for c in cases}
    assert outcomes == {
        "test_homepage_loads": "passed",
        "test_warm": "failed",
        "test_nav": "error",
        "test_redirect": "skipped",
    }


def test_pass_rate_excludes_skips_from_denominator() -> None:
    # 1 passed of (1 passed + 1 failed + 1 error) = 3 ran, skip excluded
    counts, _, _ = parse_junit(ET.fromstring(JUNIT_MIXED))
    assert counts.pass_rate == round(1 / 3, 4)


def test_pass_rate_is_none_when_only_skips() -> None:
    only_skips = """<testsuite tests="1" time="0.0">
      <testcase classname="t" name="a" time="0.0"><skipped/></testcase>
    </testsuite>"""
    counts, _, _ = parse_junit(ET.fromstring(only_skips))
    assert counts.pass_rate is None


def test_duration_stats_maps_and_tolerates_absence() -> None:
    stats = duration_stats(DURATIONS, wall_s=12.5)
    assert (stats.max_s, stats.median_s, stats.p95_s, stats.wall_s) == (1.2, 0.5, 1.14, 12.5)
    assert stats.slow_count == 0
    empty = duration_stats(None, wall_s=None)
    assert (empty.max_s, empty.p95_s, empty.retried_count, empty.wall_s) == (None, None, None, None)


def test_navigation_stats_maps_timing() -> None:
    stats = navigation_stats(NAVIGATION)
    assert stats.error is None
    assert (stats.ttfb_ms, stats.dom_content_loaded_ms, stats.load_ms, stats.connect_ms) == (
        50,
        148.3,
        357.2,
        36,
    )


def test_navigation_stats_failed_navigation_has_error_and_null_timing() -> None:
    failed = {"navigation": {"error": "Timeout 20000ms exceeded", "timing": None}}
    stats = navigation_stats(failed)
    assert stats.error == "Timeout 20000ms exceeded"
    assert stats.ttfb_ms is None and stats.load_ms is None


def test_build_run_record_full() -> None:
    env = {"GITHUB_EVENT_NAME": "schedule", "GITHUB_SHA": "abc123"}
    record = build_run_record(DURATIONS, NAVIGATION, ET.fromstring(JUNIT_MIXED), env)
    assert record.schema_version == SCHEMA_VERSION
    assert record.run_id == "12345"
    assert record.run_number == 42
    assert record.trigger == "schedule"
    assert record.commit_sha == "abc123"
    assert record.browser == "chromium"
    assert record.counts.total == 4
    assert record.duration.wall_s == 12.5
    assert record.navigation.ttfb_ms == 50
    assert len(record.cases) == 4


def test_build_run_record_survives_missing_junit() -> None:
    # A run that died before pytest wrote junit still yields a record.
    record = build_run_record(DURATIONS, NAVIGATION, None, {})
    assert record.counts.total == 0
    assert record.counts.pass_rate is None
    assert record.cases == []
    assert record.trigger == "local"
    assert record.commit_sha is None


def test_run_identity_prefers_durations_then_navigation() -> None:
    nav_only = build_run_record(None, NAVIGATION, None, {})
    assert nav_only.run_id == "12345"
    neither = build_run_record(None, None, None, {})
    assert neither.run_id == "local"
    assert neither.run_number is None


def test_partition_path_is_date_partitioned_and_run_keyed() -> None:
    record = build_run_record(DURATIONS, NAVIGATION, None, {})
    assert partition_path(record) == Path("runs/dt=2026-07-20/run-12345.json")


def test_write_record_round_trips(tmp_path: Path) -> None:
    record = build_run_record(DURATIONS, NAVIGATION, ET.fromstring(JUNIT_MIXED), {})
    out_path = write_record(record, tmp_path)
    assert out_path == tmp_path / "runs/dt=2026-07-20/run-12345.json"
    reloaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert reloaded["run_id"] == "12345"
    assert reloaded["counts"]["total"] == 4
    assert reloaded["cases"][0]["outcome"] == "passed"


def test_load_json_tolerates_missing_and_corrupt(tmp_path: Path) -> None:
    assert load_json(tmp_path / "nope.json") is None
    corrupt = tmp_path / "bad.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert load_json(corrupt) is None
    valid = tmp_path / "ok.json"
    valid.write_text('{"a": 1}', encoding="utf-8")
    assert load_json(valid) == {"a": 1}
