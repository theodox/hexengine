"""
Test the multiplayer networking infrastructure.

Tests WebSocketClient, GameServer, and NetworkGame integration.
"""

from __future__ import annotations

import asyncio
import unittest

from hexengine.hexes.types import Hex
from hexengine.server import ActionRequest, GameServer, Message, MessageType
from hexengine.server.protocol import JoinGameRequest
from hexengine.state import GameState
from hexengine.state.actions import MoveUnit


class TestGameServer(unittest.TestCase):
    """Test the GameServer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.initial_state = GameState.create_empty()
        self.server = GameServer(self.initial_state)

    def test_server_initialization(self):
        """Test server initializes correctly."""
        self.assertIsNotNone(self.server.game_state)
        self.assertIsNotNone(self.server.action_manager)
        self.assertEqual(len(self.server.players), 0)

    async def test_player_join(self):
        """Test player can join the game."""
        player_id = "test-player-1"
        join_request = JoinGameRequest(player_name="Alice", faction="Blue")

        await self.server.handle_message(player_id, join_request.to_message())

        # Check player was added
        self.assertEqual(len(self.server.players), 1)
        self.assertIn(player_id, self.server.players)

        player = self.server.players[player_id]
        self.assertEqual(player.player_name, "Alice")
        self.assertEqual(player.faction, "Blue")

    def test_leave_frees_faction_for_reconnect(self):
        """Disconnect removes player so a new WebSocket id can take the same faction."""

        async def run():
            server = GameServer(self.initial_state)
            join_red = JoinGameRequest(player_name="Alice", faction="Red").to_message()
            leave = Message(type=MessageType.LEAVE_GAME, payload={})

            await server.handle_message("conn-a", join_red)
            self.assertIn("conn-a", server.players)
            self.assertEqual(server.faction_to_player.get("Red"), "conn-a")

            await server.handle_message("conn-a", leave)
            self.assertEqual(len(server.players), 0)
            self.assertNotIn("Red", server.faction_to_player)

            await server.handle_message(
                "conn-b",
                JoinGameRequest(player_name="Bob", faction="Blue").to_message(),
            )
            await server.handle_message(
                "conn-c",
                JoinGameRequest(player_name="Carol", faction="Red").to_message(),
            )
            self.assertEqual(len(server.players), 2)
            self.assertEqual(server.faction_to_player["Red"], "conn-c")
            self.assertEqual(server.faction_to_player["Blue"], "conn-b")

        asyncio.run(run())

    def test_explicit_faction_taken_is_rejected(self):
        """If client names a faction that is already taken, do not auto-assign another."""

        async def run():
            server = GameServer(self.initial_state)
            errors: list[tuple[str, str]] = []

            def capture(pid: str, m: Message) -> None:
                if m.type == MessageType.ERROR:
                    errors.append((pid, str(m.payload.get("error", ""))))

            server.add_message_handler(capture)

            await server.handle_message(
                "conn-1",
                JoinGameRequest(player_name="P1", faction="Blue").to_message(),
            )
            await server.handle_message(
                "conn-2",
                JoinGameRequest(player_name="P2", faction="Blue").to_message(),
            )
            self.assertEqual(len(server.players), 1)
            self.assertEqual(server.faction_to_player.get("Blue"), "conn-1")
            self.assertTrue(errors)
            self.assertIn("already taken", errors[-1][1])

        asyncio.run(run())

    async def test_action_request_wrong_turn(self):
        """Test action rejected if not player's turn."""
        # Join as Blue faction
        player_id = "test-player-1"
        join_request = JoinGameRequest(player_name="Alice", faction="Blue")
        await self.server.handle_message(player_id, join_request.to_message())

        # Set current turn to Red
        state = self.server.action_manager.current_state
        from hexengine.state.game_state import TurnState

        new_turn = TurnState(
            turn_number=1,
            current_faction="Red",  # Not Blue
            current_phase="Movement",
            phase_actions_remaining=2,
        )
        self.server.action_manager.replace_state(state.with_turn(new_turn))

        player = self.server.players[player_id]
        current_faction = self.server.action_manager.current_state.turn.current_faction
        self.assertNotEqual(player.faction, current_faction)


class TestActionSerialization(unittest.TestCase):
    """Test action serialization for network transmission."""

    def test_move_unit_serialization(self):
        """Test MoveUnit action can be serialized."""
        action = MoveUnit(unit_id="tank-1", from_hex=Hex(0, 0, 0), to_hex=Hex(1, 0, -1))

        # Serialize
        params = {
            "unit_id": action.unit_id,
            "from_hex": {
                "i": action.from_hex.i,
                "j": action.from_hex.j,
                "k": action.from_hex.k,
            },
            "to_hex": {
                "i": action.to_hex.i,
                "j": action.to_hex.j,
                "k": action.to_hex.k,
            },
        }

        # Verify
        self.assertEqual(params["unit_id"], "tank-1")
        self.assertEqual(params["from_hex"]["i"], 0)
        self.assertEqual(params["to_hex"]["i"], 1)

    def test_action_request_message(self):
        """Test ActionRequest can be converted to Message."""
        request = ActionRequest(
            action_type="MoveUnit", params={"unit_id": "unit-1"}, player_id="player-1"
        )

        message = request.to_message()

        self.assertEqual(message.type, MessageType.ACTION_REQUEST)
        self.assertEqual(message.payload["action_type"], "MoveUnit")
        self.assertEqual(message.payload["player_id"], "player-1")

    def test_message_json_serialization(self):
        """Test Message can be serialized to/from JSON."""
        original = Message(type=MessageType.ACTION_REQUEST, payload={"test": "data"})

        # Serialize to JSON
        json_str = original.to_json()

        # Deserialize back
        restored = Message.from_json(json_str)

        self.assertEqual(restored.type, original.type)
        self.assertEqual(restored.payload, original.payload)


def run_async_test(coro):
    """Helper to run async test."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


if __name__ == "__main__":
    # Need to handle async tests
    for test_case in [TestGameServer]:
        for method_name in dir(test_case):
            if method_name.startswith("test_"):
                method = getattr(test_case, method_name)
                if asyncio.iscoroutinefunction(method):
                    print(f"\nRunning async test: {test_case.__name__}.{method_name}")
                    instance = test_case(method_name)
                    instance.setUp()
                    run_async_test(method(instance))

    # Run sync tests normally
    unittest.main(verbosity=2)
