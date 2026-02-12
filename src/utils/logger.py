"""
Logging configuration and utilities.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup a logger with consistent formatting.

    Args:
        name: Logger name (usually __name__)
        level: Logging level

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # File handler
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        logs_dir / f"bot_{datetime.now():%Y%m%d}.log"
    )
    file_handler.setLevel(level)

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
