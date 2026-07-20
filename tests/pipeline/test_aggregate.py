"""Tests for the history-aggregation stage.

These pin the fold from a directory of run records to the single
time-ordered series the dashboard reads: field flattening, dedupe on
run_id, ordering, and the incident summary.
"""

import json
from pathlib import Path
from typing import Any

from pipeline.aggregate import (
    build_history,
    dedupe_by_run,
    last_incident,
    load_records,
    to_series_entry,
)


def _record(run_id: str, timestamp: str, **over: Any) -> dict[str, Any]:
    """Build a minimal run record dict, overridable per field group."""
    record: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "run_number": None,
        "timestamp": timestamp,
        "trigger": "schedule",
        "browser": "chromium",
        "commit_sha": None,
        "counts": {"total": 7, "passed": 7, "failed": 0, "errors": 0, "pass_rate": 1.0},
        "duration": {
            "p95_s": 0.4,
            "max_s": 0.5,
            "wall_s": 3.0,
            "slow_count": 0,
            "retried_count": 0,
        },
        "navigation": {"error": None, "ttfb_ms": 50, "dom_content_loaded_ms": 120, "load_ms": 300},
        "cases": [{"nodeid": "t::a", "outcome": "passed", "duration_s": 1.1}],
    }
    record.update(over)
    return record


def test_to_series_entry_flattens_and_drops_cases() -> None:
    entry = to_series_entry(_record("1", "2026-07-20T06:00:00+00:00"))
    assert entry["pass_rate"] == 1.0
    assert entry["dom_content_loaded_ms"] == 120
    assert entry["wall_s"] == 3.0
    assert "cases" not in entry


def test_dedupe_keeps_latest_timestamp_and_sorts_ascending() -> None:
    older = to_series_entry(_record("1", "2026-07-20T06:00:00+00:00", trigger="old"))
    newer = to_series_entry(_record("1", "2026-07-20T18:00:00+00:00", trigger="new"))
    other = to_series_entry(_record("2", "2026-07-21T06:00:00+00:00"))
    deduped = dedupe_by_run([newer, other, older])
    assert [e["run_id"] for e in deduped] == ["1", "2"]
    # The rerun (newer timestamp) wins for the collapsed run_id.
    assert deduped[0]["trigger"] == "new"


def test_last_incident_picks_most_recent_failure() -> None:
    healthy = to_series_entry(_record("1", "2026-07-20T06:00:00+00:00"))
    failed = to_series_entry(
        _record(
            "2",
            "2026-07-20T18:00:00+00:00",
            counts={"total": 7, "passed": 6, "failed": 1, "errors": 0, "pass_rate": 0.8571},
        )
    )
    later_healthy = to_series_entry(_record("3", "2026-07-21T06:00:00+00:00"))
    incident = last_incident([healthy, failed, later_healthy])
    assert incident is not None
    assert incident["run_id"] == "2"


def test_navigation_failure_is_an_incident() -> None:
    nav_down = to_series_entry(
        _record(
            "1",
            "2026-07-20T06:00:00+00:00",
            navigation={"error": "Timeout 20000ms", "ttfb_ms": None, "dom_content_loaded_ms": None},
        )
    )
    assert last_incident([nav_down]) is not None


def test_skip_only_run_is_not_an_incident() -> None:
    # No failures and no nav error: a run that asserted nothing is not down.
    skips = to_series_entry(
        _record(
            "1",
            "2026-07-20T06:00:00+00:00",
            counts={"total": 1, "passed": 0, "failed": 0, "errors": 0, "pass_rate": None},
        )
    )
    assert last_incident([skips]) is None


def test_all_healthy_has_no_incident() -> None:
    entries = [to_series_entry(_record(str(i), f"2026-07-2{i}T06:00:00+00:00")) for i in range(3)]
    assert last_incident(entries) is None


def test_build_history_shape() -> None:
    history = build_history([_record("1", "2026-07-20T06:00:00+00:00")])
    assert history["run_count"] == 1
    assert history["schema_version"] == 1
    assert "generated_at" in history
    assert history["runs"][0]["run_id"] == "1"
    assert history["last_incident"] is None


def test_load_records_reads_partitions_and_skips_corrupt(tmp_path: Path) -> None:
    good_dir = tmp_path / "runs" / "dt=2026-07-20"
    good_dir.mkdir(parents=True)
    (good_dir / "run-1.json").write_text(json.dumps(_record("1", "2026-07-20T06:00:00+00:00")))
    (good_dir / "run-bad.json").write_text("{broken", encoding="utf-8")
    records = load_records(tmp_path)
    assert len(records) == 1
    assert records[0]["run_id"] == "1"
