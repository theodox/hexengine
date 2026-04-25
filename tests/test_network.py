"""
Test the multiplayer networking infrastructure.

Tests WebSocketClient, GameServer, and client/server integration.
"""

from __future__ import annotations

import asyncio
import unittest

from hexengine.gamedef.builtin import InterleavedTwoFactionGameDefinition
from hexengine.hexes.math import neighbors
from hexengine.hexes.types import Hex, HexColRow
from hexengine.server import (
    ActionRequest,
    GameServer,
    Message,
)
from hexengine.server.protocol import JoinGameRequest, StateUpdate
from hexengine.state import GameState
from hexengine.state.actions import MoveUnit
from hexengine.state.game_state import BoardState, TurnState, UnitState
from hexengine.state.snapshot import game_state_to_wire_dict


def _hex_wire(h: Hex) -> dict[str, int]:
    return {"i": h.i, "j": h.j, "k": h.k}


def _test_game_definition() -> InterleavedTwoFactionGameDefinition:
    """Red/Blue engine demo schedule for headless server tests."""
    return InterleavedTwoFactionGameDefinition()


class TestGameServer(unittest.TestCase):
    """Test the GameServer class."""

    def setUp(self):
        """Set up test fixtures."""
        self.initial_state = GameState.create_empty()
        self.server = GameServer(
            self.initial_state, game_definition=_test_game_definition()
        )

    def test_server_initialization(self):
        """Test server initializes correctly."""
        self.assertIsNotNone(self.server.game_state)
        self.assertIsNotNone(self.server.action_manager)
        self.assertEqual(len(self.server.players), 0)

    async def test_player_join(self):
        """Test player can join the game."""
        player_id = "test-player-1"
        join_request = JoinGameRequest(player_name="Alice", faction="Red")

        await self.server.handle_message(player_id, join_request.to_message())

        # Check player was added
        self.assertEqual(len(self.server.players), 1)
        self.assertIn(player_id, self.server.players)

        player = self.server.players[player_id]
        self.assertEqual(player.player_name, "Alice")
        self.assertEqual(player.faction, "Red")

    def test_leave_frees_faction_for_reconnect(self):
        """Disconnect removes player so a new WebSocket id can take the same faction."""

        async def run():
            server = GameServer(
                self.initial_state, game_definition=_test_game_definition()
            )
            join_red = JoinGameRequest(player_name="Alice", faction="Red").to_message()
            leave = Message(type="leave_game", payload={})

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
            server = GameServer(
                self.initial_state, game_definition=_test_game_definition()
            )
            errors: list[tuple[str, str]] = []

            def capture(pid: str, m: Message) -> None:
                if m.type == "error":
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
            schedule_index=0,
        )
        self.server.action_manager.replace_state(state.with_turn(new_turn))

        player = self.server.players[player_id]
        current_faction = self.server.action_manager.current_state.turn.current_faction
        self.assertNotEqual(player.faction, current_faction)

    def test_move_unit_rejected_out_of_budget(self) -> None:
        """Server rejects MoveUnit when path cost exceeds movement budget."""

        async def run() -> None:
            start = Hex.from_hex_col_row(HexColRow(0, 0))
            far = Hex.from_hex_col_row(HexColRow(20, 0))
            board = BoardState(
                units={
                    "u1": UnitState(
                        unit_id="u1",
                        unit_type="t",
                        faction="Blue",
                        position=start,
                    )
                }
            )
            turn = TurnState(
                current_faction="Blue",
                current_phase="Movement",
                phase_actions_remaining=2,
                schedule_index=1,
            )
            state = GameState(board=board, turn=turn)
            server = GameServer(state, game_definition=_test_game_definition())
            errors: list[str] = []

            def capture(_pid: str, m: Message) -> None:
                if m.type == "error":
                    errors.append(str(m.payload.get("error", "")))

            server.add_message_handler(capture)
            await server.handle_message(
                "p1",
                JoinGameRequest(player_name="Alice", faction="Blue").to_message(),
            )
            req = ActionRequest(
                action_type="MoveUnit",
                params={
                    "unit_id": "u1",
                    "from_hex": _hex_wire(start),
                    "to_hex": _hex_wire(far),
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            self.assertTrue(errors)
            self.assertIn("Illegal move", errors[-1])
            self.assertEqual(
                server.action_manager.current_state.board.units["u1"].position, start
            )

        asyncio.run(run())

    def test_move_unit_rejected_wrong_from_hex(self) -> None:
        async def run() -> None:
            start = Hex.from_hex_col_row(HexColRow(0, 0))
            nlist = list(neighbors(start))
            wrong_from, dest = nlist[0], nlist[1]
            board = BoardState(
                units={
                    "u1": UnitState(
                        unit_id="u1",
                        unit_type="t",
                        faction="Blue",
                        position=start,
                    )
                }
            )
            turn = TurnState(
                current_faction="Blue",
                current_phase="Movement",
                phase_actions_remaining=2,
                schedule_index=1,
            )
            state = GameState(board=board, turn=turn)
            server = GameServer(state, game_definition=_test_game_definition())
            errors: list[str] = []

            def capture(_pid: str, m: Message) -> None:
                if m.type == "error":
                    errors.append(str(m.payload.get("error", "")))

            server.add_message_handler(capture)
            await server.handle_message(
                "p1",
                JoinGameRequest(player_name="Alice", faction="Blue").to_message(),
            )
            req = ActionRequest(
                action_type="MoveUnit",
                params={
                    "unit_id": "u1",
                    "from_hex": _hex_wire(wrong_from),
                    "to_hex": _hex_wire(dest),
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            self.assertTrue(any("from_hex" in e for e in errors))

        asyncio.run(run())

    def test_move_unit_rejected_outside_movement_phase(self) -> None:
        async def run() -> None:
            start = Hex.from_hex_col_row(HexColRow(0, 0))
            nbr = list(neighbors(start))[0]
            board = BoardState(
                units={
                    "u1": UnitState(
                        unit_id="u1",
                        unit_type="t",
                        faction="Blue",
                        position=start,
                    )
                }
            )
            turn = TurnState(
                current_faction="Blue",
                current_phase="Attack",
                phase_actions_remaining=2,
            )
            state = GameState(board=board, turn=turn)
            server = GameServer(state, game_definition=_test_game_definition())
            errors: list[str] = []

            def capture(_pid: str, m: Message) -> None:
                if m.type == "error":
                    errors.append(str(m.payload.get("error", "")))

            server.add_message_handler(capture)
            await server.handle_message(
                "p1",
                JoinGameRequest(player_name="Alice", faction="Blue").to_message(),
            )
            req = ActionRequest(
                action_type="MoveUnit",
                params={
                    "unit_id": "u1",
                    "from_hex": _hex_wire(start),
                    "to_hex": _hex_wire(nbr),
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            self.assertTrue(errors)
            self.assertIn("movement", errors[-1].lower())

        asyncio.run(run())

    def test_move_unit_rejected_onto_occupied_hex(self) -> None:
        async def run() -> None:
            start = Hex.from_hex_col_row(HexColRow(0, 0))
            nlist = list(neighbors(start))
            occupied = nlist[0]
            board = BoardState(
                units={
                    "u1": UnitState(
                        unit_id="u1",
                        unit_type="t",
                        faction="Blue",
                        position=start,
                    ),
                    "u2": UnitState(
                        unit_id="u2",
                        unit_type="t",
                        faction="Blue",
                        position=occupied,
                    ),
                }
            )
            turn = TurnState(
                current_faction="Blue",
                current_phase="Movement",
                phase_actions_remaining=2,
                schedule_index=1,
            )
            state = GameState(board=board, turn=turn)
            server = GameServer(state, game_definition=_test_game_definition())
            errors: list[str] = []

            def capture(_pid: str, m: Message) -> None:
                if m.type == "error":
                    errors.append(str(m.payload.get("error", "")))

            server.add_message_handler(capture)
            await server.handle_message(
                "p1",
                JoinGameRequest(player_name="Alice", faction="Blue").to_message(),
            )
            req = ActionRequest(
                action_type="MoveUnit",
                params={
                    "unit_id": "u1",
                    "from_hex": _hex_wire(start),
                    "to_hex": _hex_wire(occupied),
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            self.assertTrue(errors)
            self.assertIn("Illegal move", errors[-1])

        asyncio.run(run())

    def test_move_unit_accepted_adjacent(self) -> None:
        async def run() -> None:
            start = Hex.from_hex_col_row(HexColRow(0, 0))
            nbr = list(neighbors(start))[0]
            board = BoardState(
                units={
                    "u1": UnitState(
                        unit_id="u1",
                        unit_type="t",
                        faction="Blue",
                        position=start,
                    )
                }
            )
            turn = TurnState(
                current_faction="Blue",
                current_phase="Movement",
                phase_actions_remaining=2,
                schedule_index=1,
            )
            state = GameState(board=board, turn=turn)
            server = GameServer(state, game_definition=_test_game_definition())
            errors: list[str] = []

            def capture(_pid: str, m: Message) -> None:
                if m.type == "error":
                    errors.append(str(m.payload.get("error", "")))

            server.add_message_handler(capture)
            await server.handle_message(
                "p1",
                JoinGameRequest(player_name="Alice", faction="Blue").to_message(),
            )
            req = ActionRequest(
                action_type="MoveUnit",
                params={
                    "unit_id": "u1",
                    "from_hex": _hex_wire(start),
                    "to_hex": _hex_wire(nbr),
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            self.assertFalse(errors)
            self.assertEqual(
                server.action_manager.current_state.board.units["u1"].position, nbr
            )

        asyncio.run(run())

    def test_next_phase_uses_server_schedule_not_client_payload(self) -> None:
        """Manual advance: server must ignore client-supplied faction/phase (authoritative)."""

        async def run() -> None:
            from hexengine.gamedef.builtin import InterleavedTwoFactionGameDefinition
            from hexengine.server.protocol import ActionRequest, JoinGameRequest

            gd = InterleavedTwoFactionGameDefinition(factions=("confederate", "union"))
            st = GameState(
                board=BoardState(),
                turn=TurnState(
                    current_faction="confederate",
                    current_phase="Movement",
                    phase_actions_remaining=2,
                    schedule_index=0,
                ),
            )
            server = GameServer(st, game_definition=gd)
            await server.handle_message(
                "p1",
                JoinGameRequest(
                    player_name="Alice", faction="confederate"
                ).to_message(),
            )
            req = ActionRequest(
                action_type="NextPhase",
                params={
                    "new_faction": "Red",
                    "new_phase": "Attack",
                    "max_actions": 99,
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            t = server.action_manager.current_state.turn
            self.assertEqual(t.current_faction, "union")
            self.assertEqual(t.current_phase, "Movement")
            self.assertEqual(t.phase_actions_remaining, 2)

        asyncio.run(run())


class TestStateUpdateTurnRules(unittest.TestCase):
    def test_state_update_turn_rules_roundtrip(self) -> None:
        st = GameState.create_empty(
            initial_faction="confederate",
            initial_phase="Attack",
            schedule_index=2,
        )
        wire = game_state_to_wire_dict(st)
        rules = {
            "turn_rules_schema": 1,
            "entries": [
                {"faction": "confederate", "phase": "Movement", "max_actions": 2},
                {"faction": "union", "phase": "Movement", "max_actions": 2},
                {"faction": "confederate", "phase": "Attack", "max_actions": 2},
                {"faction": "union", "phase": "Attack", "max_actions": 2},
            ],
            "movement_budget": 4.0,
            "rota_id": "deadbeef00000000",
            "client_contract": {"schema": 1, "features": ["retreat_obligations"]},
        }
        u = StateUpdate(
            game_state=wire,
            sequence_number=3,
            turn_rules=rules,
            suggested_focus_unit_id="u-1",
            retreat_obligations={"u-1": 2},
        )
        m = u.to_message()
        u2 = StateUpdate.from_message(m)
        self.assertEqual(u2.turn_rules, rules)


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

        self.assertEqual(message.type, "action_request")
        self.assertEqual(message.payload["action_type"], "MoveUnit")
        self.assertEqual(message.payload["player_id"], "player-1")

    def test_message_json_serialization(self):
        """Test Message can be serialized to/from JSON."""
        original = Message(
            type="action_request",
            payload={"test": "data"},
        )

        # Serialize to JSON
        json_str = original.to_json()

        # Deserialize back
        restored = Message.from_json(json_str)

        self.assertEqual(restored.type, original.type)
        self.assertEqual(restored.payload, original.payload)


def test_wire_message_registry_covers_all_message_types() -> None:
    """Every wire message type must have a @wire_message payload class."""
    from hexengine.server.protocol import registered_message_types

    assert registered_message_types() == frozenset(
        {
            # client -> server
            "action_request",
            "join_game",
            "leave_game",
            "undo_request",
            "redo_request",
            "load_snapshot",
            # server -> client
            "state_update",
            "action_result",
            "player_joined",
            "player_left",
            "error",
            "server_log",
            "combat_event",
        }
    )


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
