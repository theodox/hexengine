"""
Manager for running a local game server.

Handles starting/stopping a local server for single-player games.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from ..server.game_server import GameServer
from ..state import GameState


class LocalServerManager:
    """
    Manages a local game server running in the same process.

    For single-player mode, this starts a local server that the client
    connects to via WebSocket on localhost. From the client's perspective,
    this is identical to connecting to a remote server.
    """

    def __init__(
        self,
        initial_state: GameState | None = None,
        map_display: dict[str, Any] | None = None,
        global_styles: dict[str, Any] | None = None,
        unit_graphics: dict[str, Any] | None = None,
    ):
        """
        Initialize the local server manager.

        Args:
            initial_state: Initial game state for the server
            map_display: Scenario map presentation dict for StateUpdate (optional)
            global_styles: Global CSS dict for StateUpdate (optional)
            unit_graphics: Unit graphics templates for StateUpdate (optional)
        """
        self.initial_state = initial_state
        self.map_display = map_display
        self.global_styles = global_styles
        self.unit_graphics = unit_graphics
        self.server: GameServer | None = None
        self.server_thread: threading.Thread | None = None
        self.logger = logging.getLogger("local_server")
        self._running = False

    def start(self, port: int = 8765) -> bool:
        """
        Start the local server in a background thread.

        Args:
            port: Port to run the server on

        Returns:
            True if started successfully
        """
        if self._running:
            self.logger.warning("Server already running")
            return False

        try:
            from ..server.websocket_server import WebSocketGameServer

            # Create server
            server = WebSocketGameServer(
                host="127.0.0.1",
                port=port,
                initial_state=self.initial_state,
                map_display=self.map_display,
                global_styles=self.global_styles,
                unit_graphics=self.unit_graphics,
            )

            # Start in background thread
            self.server_thread = threading.Thread(
                target=self._run_server,
                args=(server,),
                daemon=True,
            )
            self.server_thread.start()

            self._running = True
            self.logger.info(f"Local server started on port {port}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start local server: {e}")
            return False

    def _run_server(self, server) -> None:
        """
        Run the server in an asyncio event loop.

        Args:
            server: WebSocketGameServer instance
        """
        asyncio.run(server.start())

    def stop(self) -> None:
        """Stop the local server."""
        if not self._running:
            return

        self._running = False
        # The server daemon will stop when the thread is terminated
        self.logger.info("Local server stopped")

    def is_running(self) -> bool:
        """Check if the server is currently running."""
        return self._running
