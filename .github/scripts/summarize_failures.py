"""Summarize pytest junit.xml results for the incident-alert job.

Reads the junit report the scheduled QA run writes and prints GitHub
Actions output lines (append stdout to $GITHUB_OUTPUT):

    has_results=true|false   whether a junit report was found and parsed
    failed_count=N           tests that failed or errored
    smoke_failed=true|false  whether any failure was a smoke test
    failed_tests<<EOF        one failing test node id per line
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


def to_node_id(classname: str, name: str) -> str:
    """Reconstruct a pytest node id from junit classname and test name.

    pytest's default xunit2 junit output carries no file attribute, so
    the module path is rebuilt from the dotted classname (e.g.
    tests.smoke.test_smoke -> tests/smoke/test_smoke.py). When the
    rebuilt file does not exist (class-based tests, or running outside
    the repo root), falls back to the raw classname::name form.

    Args:
        classname: Dotted module path from the junit testcase
        name: Test name from the junit testcase, including parameters

    Returns:
        A runnable pytest node id, or classname::name as best effort
    """
    module_path = Path(classname.replace(".", "/") + ".py")
    if classname and module_path.exists():
        node_id = f"{module_path}::{name}"
    else:
        node_id = f"{classname}::{name}"
    return node_id


def collect_failures(junit_path: Path) -> tuple[list[str], bool] | None:
    """Extract failing test ids and smoke involvement from a junit report.

    A test counts as failing when its testcase carries a <failure> or
    <error> child (errors cover collection/fixture crashes, which are
    just as actionable as assertion failures).

    Args:
        junit_path: Path to the junit.xml report

    Returns:
        (failing test node ids, any smoke test failed), or None when the
        report is missing, unreadable, or malformed - all of which mean
        the run died before pytest could write it completely
    """
    try:
        root: ET.Element | None = ET.parse(junit_path).getroot()
    except (OSError, ET.ParseError):
        root = None
    result: tuple[list[str], bool] | None = None
    if root is not None:
        failing: list[str] = []
        smoke_failed = False
        for case in root.iter("testcase"):
            broken = case.find("failure") is not None or case.find("error") is not None
            if broken:
                classname = case.get("classname") or ""
                name = case.get("name") or ""
                failing.append(to_node_id(classname, name))
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
