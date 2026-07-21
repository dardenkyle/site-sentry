"""Metrics pipeline for Site Sentry.

Turns the raw artifacts each QA run emits (junit.xml, durations.json,
navigation.json) into one normalized run record, and folds a directory
of those records into the history the trend dashboard reads. This is the
transform and serve half of the extract -> transform -> load -> serve
pipeline described in issue #33; extraction happens in the pytest run
itself, loading is the workflow committing records to the store.

Stdlib only and no pytest/Playwright imports, so the pipeline runs as a
plain script in CI without the test toolchain installed.
"""
