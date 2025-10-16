# Contributing to Site Sentry

Thanks for checking out **Site Sentry** — a Playwright + Pytest QA suite.
This guide keeps contributions consistent and the CI green.

---

## Quick Start

```bash
# Python 3.13 recommended
poetry install
poetry run python -m playwright install --with-deps chromium

# “Pre-commit hooks are recommended for consistent formatting and linting. The CI pipeline enforces the same checks.”
poetry add --dev pre-commit
poetry run pre-commit install
poetry run pre-commit run --all-files
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
poetry run ruff check .
poetry run ruff format .
poetry run mypy .
poetry run pytest -v --html=test-results/report.html --self-contained-html
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
HEADLESS=false poetry run pytest -v
```

```bash
# Windows
$env:HEADLESS = "false"; poetry run pytest -v; Remove-Item Env:\HEADLESS
```

---

## Code Style & Editors

- Formatting and linting: **Ruff**
- Types: **mypy**
- Line endings: **LF**
- Indentation: **4 spaces (Python), 2 spaces (YAML/JSON)**

---

Thanks for keeping the project clean and consistent!
