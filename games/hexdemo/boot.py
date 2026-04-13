"""One-shot console banner when the hexdemo pack has finished authoritative load."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def print_loaded_banner() -> None:
    logger.info("welcome to hexdemo")
