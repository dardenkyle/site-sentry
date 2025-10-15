# site-sentry

[![QA Tests](https://github.com/dardenkyle/site-sentry/actions/workflows/tests.yml/badge.svg)](https://github.com/dardenkyle/site-sentry/actions/workflows/tests.yml)

Automated QA suite for [kyledarden.com](https://kyledarden.com) built with Playwright + Pytest. Runs smoke, navigation, and UI tests in CI to keep the site fast and reliable. Features twice-daily automated checks, HTML reports, and easy local/Docker execution.

## Features

- 🎭 **Playwright-powered**: Modern, reliable browser automation
- 🧪 **Comprehensive tests**: Smoke tests, UI validation, and navigation checks
- 🐳 **Containerized**: Full Docker support for consistent environments
- 🤖 **CI/CD ready**: Automated runs twice daily with GitHub Actions
- 📊 **Rich reporting**: HTML test reports with screenshots on failure
- ⚡ **Fast & efficient**: Optimized for quick feedback
- 📝 **Fully typed**: Type hints throughout for better IDE support

## Quick Start

### Prerequisites

- Python 3.13+
- pip

### Local Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/dardenkyle/site-sentry.git
   cd site-sentry
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .[dev]
   playwright install chromium
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env if needed to customize settings
   ```

5. **Run tests**
   ```bash
   pytest
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
├── conftest.py           # Pytest configuration and fixtures
├── test_smoke.py         # Critical smoke tests
├── test_ui_nav.py        # UI and navigation tests
└── utils/
    └── logger.py         # Logging utilities
```

### Test Categories

- **Smoke tests** (`@pytest.mark.smoke`): Fast, critical tests verifying core functionality
- **UI tests** (`@pytest.mark.ui`): User interface and navigation validation
- **Slow tests** (`@pytest.mark.slow`): Longer-running comprehensive tests

### Running Specific Tests

```bash
# Run only smoke tests
pytest -m smoke

# Run only UI tests
pytest -m ui

# Run specific test file
pytest tests/test_smoke.py

# Run with verbose output
pytest -v

# Run with HTML report
pytest --html=test-results/report.html --self-contained-html
```

## Configuration

Configuration is managed via environment variables. Copy `.env.example` to `.env` and customize:

```bash
# Target website
BASE_URL=https://kyledarden.com

# Browser settings
HEADLESS=true
BROWSER=chromium
VIEWPORT_WIDTH=1280
VIEWPORT_HEIGHT=720

# Test settings
TIMEOUT=30000
LOG_LEVEL=INFO
```

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
mypy tests/

# Linting
ruff check tests/

# Format checking
ruff format --check tests/
```

### Adding New Tests

1. Create test file in `tests/` directory (must start with `test_`)
2. Add appropriate markers (`@pytest.mark.smoke`, `@pytest.mark.ui`, etc.)
3. Use fixtures from `conftest.py` (page, context, base_url)
4. Add type hints and docstrings
5. Run tests locally before committing

## Project Structure

```
site-sentry/
├── .github/
│   └── workflows/
│       └── tests.yml        # CI/CD workflow
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest configuration
│   ├── test_smoke.py        # Smoke tests
│   ├── test_ui_nav.py       # UI/navigation tests
│   └── utils/
│       ├── __init__.py
│       └── logger.py        # Logging utility
├── .env.example             # Environment template
├── .gitignore               # Git ignore rules
├── Dockerfile               # Container definition
├── LICENSE                  # MIT License
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Kyle Darden - [kyledarden.com](https://kyledarden.com)