"""
WebSocket server implementation for real-time multiplayer.

Provides a WebSocket transport layer on top of GameServer.
Clients connect via WebSocket and send/receive JSON messages.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

from ..gamedef.protocol import GameDefinition
from ..state import GameState
from .game_server import GameServer
from .protocol import Message, ServerError


class WebSocketGameServer:
    """
    WebSocket wrapper around GameServer.

    Manages WebSocket connections and routes messages to/from GameServer.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        initial_state: GameState | None = None,
        map_display: dict[str, Any] | None = None,
        global_styles: dict[str, Any] | None = None,
        unit_graphics: dict[str, Any] | None = None,
        marker_graphics: dict[str, Any] | None = None,
        markers: list[dict[str, Any]] | None = None,
        marker_placement_rule=None,
        *,
        game_definition: GameDefinition,
    ) -> None:
        """
        Initialize WebSocket server.

        Args:
            host: Host to bind to
            port: Port to listen on
            initial_state: Initial game state
            map_display: Optional scenario map presentation (JSON-safe dict)
            global_styles: Optional global CSS dict (JSON-safe)
            unit_graphics: Optional unit type -> template dict (JSON-safe)
        """
        self.host = host
        self.port = port
        self.game_server = GameServer(
            initial_state,
            map_display=map_display,
            global_styles=global_styles,
            unit_graphics=unit_graphics,
            marker_graphics=marker_graphics,
            markers=markers,
            marker_placement_rule=marker_placement_rule,
            game_definition=game_definition,
        )

        # Map connection to player_id
        self.connections: dict[WebSocketServerProtocol, str] = {}
        self.player_connections: dict[str, WebSocketServerProtocol] = {}

        self.logger = logging.getLogger("websocket_server")

        # Register message handler with game server
        self.game_server.add_message_handler(self._send_to_player)

    async def start(self) -> None:
        """Start the WebSocket server."""
        self.logger.info(f"Starting WebSocket server on {self.host}:{self.port}")

        async with websockets.serve(self._handle_connection, self.host, self.port):
            self.logger.info("WebSocket server started")
            await asyncio.Future()  # Run forever

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handle a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
        """
        player_id = self._generate_player_id()
        self.connections[websocket] = player_id
        self.player_connections[player_id] = websocket

        self.logger.info(
            f"New connection from {websocket.remote_address}, assigned ID: {player_id}"
        )

        try:
            async for raw_message in websocket:
                try:
                    # Parse message
                    message = Message.from_json(raw_message)

                    # Route to game server
                    await self.game_server.handle_message(player_id, message)

                except json.JSONDecodeError as e:
                    self.logger.error(f"Invalid JSON from {player_id}: {e}")
                    await self._send_error(websocket, "Invalid message format")
                except Exception as e:
                    self.logger.error(f"Error processing message from {player_id}: {e}")
                    await self._send_error(websocket, str(e))

        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Connection closed for {player_id}")
        finally:
            # Cleanup
            await self.game_server._handle_leave_game(player_id)
            del self.connections[websocket]
            del self.player_connections[player_id]

    def _send_to_player(self, player_id: str, message: Message) -> None:
        """
        Send a message to a specific player.

        This is called by GameServer when it wants to send messages.

        Args:
            player_id: Target player ID
            message: Message to send
        """
        websocket = self.player_connections.get(player_id)
        if websocket:
            # Schedule the send (non-blocking)
            asyncio.create_task(self._send_message(websocket, message))

    async def _send_message(
        self, websocket: WebSocketServerProtocol, message: Message
    ) -> None:
        """
        Actually send a message over WebSocket.

        Args:
            websocket: Target WebSocket connection
            message: Message to send
        """
        try:
            await websocket.send(message.to_json())
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")

    async def _send_error(self, websocket: WebSocketServerProtocol, error: str) -> None:
        """
        Send an error message to a WebSocket.

        Args:
            websocket: Target connection
            error: Error message
        """
        await self._send_message(websocket, ServerError(error=error).to_message())

    def _generate_player_id(self) -> str:
        """Generate a unique player ID."""
        import uuid

        return str(uuid.uuid4())


def build_websocket_arg_parser() -> argparse.ArgumentParser:
    from ..gameroot import add_game_launch_arguments

    p = argparse.ArgumentParser(description="Hexes WebSocket game server")
    add_game_launch_arguments(p)
    return p


async def main(
    *,
    scenario_file: Path | str | None = None,
    game_root: Path | str | None = None,
    scenario_id: str | None = None,
    schedule: str = "interleaved",
):
    """Run a standalone WebSocket game server."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    from ..gameroot import (
        initial_turn_slot_for_game_definition,
        load_game_definition_for_scenario,
        resolve_scenario_path_with_game_root,
        try_hexdemo_loaded_banner,
    )
    from ..scenarios import load_scenario
    from ..scenarios.loader import scenario_to_initial_state

    scenario_path = resolve_scenario_path_with_game_root(
        scenario_file=scenario_file,
        game_root=game_root,
        scenario_id=scenario_id,
    )
    scenario_data = load_scenario(scenario_path)
    game_def = load_game_definition_for_scenario(scenario_path, schedule=schedule)
    first = initial_turn_slot_for_game_definition(game_def)

    initial_state = scenario_to_initial_state(
        scenario_data,
        initial_faction=first["faction"],
        initial_phase=first["phase"],
        phase_actions_remaining=int(first["max_actions"]),
        schedule_index=0,
    )

    server = WebSocketGameServer(
        host="0.0.0.0",
        port=8765,
        initial_state=initial_state,
        map_display=scenario_data.map_display.to_wire_dict(),
        global_styles=scenario_data.global_styles.to_wire_dict(),
        unit_graphics=scenario_data.unit_graphics_to_wire_dict(),
        marker_graphics=scenario_data.marker_graphics_to_wire_dict(),
        markers=scenario_data.markers_to_wire_list(),
        game_definition=game_def,
    )
    try_hexdemo_loaded_banner(scenario_path)
    await server.start()


def run(argv: list[str] | None = None) -> None:
    """Synchronous entry point for console script."""
    args = build_websocket_arg_parser().parse_args(
        argv if argv is not None else sys.argv[1:]
    )
    asyncio.run(
        main(
            scenario_file=args.scenario_file,
            game_root=args.game_root,
            scenario_id=args.scenario_id,
            schedule=args.schedule,
        )
    )


if __name__ == "__main__":
    run()
