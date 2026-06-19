import logging
import os
from typing import Optional

_LOGGER_NAME = "schedulabackend-api"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return an app logger configured with a helpful formatter.

    Uses environment variable `LOG_LEVEL` if present (default INFO).
    """
    logger_name = name or _LOGGER_NAME
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return logger

    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | %(levelname)s | route=%(route)s | "
            "client=%(client)s | %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
