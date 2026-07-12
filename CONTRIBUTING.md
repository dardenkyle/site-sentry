# Contributing to Site Sentry

Thanks for checking out **Site Sentry** — a Playwright + Pytest QA suite.
This guide keeps contributions consistent and the CI green.

---

## Quick Start

```bash
# Python 3.12.13 (pinned in .python-version; uv provisions it automatically)
uv sync
uv run playwright install --with-deps chromium

# “Pre-commit hooks are recommended for consistent formatting and linting. The CI pipeline enforces the same checks.”
uv add --dev pre-commit
uv run pre-commit install
uv run pre-commit run --all-files
```

If you have a Makefile:

```bash
make lint     # Ruff lint
make fmt      # Ruff format
make type     # mypy type check
make test     # pytest (HTML/JUnit reports)
```

Without Makefile:

```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run pytest -v --html=test-results/report.html --self-contained-html
```

---

## Branch Naming

Use the issue number + short slug:

```
<issue#>-<type>-<slug>
```

Examples:

```
7-chore-add-editorconfig-and-contributingmd
15-ci-unify-ci-and-qa-workflows
```

---

## Commit Style

Follow Conventional Commits:

```
<type>(optional-scope): <summary>
```

Examples:

```
dx: add pre-commit hooks for ruff and mypy
ci: generate junit and html reports
test: embed screenshots and traces in pytest-html
docs: rewrite README
```

Link issues in commits/PRs:

```
Closes #21
```

---

## Pull Requests

### Checklist

- [ ] Branch named with issue number/slug
- [ ] `ruff format` and `ruff check` pass
- [ ] `mypy` passes
- [ ] `pytest` passes locally
- [ ] Docs updated if behavior changed

### PR Expectations

- Keep diffs small and focused
- Add tests for new behavior
- Include a short rationale in the PR body
- Reference the issue (`Closes #<n>`)

---

## Testing Notes

Artifacts:

- HTML report: `test-results/report.html`
- JUnit XML: `test-results/junit.xml`
- Screenshots: `test-results/screenshots/`
- Playwright traces: `test-results/playwright-traces/`

Run locally:

```bash
# Linux/macOS
HEADLESS=false uv run pytest -v
```

```bash
# Windows
$env:HEADLESS = "false"; uv run pytest -v; Remove-Item Env:\HEADLESS
```

---

## Code Style & Editors

- Formatting and linting: **Ruff**
- Types: **mypy**
- Line endings: **LF**
- Indentation: **4 spaces (Python), 2 spaces (YAML/JSON)**

---

Thanks for keeping the project clean and consistent!
