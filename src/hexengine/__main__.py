import time
from typing import Sequence, Iterable
from math import atan2, copysign, cos, sin, pi, sqrt, ceil, floor
from pyodide.ffi import create_proxy
import js
import logging
import sys

from . import dev_console
from .document import element
from .hexes.math import Hex
from .hexes.shapes import  angle, convex_hull, path, polygon, line#, convex_polygon
from .excepthook import install_exception_hook
from .game import Game
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

    global GAME, MAP
    GAME = Game()

    MAP = hex_canvas = GAME.canvas
