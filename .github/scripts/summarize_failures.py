"""Summarize pytest junit.xml results for the incident-alert job.

Reads the junit report the scheduled QA run writes and prints GitHub
Actions output lines (append stdout to $GITHUB_OUTPUT):

    has_results=true|false   whether a junit report was found
    failed_count=N           tests that failed or errored
    smoke_failed=true|false  whether any failure was a smoke test
    failed_tests<<EOF        one failing node id per line
    ...
    EOF

The alert job uses smoke_failed to decide between a "Site down" and a
"QA run failed" incident title, and failed_tests to make the incident
issue self-describing without opening artifacts. Stdlib only.
"""

import os
import xml.etree.ElementTree as ET
from pathlib import Path

JUNIT_PATH_ENV = "JUNIT_PATH"
DEFAULT_JUNIT_PATH = "test-results/junit.xml"

# pytest junit classnames are dotted module paths, e.g. tests.smoke.test_smoke
SMOKE_CLASSNAME_PREFIX = "tests.smoke."

OUTPUT_DELIMITER = "GHA_FAILED_TESTS_EOF"


def collect_failures(junit_path: Path) -> tuple[list[str], bool] | None:
    """Extract failing test ids and smoke involvement from a junit report.

    A test counts as failing when its testcase carries a <failure> or
    <error> child (errors cover collection/fixture crashes, which are
    just as actionable as assertion failures).

    Args:
        junit_path: Path to the junit.xml report

    Returns:
        (failing test ids, any smoke test failed), or None when the
        report does not exist (the run died before pytest could write it)
    """
    result: tuple[list[str], bool] | None = None
    if junit_path.exists():
        root = ET.parse(junit_path).getroot()
        failing: list[str] = []
        smoke_failed = False
        for case in root.iter("testcase"):
            broken = case.find("failure") is not None or case.find("error") is not None
            if broken:
                classname = case.get("classname") or ""
                name = case.get("name") or ""
                failing.append(f"{classname}::{name}")
                smoke_failed = smoke_failed or classname.startswith(SMOKE_CLASSNAME_PREFIX)
        result = (failing, smoke_failed)
    return result


def main() -> None:
    """Print the failure summary as GitHub Actions output lines.

    The output format is defined in the module docstring. The junit
    report location can be overridden via the JUNIT_PATH env var.
    """
    junit_path = Path(os.getenv(JUNIT_PATH_ENV, DEFAULT_JUNIT_PATH))
    summary = collect_failures(junit_path)
    failing, smoke_failed = summary if summary is not None else ([], False)
    print(f"has_results={'true' if summary is not None else 'false'}")
    print(f"failed_count={len(failing)}")
    print(f"smoke_failed={'true' if smoke_failed else 'false'}")
    print(f"failed_tests<<{OUTPUT_DELIMITER}")
    for node_id in failing:
        print(node_id)
    print(OUTPUT_DELIMITER)


if __name__ == "__main__":
    main()
