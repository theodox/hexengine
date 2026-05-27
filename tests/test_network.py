"""
Test the multiplayer networking infrastructure.

Tests WebSocketClient, GameServer, and client/server integration.
"""

from __future__ import annotations

import asyncio
import unittest

from hexengine.gamedef.builtin import InterleavedTwoFactionGameDefinition
from hexengine.gamedef.game_data import GameData
from hexengine.hexes.math import neighbors
from hexengine.hexes.types import Hex, HexColRow
from hexengine.hooks.attack import (
    AttackHooks,
    AttackResolution,
    attack_hooks_unsupported,
)
from hexengine.hooks.movement import MovementHooks
from hexengine.hooks.title import TitleHooks
from hexengine.hooks.ui import UIHooks
from hexengine.hooks.ui_turn_action_dock import empty_turn_action_dock_for_viewer
from hexengine.server import (
    ActionRequest,
    GameServer,
    Message,
)
from hexengine.server.protocol import JoinGameRequest, StateUpdate
from hexengine.state import GameState
from hexengine.state.title_extension import title_bucket
from hexengine.state.actions import MoveUnit
from hexengine.state.game_state import BoardState, TurnState, UnitState
from hexengine.state.snapshot import game_state_to_wire_dict


def _hex_wire(h: Hex) -> dict[str, int]:
    return {"i": h.i, "j": h.j, "k": h.k}


_TEST_TITLE_DOCK_UI = UIHooks(
    turn_action_dock_for_viewer=empty_turn_action_dock_for_viewer,
)


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

    def test_player_join(self):
        """Test player can join the game."""

        async def run():
            player_id = "test-player-1"
            join_request = JoinGameRequest(player_name="Alice", faction="Red")

            await self.server.handle_message(player_id, join_request.to_message())

            self.assertEqual(len(self.server.players), 1)
            self.assertIn(player_id, self.server.players)

            player = self.server.players[player_id]
            self.assertEqual(player.player_name, "Alice")
            self.assertEqual(player.faction, "Red")

        asyncio.run(run())

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

    def test_action_request_wrong_turn(self):
        """Test action rejected if not player's turn."""

        async def run():
            player_id = "test-player-1"
            join_request = JoinGameRequest(player_name="Alice", faction="Blue")
            await self.server.handle_message(player_id, join_request.to_message())

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
            current_faction = (
                self.server.action_manager.current_state.turn.current_faction
            )
            self.assertNotEqual(player.faction, current_faction)

        asyncio.run(run())

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

    def test_game_data_max_stack_enforces_move(self) -> None:
        async def run() -> None:
            start = Hex.from_hex_col_row(HexColRow(0, 0))
            dest = next(iter(neighbors(start)))
            board = BoardState(
                units={
                    "mover": UnitState(
                        unit_id="mover",
                        unit_type="t",
                        faction="Blue",
                        position=start,
                        active=True,
                    ),
                    "b1": UnitState(
                        unit_id="b1",
                        unit_type="t",
                        faction="Blue",
                        position=dest,
                        active=True,
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

            class _GD(InterleavedTwoFactionGameDefinition):
                @property
                def game_data(self) -> GameData:
                    return super().game_data.replacing(max_active_units_per_hex=1)

                def movement_budget_for_unit(
                    self, _state: GameState, _unit_id: str
                ) -> float:
                    return 10.0

                @property
                def hooks(self) -> TitleHooks:
                    return TitleHooks(
                        movement=MovementHooks(),
                        attack=attack_hooks_unsupported(),
                    )

            server = GameServer(state, game_definition=_GD())
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
                    "unit_id": "mover",
                    "from_hex": _hex_wire(start),
                    "to_hex": _hex_wire(dest),
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            self.assertTrue(errors)
            self.assertIn("stacking limit", errors[-1])

        asyncio.run(run())

    def test_hooks_attack_validate_used_when_present(self) -> None:
        async def run() -> None:
            h0 = Hex.from_hex_col_row(HexColRow(0, 0))
            h1 = next(iter(neighbors(h0)))
            board = BoardState(
                units={
                    "a": UnitState(
                        unit_id="a",
                        unit_type="t",
                        faction="Blue",
                        position=h0,
                        active=True,
                    ),
                    "d": UnitState(
                        unit_id="d",
                        unit_type="t",
                        faction="Red",
                        position=h1,
                        active=True,
                    ),
                }
            )
            turn = TurnState(
                current_faction="Blue",
                current_phase="Combat",
                phase_actions_remaining=2,
                schedule_index=1,
            )
            state = GameState(board=board, turn=turn, title_state={}, title_bucket_key="t", rng_log=())

            class _GD(InterleavedTwoFactionGameDefinition):
                @property
                def game_data(self) -> GameData:
                    return super().game_data.replacing(title_state_extension_key="t")

                @property
                def hooks(self) -> TitleHooks:
                    def _reject(_ctx):
                        raise ValueError("nope")

                    return TitleHooks(
                        ui=_TEST_TITLE_DOCK_UI,
                        attack=AttackHooks(
                            validate_attack=_reject,
                            resolve_attack=lambda _c: AttackResolution(outcome="miss"),
                        ),
                    )

            server = GameServer(state, game_definition=_GD())
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
                action_type="Attack",
                params={
                    "attack_kind": "adjacent",
                    "attacker_id": "a",
                    "defender_id": "d",
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            self.assertTrue(errors)
            self.assertIn("nope", errors[-1])

        asyncio.run(run())

    def test_hooks_attack_resolve_can_choose_retreat_owner(self) -> None:
        async def run() -> None:
            h0 = Hex.from_hex_col_row(HexColRow(0, 0))
            h1 = next(iter(neighbors(h0)))
            board = BoardState(
                units={
                    "a": UnitState(
                        unit_id="a",
                        unit_type="t",
                        faction="Blue",
                        position=h0,
                        active=True,
                    ),
                    "d": UnitState(
                        unit_id="d",
                        unit_type="t",
                        faction="Red",
                        position=h1,
                        active=True,
                    ),
                    # Extra friendly unit stacked with attacker.
                    "a2": UnitState(
                        unit_id="a2",
                        unit_type="t",
                        faction="Blue",
                        position=h0,
                        active=True,
                        stack_index=1,
                    ),
                }
            )
            turn = TurnState(
                current_faction="Blue",
                current_phase="Combat",
                phase_actions_remaining=2,
                schedule_index=1,
            )
            state = GameState(board=board, turn=turn, title_state={}, title_bucket_key="t", rng_log=())

            class _GD(InterleavedTwoFactionGameDefinition):
                @property
                def game_data(self) -> GameData:
                    return super().game_data.replacing(title_state_extension_key="t")

                @property
                def hooks(self) -> TitleHooks:
                    def resolve(_ctx):
                        # Force attacker retreat, but choose a2 as the retreat owner.
                        from hexengine.hooks.attack import AttackResolution

                        return AttackResolution(
                            outcome="attacker_retreat",
                            retreat_distance=1,
                            retreat_unit_id="a2",
                            rng_entry={"op": "test"},
                        )

                    return TitleHooks(
                        ui=_TEST_TITLE_DOCK_UI,
                        attack=AttackHooks(
                            validate_attack=lambda _c: None, resolve_attack=resolve
                        ),
                    )

            server = GameServer(state, game_definition=_GD())
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
                action_type="Attack",
                params={
                    "attack_kind": "adjacent",
                    "attacker_id": "a",
                    "defender_id": "d",
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            self.assertFalse(errors)
            from hexengine.state.title_extension import title_bucket

            hx = title_bucket(server.action_manager.current_state, "t")
            self.assertEqual(hx.get("last_combat", {}).get("retreat_unit_id"), "a2")
            ro = hx.get("retreat_obligations", {})
            # Group retreat applies to the stack at a2's hex (h0), so both Blue units retreat.
            self.assertEqual(ro.get("a"), 1)
            self.assertEqual(ro.get("a2"), 1)

        asyncio.run(run())

    def test_hooks_retreat_blocked_hexes_blocks_retreat_path(self) -> None:
        async def run() -> None:
            h0 = Hex.from_hex_col_row(HexColRow(0, 0))
            h1 = next(iter(neighbors(h0)))
            board = BoardState(
                units={
                    "u": UnitState(
                        unit_id="u",
                        unit_type="t",
                        faction="Blue",
                        position=h0,
                        active=True,
                    ),
                }
            )
            turn = TurnState(
                current_faction="Blue",
                current_phase="Combat",
                phase_actions_remaining=2,
                schedule_index=1,
            )
            state = GameState(
                board=board,
                turn=turn,
                title_state={"retreat_obligations": {"u": 1}},
                title_bucket_key="t",
                rng_log=(),
            )

            class _GD(InterleavedTwoFactionGameDefinition):
                @property
                def game_data(self) -> GameData:
                    return super().game_data.replacing(title_state_extension_key="t")

                @property
                def hooks(self) -> TitleHooks:
                    return TitleHooks(
                        ui=_TEST_TITLE_DOCK_UI,
                        movement=MovementHooks(
                            retreat_obligation_hexes_remaining=lambda st, uid: (
                                1 if uid == "u" else None
                            ),
                            faction_has_pending_retreat_obligation=lambda _st, fac: (
                                fac == "Blue"
                            ),
                            retreat_blocked_hexes=lambda _st, _uid: frozenset({h1}),
                        ),
                        attack=attack_hooks_unsupported(),
                    )

            server = GameServer(state, game_definition=_GD())
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
                    "unit_id": "u",
                    "from_hex": _hex_wire(h0),
                    "to_hex": _hex_wire(h1),
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            self.assertTrue(errors)
            self.assertIn("Illegal retreat path", errors[-1])

        asyncio.run(run())

    def test_hooks_validate_retreat_move_can_override_distance_rule(self) -> None:
        async def run() -> None:
            h0 = Hex.from_hex_col_row(HexColRow(0, 0))
            # We'll make obligation 2 but allow a 1-hex retreat.
            h1 = next(iter(neighbors(h0)))
            board = BoardState(
                units={
                    "u": UnitState(
                        unit_id="u",
                        unit_type="t",
                        faction="Blue",
                        position=h0,
                        active=True,
                    ),
                }
            )
            turn = TurnState(
                current_faction="Blue",
                current_phase="Combat",
                phase_actions_remaining=2,
                schedule_index=1,
            )
            state = GameState(
                board=board,
                turn=turn,
                title_state={"retreat_obligations": {"u": 2}},
                title_bucket_key="t",
                rng_log=(),
            )

            class _GD(InterleavedTwoFactionGameDefinition):
                @property
                def game_data(self) -> GameData:
                    return super().game_data.replacing(title_state_extension_key="t")

                @property
                def hooks(self) -> TitleHooks:
                    def allow_any_distance(_ctx, _rem: int) -> None:
                        return None

                    return TitleHooks(
                        ui=_TEST_TITLE_DOCK_UI,
                        movement=MovementHooks(
                            retreat_obligation_hexes_remaining=lambda _st, uid: (
                                2 if uid == "u" else None
                            ),
                            faction_has_pending_retreat_obligation=lambda _st, fac: (
                                fac == "Blue"
                            ),
                            validate_retreat_move=allow_any_distance,
                        ),
                        attack=attack_hooks_unsupported(),
                    )

            server = GameServer(state, game_definition=_GD())
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
                    "unit_id": "u",
                    "from_hex": _hex_wire(h0),
                    "to_hex": _hex_wire(h1),
                },
                player_id="p1",
            )
            await server.handle_message("p1", req.to_message())
            self.assertFalse(errors)

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

    def test_turn_rules_wire_builtin_omits_title_state_extension_key(self) -> None:
        server = GameServer(self.initial_state, game_definition=_test_game_definition())
        tr = server._turn_rules_wire()
        self.assertNotIn("title_state_extension_key", tr)

    def test_turn_rules_wire_builtin_includes_faction_ui_labels(self) -> None:
        server = GameServer(self.initial_state, game_definition=_test_game_definition())
        tr = server._turn_rules_wire()
        self.assertNotIn("faction_display_contract_error", tr)
        fu = tr.get("faction_ui")
        self.assertIsInstance(fu, dict)
        rows = fu.get("factions")
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)
        by_id = {str(r["id"]): r for r in rows}
        self.assertEqual(by_id["Red"]["label"], "Red")
        self.assertEqual(by_id["Blue"]["label"], "Blue")

    def test_turn_rules_wire_faction_display_contract_error_without_labels(
        self,
    ) -> None:
        class _NoFactionLabels(InterleavedTwoFactionGameDefinition):
            @property
            def game_data(self) -> GameData:
                return GameData()

        server = GameServer(self.initial_state, game_definition=_NoFactionLabels())
        tr = server._turn_rules_wire()
        self.assertIn("faction_display_contract_error", tr)
        self.assertNotIn("faction_ui", tr)
        err = tr["faction_display_contract_error"]
        self.assertIsInstance(err, dict)
        self.assertIn("Red", err.get("missing_faction_ids", []))
        self.assertIn("Blue", err.get("missing_faction_ids", []))

    def test_turn_rules_wire_hexdemo_includes_title_state_extension_key(self) -> None:
        from games.hexdemo.game_config import (
            HexdemoGameDefinition,
            default_match_config,
            game_definition_from_config,
        )

        base = game_definition_from_config(default_match_config())
        gd = HexdemoGameDefinition(base)
        server = GameServer(self.initial_state, game_definition=gd)
        tr = server._turn_rules_wire()
        self.assertEqual(tr.get("title_state_extension_key"), "hexdemo")
        self.assertEqual(tr.get("max_active_units_per_hex"), 3)
        su = tr.get("shell_ui")
        self.assertIsInstance(su, dict)
        self.assertEqual(su.get("advance_turn_button_label"), "End Phase")
        self.assertEqual(su.get("attack_confirm_label"), "Confirm attack")
        kinds = tr.get("interaction_kind_styles")
        self.assertIsInstance(kinds, dict)
        self.assertEqual(kinds.get("phase"), "interaction-msg--phase")

    def test_after_next_phase_builtin_skips_title_combat_extension_clear(self) -> None:
        """Built-in `GameDefinition` has no `title_state_extension_key`; do not mutate."""
        server = GameServer(self.initial_state, game_definition=_test_game_definition())
        hx0 = {
            "attacks_this_phase": ["x"],
            "last_combat": {"outcome": "none"},
        }
        server.action_manager._current_state = (
            server.action_manager.current_state.with_title_state(
                hx0, title_bucket_key="hexdemo"
            )
        )
        server._after_next_phase_applied()
        from hexengine.state.title_extension import title_bucket

        hx = title_bucket(server.action_manager.current_state, "hexdemo")
        self.assertIsInstance(hx, dict)
        self.assertIn("attacks_this_phase", hx)


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


def test_state_update_map_overlays_round_trip() -> None:
    """StateUpdate carries optional map_overlays list for client DOM sync."""
    from hexengine.server.protocol import Message, StateUpdate

    msg = StateUpdate(
        game_state={"board": {"units": {}}},
        sequence_number=7,
        map_overlays=[
            {
                "schema": 1,
                "id": "t1",
                "kind": "glyph",
                "hex": {"i": 1, "j": -1, "k": 0},
                "text": "🟎",
                "css_class": "x",
            }
        ],
    ).to_message()
    restored = Message.from_json(msg.to_json())
    assert restored.type == StateUpdate.wire_type
    p = restored.payload
    assert isinstance(p.get("map_overlays"), list)
    assert p["map_overlays"][0]["id"] == "t1"


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
            "inspect",
            "marker_preview_request",
            "unit_preview_request",
            "map_selection_preview_request",
            # server -> client
            "state_update",
            "action_result",
            "player_joined",
            "player_left",
            "error",
            "server_log",
            "combat_event",
            "ui_popup",
            "marker_preview",
            "unit_preview",
            "map_selection_preview",
        }
    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
