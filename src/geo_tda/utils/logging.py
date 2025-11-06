"""
Colored logging setup for notebook and script environments.
"""

import logging
import sys


class ColoredFormatter(logging.Formatter):
    """A custom formatter to wrap log messages in ANSI colors."""

    GREY = "\x1b[37m"  # White
    YELLOW = "\x1b[33m"
    RED = "\x1b[31m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    COLOR_MAP = {
        logging.DEBUG: GREY,
        logging.INFO: GREY,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED
    }

    def format(self, record):
        """Applies color to the entire formatted log message."""
        color = self.COLOR_MAP.get(record.levelno)
        formatted_message = super().format(record)
        return f"{color}{formatted_message}{self.RESET}"


def setup_colored_logging(level=logging.INFO):
    """
    Forcefully configures the root logger to output colored logs to stdout.

    This function uses logging.basicConfig(force=True) to ensure that it
    overrides any pre-existing logging configurations, which is a common
    issue in interactive environments like Jupyter notebooks.
    """
    FMT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DATEFMT = "%Y-%m-%d %H:%M:%S"

    # Forcefully reconfigure the root logger
    logging.basicConfig(
        level=level,
        format=FMT,
        datefmt=DATEFMT,
        force=True,
        stream=sys.stdout
    )

    # Replace the formatter on the handler that basicConfig just created
    for handler in logging.getLogger().handlers:
        handler.setFormatter(ColoredFormatter(fmt=FMT, datefmt=DATEFMT))
