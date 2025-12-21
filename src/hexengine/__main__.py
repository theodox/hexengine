import logging
import sys
import time
from math import atan2, ceil, copysign, cos, floor, pi, sin, sqrt
from typing import Iterable, Sequence

import js
from pyodide.ffi import create_proxy

from . import dev_console
from .document import element
from .excepthook import install_exception_hook
from .game import Game
from .game.scenarios.test_scenario import TEST_SCENARIO
from .hexes.math import Hex
from .hexes.shapes import angle, convex_hull, line, path, polygon  # , convex_polygon

__version__ = "0.1.1"


GAME = None
MAP = None


def main():
    loading = element("loading")
    loading.style.display = "none"

    dev_console.initialize("", globals())
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.warning("Hexes demo starting...")
    install_exception_hook(logger)

    logger.debug(f"Hexes version: {__version__}")

    global GAME, MAP, BOARD
    GAME = Game()
    MAP = GAME.canvas
    BOARD = GAME.board

    TEST_SCENARIO.populate(GAME)