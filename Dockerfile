# Site Sentry Dockerfile
# Containerized Playwright + Pytest QA suite, pinned to Python 3.12.13.
#
# Build:  docker build -t site-sentry .
# Run:    docker run --rm site-sentry
# Config: docker run --rm -e BASE_URL=https://kyledarden.com site-sentry

FROM python:3.12.13-slim

# uv binary pinned for reproducible builds; bump deliberately.
COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /uvx /usr/local/bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    # The image's interpreter is exactly 3.12.13; never download another.
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependency layer: only pyproject.toml/uv.lock invalidate it.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked

# Browser layer: version always matches the locked playwright package.
RUN uv run playwright install --with-deps chromium

COPY tests/ ./tests/

# Report output directory; mount it to keep reports on the host:
#   docker run --rm -v $(pwd)/test-results:/app/test-results site-sentry
RUN mkdir -p test-results

# Configuration comes from -e flags at run time (see README), never a
# baked-in .env.
CMD ["uv", "run", "--locked", "pytest"]
