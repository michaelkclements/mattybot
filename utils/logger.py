"""
Logging utility for MattyBot.

Provides a pre-configured logger with both console and rotating file output.
Import ``logger`` directly from this module wherever logging is needed.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = "logs"
_LOG_FILE = os.path.join(_LOG_DIR, "bot.log")
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
_BACKUP_COUNT = 3
_FMT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "mattybot") -> logging.Logger:
    """
    Create and configure a named logger.

    Attaches a StreamHandler (stdout) and a RotatingFileHandler.
    Calling this function more than once with the same *name* is safe —
    handlers are only attached once.
    """
    log = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls (e.g. during hot-reload)
    if log.handlers:
        return log

    log.setLevel(logging.INFO)

    formatter = logging.Formatter(fmt=_FMT, datefmt=_DATE_FMT)

    # ── Console handler ──────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # ── Rotating file handler ────────────────────────────────────────────────
    os.makedirs(_LOG_DIR, exist_ok=True)
    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    log.addHandler(console_handler)
    log.addHandler(file_handler)

    return log


# Module-level logger — import this directly elsewhere:
#   from utils.logger import logger
logger: logging.Logger = setup_logger()
