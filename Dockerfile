# Site Sentry Dockerfile
# Production-ready containerized Playwright + Pytest QA suite

FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Set Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -e .[dev]

# Copy application files
COPY tests/ ./tests/
COPY .env.example .env

# Create test results directory
RUN mkdir -p test-results

# Set default command to run tests
CMD ["pytest", "--html=test-results/report.html", "--self-contained-html"]
