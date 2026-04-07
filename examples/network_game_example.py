"""
Example: How to use the NetworkGame class for multiplayer.

Shows both single-player (local server) and multiplayer (remote server) setups.
"""

from __future__ import annotations

import asyncio
import logging

from hexengine.game import NetworkGame


async def example_singleplayer():
    """Example: Single-player game with local server."""
    logging.basicConfig(level=logging.INFO)

    # Create game with local server
    game = NetworkGame(
        server_url="ws://localhost:8765",
        player_name="Alice",
        preferred_faction="Blue",
        use_local_server=True,  # Starts local server automatically
    )

    # Connect (will start local server, then connect to it)
    if await game.connect():
        print("Connected to local server!")
        print(f"Playing as: {game.my_faction}")

        # Game is now ready - UI interactions will send actions to local server
        # The local server validates and broadcasts state updates back

        # Keep running...
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            await game.disconnect()
    else:
        print("Failed to connect")


async def example_multiplayer():
    """Example: Multiplayer game connecting to remote server."""
    logging.basicConfig(level=logging.INFO)

    # Create game connecting to remote server
    game = NetworkGame(
        server_url="ws://game.example.com:8765",
        player_name="Bob",
        preferred_faction="Red",
        use_local_server=False,  # Connect to remote server
    )

    # Connect to remote server
    if await game.connect():
        print("Connected to remote server!")
        print(f"Playing as: {game.my_faction}")

        # Game is now ready - actions sent to remote server
        # State updates received from remote server

        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            await game.disconnect()
    else:
        print("Failed to connect")


async def example_two_clients():
    """Example: Two clients playing against each other (local testing)."""
    logging.basicConfig(level=logging.INFO)

    # Start a dedicated local server
    from hexengine.server import WebSocketGameServer
    from hexengine.state import GameState

    # Create initial state with some units
    initial_state = GameState.create_empty()

    # Start server in background
    server = WebSocketGameServer(
        host="127.0.0.1", port=8765, initial_state=initial_state
    )
    server_task = asyncio.create_task(server.start())

    # Give server time to start
    await asyncio.sleep(0.5)

    # Create two clients
    player1 = NetworkGame(
        server_url="ws://localhost:8765",
        player_name="Alice",
        preferred_faction="Blue",
        use_local_server=False,  # Use existing server
    )

    player2 = NetworkGame(
        server_url="ws://localhost:8765",
        player_name="Bob",
        preferred_faction="Red",
        use_local_server=False,
    )

    # Connect both clients
    if await player1.connect() and await player2.connect():
        print(f"Player 1 connected as {player1.my_faction}")
        print(f"Player 2 connected as {player2.my_faction}")

        # Both players now see the same game state
        # Actions from either player are validated and broadcast to both

        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            await player1.disconnect()
            await player2.disconnect()
            server_task.cancel()


if __name__ == "__main__":
    # Run single-player example
    asyncio.run(example_singleplayer())

    # Or run multiplayer example:
    # asyncio.run(example_multiplayer())

    # Or run two-client test:
    # asyncio.run(example_two_clients())
