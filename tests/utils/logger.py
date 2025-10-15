"""Logging utility for Site Sentry tests.

This module provides a configured logger for the test suite with
structured output and appropriate log levels.
"""

import logging
import os
import sys


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Name of the logger (typically __name__)
        level: Optional log level override (defaults to env LOG_LEVEL or INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        log_level_str: str = level if level is not None else os.getenv("LOG_LEVEL", "INFO")
        logger.setLevel(getattr(logging, log_level_str.upper(), logging.INFO))

        # Create console handler with formatting
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logger.level)

        # Create formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger


# Module-level logger for convenience
logger = get_logger(__name__)
