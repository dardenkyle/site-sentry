# site-sentry

[![QA Tests](https://github.com/dardenkyle/site-sentry/actions/workflows/tests.yml/badge.svg)](https://github.com/dardenkyle/site-sentry/actions/workflows/tests.yml)
[![Last Commit](https://img.shields.io/github/last-commit/dardenkyle/site-sentry?label=last%20commit&color=brightgreen)](https://github.com/dardenkyle/site-sentry/commits/main)

Automated QA suite for [kyledarden.com](https://kyledarden.com) built with Playwright + Pytest. Runs smoke, navigation, and UI tests in CI to keep the site fast and reliable. Features twice-daily automated checks, HTML reports, and easy local/Docker execution.

## Features

- **Playwright-powered**: Modern, reliable browser automation
- **Comprehensive tests**: Smoke tests, UI validation, and navigation checks
- **Containerized**: Full Docker support for consistent environments
- **CI/CD ready**: Automated runs twice daily with GitHub Actions
- **Rich reporting**: HTML test reports auto-generate with screenshots on failure
- **Fast & efficient**: Optimized for quick feedback (~2m 30s in CI)
- **uv-managed**: Fast, modern Python dependency management with a committed lockfile
- **Fully typed**: Type hints throughout for better IDE support

## Quick Start

### Prerequisites

- Python 3.12.13 (pinned in `.python-version`; uv provisions it automatically)
- [uv](https://docs.astral.sh/uv/) (for dependency management)

### Local Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/dardenkyle/site-sentry.git
   cd site-sentry
   ```

2. **Install uv** (if not already installed)

   ```bash
   # Windows (PowerShell)
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies**

   ```bash
   uv sync
   uv run playwright install chromium
   ```

4. **Configure environment** (optional)

   ```bash
   cp .env.example .env
   # Edit .env if needed to customize settings
   ```

5. **Run tests**
   ```bash
   uv run pytest -v
   ```

### Docker Run

Run tests in a containerized environment:

```bash
# Build the image
docker build -t site-sentry .

# Run tests
docker run --rm site-sentry

# Run with custom environment
docker run --rm -e BASE_URL=https://kyledarden.com site-sentry

# Extract test results
docker run --rm -v $(pwd)/test-results:/app/test-results site-sentry
```

## Test Structure

```
tests/
├── conftest.py               # Pytest configuration and fixtures
├── smoke/
│   ├── test_config.py        # Configuration and environment checks
│   └── test_smoke.py         # Critical smoke tests
├── ui/
│   ├── test_contact_form.py  # Contact form tests
│   └── test_ui_nav.py        # UI and navigation tests
└── utils/
    └── logger.py             # Logging utilities
```

### Test Categories

- **Smoke tests** (`@pytest.mark.smoke`): Fast, critical tests verifying core functionality
- **UI tests** (`@pytest.mark.ui`): User interface and navigation validation
- **Slow tests** (`@pytest.mark.slow`): Longer-running comprehensive tests

### Running Specific Tests

```bash
# Run only smoke tests
uv run pytest -m smoke

# Run only UI tests
uv run pytest -m ui

# Run specific test file
uv run pytest tests/smoke/test_smoke.py

# Run with verbose output
uv run pytest -v

# HTML reports auto-generate at test-results/report.html
```

## Configuration

Configuration is managed via environment variables. Copy `.env.example` to `.env` and customize:

```bash
# Target website
BASE_URL=https://kyledarden.com

# Browser settings
HEADLESS=true
SLOWMO=0
BROWSER=chromium          # chromium, firefox, or webkit; --browser wins
VIEWPORT_WIDTH=1280
VIEWPORT_HEIGHT=720

# Output
TEST_RESULTS_DIR=test-results
SCREENSHOTS_DIR=test-results/screenshots
LOG_LEVEL=INFO
```

Navigation timeouts are deliberate constants in `tests/utils/timing.py`,
not an environment setting: an unchosen timeout value had previously
become the suite's de-facto performance gate, so the ceilings now live
in code where they read as a decision (see issues #57-61).

## CI/CD

Tests run automatically via GitHub Actions:

- **On push/PR**: Every commit to main and pull requests
- **Scheduled**: Twice daily at 6 AM and 6 PM UTC
- **Manual**: Via workflow_dispatch

Test results and HTML reports are uploaded as artifacts and retained for 30 days.

## Development

### Code Quality

```bash
# Type checking
uv run mypy tests/

# Linting
uv run ruff check tests/

# Format checking
uv run ruff format --check tests/
```

### Adding New Tests

1. Create the test file in the matching category directory (`tests/smoke/`, `tests/ui/`); the filename must start with `test_`
2. Add appropriate markers (`@pytest.mark.smoke`, `@pytest.mark.ui`, etc.)
3. Use fixtures from `conftest.py` (page, context, base_url)
4. Add type hints and docstrings
5. Run tests locally before committing

## Project Structure

```
site-sentry/
├── .github/
│   └── workflows/
│       ├── ci.yml               # Lint/type-check workflow
│       └── tests.yml            # QA test workflow (push, PR, schedule)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest configuration
│   ├── smoke/                   # Smoke tests
│   ├── ui/                      # UI/navigation tests
│   └── utils/
│       ├── __init__.py
│       └── logger.py            # Logging utility
├── .dockerignore                # Docker build exclusions
├── .editorconfig                # Editor formatting rules
├── .env.example                 # Environment template
├── .gitignore                   # Git ignore rules
├── .python-version              # Pinned Python version (uv)
├── CONTRIBUTING.md              # Contribution guidelines
├── Dockerfile                   # Container definition
├── LICENSE                      # MIT License
├── pyproject.toml               # Project configuration
├── uv.lock                      # Locked dependency versions
└── README.md                    # This file
```

## Contributing & Standards

This project follows consistent formatting and contribution standards:

- Code style and indentation enforced via [`.editorconfig`](.editorconfig)
- Linting, formatting, and type checks handled by **Ruff** and **mypy**, enforced in CI
- Pre-commit hooks are planned (#9); until then, run the checks below before committing
- See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit style, and PR guidelines

**Quick reference:**

```bash
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run pytest -v
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Kyle Darden - [kyledarden.com](https://kyledarden.com)
