"""
Manager for running a local game server.

Handles starting/stopping a local server for single-player games.
"""

import asyncio
import logging
import threading
from typing import Optional

from ..state import GameState
from ..server.game_server import GameServer


class LocalServerManager:
    """
    Manages a local game server running in the same process.
    
    For single-player mode, this starts a local server that the client
    connects to via WebSocket on localhost. From the client's perspective,
    this is identical to connecting to a remote server.
    """
    
    def __init__(self, initial_state: Optional[GameState] = None):
        """
        Initialize the local server manager.
        
        Args:
            initial_state: Initial game state for the server
        """
        self.initial_state = initial_state
        self.server: Optional[GameServer] = None
        self.server_thread: Optional[threading.Thread] = None
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
