import logging
from urllib.parse import urlparse, parse_qs

from . import dev_console
from .document import element, js
from .excepthook import install_exception_hook
from .game import NetworkGame
from .game.scenarios.test_scenario import TEST_SCENARIO

__version__ = "0.1.1"


GAME = None
MAP = None


def parse_url_params():
    """Parse URL parameters to determine game mode."""
    # Get URL from browser
    url = js.window.location.href
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    # Helper to get first value from query param
    def get_param(key, default=None):
        values = params.get(key, [])
        return values[0] if values else default

    mode = get_param("mode", "single")  # "single" or "multi"
    player_name = get_param("name", "Player")
    faction = get_param("faction")  # None for auto-assign
    server_url = get_param("server", "ws://localhost:8765")

    return {
        "mode": mode,
        "player_name": player_name,
        "faction": faction,
        "server_url": server_url,
        "use_local_server": mode == "single",
    }


def async_main() -> None:
    loading = element("loading")
    loading.style.display = "none"

    dev_console.initialize("", globals())
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.warning("Hexes demo starting...")
    install_exception_hook(logger)

    logger.debug(f"Hexes version: {__version__}")

    try:
        # Parse URL parameters
        config = parse_url_params()
        logger.info(f"Config: {config}")
        logger.info(f"Starting in {config['mode']} mode as {config['player_name']}")

        global GAME, MAP, BOARD

        # Create network-enabled game
        logger.info("Creating NetworkGame...")
        GAME = NetworkGame(
            server_url=config["server_url"],
            player_name=config["player_name"],
            preferred_faction=config["faction"],
            use_local_server=config["use_local_server"],
        )

        MAP = GAME.canvas
        BOARD = GAME.board

        # Connect to server (asynchronous via callbacks)
        logger.info("Calling GAME.connect()...")
        GAME.connect()
        logger.info("GAME.connect() returned")

        # Don't populate scenario on client - units come from server state
        # The server initializes with the scenario units
        # TEST_SCENARIO.populate(GAME)  # <-- Removed

        logger.info("Initialization complete!")

    except Exception as e:
        logger.error(f"Error during initialization: {e}", exc_info=True)


def main() -> None:
    """Entry point."""
    logger = logging.getLogger()
    logger.debug("main() called")
    try:
        async_main()
    except Exception as e:
        logging.exception("FATAL ERROR in main()")
