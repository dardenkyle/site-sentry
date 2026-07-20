"""Fold the store of run records into the history the dashboard reads.

The store holds one record per run, partitioned by date. The dashboard
needs a single time-ordered series, not a directory tree, so this stage
reads every record, flattens each to the handful of fields a chart plots
(dropping the per-test case list the trend view never uses), and writes
one history.json.

Records are deduplicated on run_id keeping the latest timestamp, so a
re-run that rewrote its record cannot double-count in the history even if
a stale copy lingers. Stdlib only.
"""

import argparse
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.schema import SCHEMA_VERSION

DEFAULT_STORE_DIR = "test-results"
RUNS_GLOB = "runs/**/*.json"
HISTORY_NAME = "history.json"


def load_records(store_dir: Path) -> list[dict[str, Any]]:
    """Read every run record under a store directory.

    Corrupt or non-object files are skipped rather than aborting the
    aggregation: one unreadable partition should not blank the dashboard.

    Args:
        store_dir: Root the partitioned records live under

    Returns:
        The parsed record objects, in filesystem-glob order
    """
    records: list[dict[str, Any]] = []
    for path in sorted(store_dir.glob(RUNS_GLOB)):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            # A half-written record can be invalid UTF-8, not just invalid
            # JSON; catching UnicodeDecodeError too keeps one truncated
            # partition from aborting the whole aggregation.
            loaded = None
        if isinstance(loaded, dict):
            records.append(loaded)
    return records


def to_series_entry(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten a run record to the fields the dashboard charts.

    The nested record is convenient to write but awkward to plot; this
    projects it to a flat row (pass rate, load timings, timing
    aggregates) and drops the per-test case list, which the trend view
    never reads.

    Args:
        record: One parsed run record

    Returns:
        A flat dict of the chartable fields for one run
    """
    counts = record.get("counts") or {}
    duration = record.get("duration") or {}
    navigation = record.get("navigation") or {}
    return {
        "run_id": record.get("run_id"),
        "run_number": record.get("run_number"),
        "timestamp": record.get("timestamp"),
        "trigger": record.get("trigger"),
        "browser": record.get("browser"),
        "commit_sha": record.get("commit_sha"),
        "total": counts.get("total"),
        "passed": counts.get("passed"),
        "failed": counts.get("failed"),
        "errors": counts.get("errors"),
        "pass_rate": counts.get("pass_rate"),
        "ttfb_ms": navigation.get("ttfb_ms"),
        "dom_content_loaded_ms": navigation.get("dom_content_loaded_ms"),
        "load_ms": navigation.get("load_ms"),
        "nav_error": navigation.get("error"),
        "p95_s": duration.get("p95_s"),
        "max_s": duration.get("max_s"),
        "wall_s": duration.get("wall_s"),
        "slow_count": duration.get("slow_count"),
        "retried_count": duration.get("retried_count"),
    }


def dedupe_by_run(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse entries sharing a run_id, keeping the latest timestamp.

    The store already keys files by run_id, so this defends against a
    stale duplicate rather than routine collisions: whichever copy has
    the newer timestamp wins, matching the idempotency the pipeline
    promises. The result is sorted ascending by timestamp so the series
    reads left-to-right as time.

    Args:
        entries: Flattened run entries in any order

    Returns:
        One entry per run_id, sorted oldest run first
    """
    latest: dict[str, dict[str, Any]] = {}
    for entry in entries:
        run_id = str(entry.get("run_id"))
        prior = latest.get(run_id)
        if prior is None or str(entry.get("timestamp")) >= str(prior.get("timestamp")):
            latest[run_id] = entry
    return sorted(latest.values(), key=lambda e: str(e.get("timestamp")))


def _is_incident(entry: dict[str, Any]) -> bool:
    """Decide whether a run entry counts as an incident.

    An incident is a run that failed to prove the site healthy: a test
    failed or errored, or the site's first navigation itself failed. A
    run of only skips is not an incident (it asserted nothing), which is
    why the test check reads the failure counts, not the pass rate.

    Args:
        entry: A flattened run entry

    Returns:
        True when the run failed a test, errored, or could not navigate
    """
    failed = entry.get("failed") or 0
    errors = entry.get("errors") or 0
    return failed > 0 or errors > 0 or entry.get("nav_error") is not None


def last_incident(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the most recent incident in a time-ascending series.

    Args:
        entries: Run entries sorted oldest first

    Returns:
        The latest entry that is an incident, or None if all were healthy
    """
    incidents = [e for e in entries if _is_incident(e)]
    return incidents[-1] if incidents else None


def build_history(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build the dashboard's history document from raw records.

    Args:
        records: Parsed run records from the store

    Returns:
        A history document: metadata, the deduped time-ordered run
        series, and the last-incident summary
    """
    runs = dedupe_by_run(to_series_entry(r) for r in records)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "run_count": len(runs),
        "runs": runs,
        "last_incident": last_incident(runs),
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the aggregate CLI arguments.

    Args:
        argv: Argument list, or None to read from sys.argv

    Returns:
        Parsed arguments with store_dir and out path
    """
    parser = argparse.ArgumentParser(description="Fold run records into history.json.")
    parser.add_argument(
        "--store-dir",
        type=Path,
        default=Path(DEFAULT_STORE_DIR),
        help="Root the partitioned run records live under",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(DEFAULT_STORE_DIR) / HISTORY_NAME,
        help="Path to write the history document to",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Read the store and write history.json for the dashboard.

    Args:
        argv: Argument list, or None to read from sys.argv
    """
    args = _parse_args(argv)
    history = build_history(load_records(args.store_dir))
    out_path: Path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    print(f"{out_path} ({history['run_count']} runs)")


if __name__ == "__main__":
    main()
