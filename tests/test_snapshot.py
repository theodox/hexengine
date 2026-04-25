"""Tests for wire snapshot serialization and ActionManager.replace_state."""

from __future__ import annotations

import unittest

from hexengine.hexes.types import Hex
from hexengine.state import ActionManager, GameState
from hexengine.gamedef.builtin import (
    InterleavedTwoFactionGameDefinition,
    advance_turn_action_for_state,
)
from hexengine.state.actions import MoveUnit, PatchUnitAttributes
from hexengine.state.game_state import (
    BoardState,
    LocationState,
    TurnState,
    UnitState,
    UnsetTerrainDefaults,
)
from hexengine.state.snapshot import game_state_from_wire_dict, game_state_to_wire_dict


class TestSnapshotRoundTrip(unittest.TestCase):
    def test_game_state_wire_round_trip(self):
        h0 = Hex(0, 0, 0)
        h1 = Hex(1, 0, -1)
        board = BoardState(
            units={
                "u1": UnitState(
                    unit_id="u1",
                    unit_type="tank",
                    faction="Red",
                    position=h0,
                    health=80,
                    active=True,
                )
            },
            locations={
                h0: LocationState(
                    position=h0,
                    terrain_type="plain",
                    movement_cost=1.0,
                    hex_color="#aabbcc",
                ),
                h1: LocationState(position=h1, terrain_type="hill", movement_cost=2.0),
            },
        )
        turn = TurnState(
            current_faction="Blue",
            current_phase="Attack",
            phase_actions_remaining=1,
            turn_number=3,
        )
        original = GameState(
            board=board,
            turn=turn,
            extension={"demo": {"x": 1}},
            rng_log=({"kind": "d6", "value": 3, "rolls": [3]},),
        )

        wire = game_state_to_wire_dict(original)
        restored = game_state_from_wire_dict(wire)

        self.assertEqual(restored, original)

    def test_game_state_wire_round_trip_with_graphics(self):
        h0 = Hex(0, 0, 0)
        board = BoardState(
            units={
                "u1": UnitState(
                    unit_id="u1",
                    unit_type="line_infantry",
                    faction="Red",
                    position=h0,
                    graphics="soldier",
                )
            },
        )
        turn = TurnState(
            current_faction="Red",
            current_phase="Movement",
            phase_actions_remaining=2,
            turn_number=1,
        )
        original = GameState(board=board, turn=turn)
        wire = game_state_to_wire_dict(original)
        self.assertEqual(wire["board"]["units"]["u1"]["graphics"], "soldier")
        restored = game_state_from_wire_dict(wire)
        self.assertEqual(restored, original)

    def test_game_state_wire_round_trip_unset_defaults(self):
        h0 = Hex(0, 0, 0)
        board = BoardState(
            locations={
                h0: LocationState(
                    position=h0,
                    terrain_type="hill",
                    movement_cost=3.0,
                ),
            },
            unset_defaults=UnsetTerrainDefaults(
                terrain_type="plain",
                movement_cost=1.25,
                hex_color="#00ff0088",
            ),
        )
        turn = TurnState(
            current_faction="Red",
            current_phase="Movement",
            phase_actions_remaining=2,
            turn_number=1,
        )
        original = GameState(board=board, turn=turn)
        wire = game_state_to_wire_dict(original)
        restored = game_state_from_wire_dict(wire)
        self.assertEqual(restored, original)
        h1 = Hex(1, 0, -1)
        self.assertEqual(restored.board.get_movement_cost(h1), 1.25)


class TestReplaceStateClearsUndo(unittest.TestCase):
    def test_replace_state_clears_undo(self):
        h0 = Hex(0, 0, 0)
        h1 = Hex(1, 0, -1)
        unit = UnitState(
            unit_id="u1",
            unit_type="tank",
            faction="Red",
            position=h0,
        )
        board = BoardState(
            units={"u1": unit},
            locations={
                h0: LocationState(position=h0, terrain_type="plain", movement_cost=1.0),
                h1: LocationState(position=h1, terrain_type="plain", movement_cost=1.0),
            },
        )
        turn = TurnState(
            current_faction="Red",
            current_phase="Movement",
            phase_actions_remaining=2,
            turn_number=1,
        )
        state = GameState(board=board, turn=turn)
        mgr = ActionManager(state)

        mgr.execute(MoveUnit(unit_id="u1", from_hex=h0, to_hex=h1))
        self.assertTrue(mgr.can_undo())

        fresh = GameState.create_empty()
        mgr.replace_state(fresh)

        self.assertIsNone(mgr.undo())
        self.assertFalse(mgr.can_undo())
        self.assertEqual(mgr.current_state, fresh)


class TestPerUnitStateStackingAndTick(unittest.TestCase):
    def test_wire_round_trip_attributes_stack_global_tick(self):
        h0 = Hex(0, 0, 0)
        board = BoardState(
            units={
                "a": UnitState(
                    unit_id="a",
                    unit_type="x",
                    faction="Red",
                    position=h0,
                    stack_index=0,
                    attributes={"pinned": 1},
                ),
                "b": UnitState(
                    unit_id="b",
                    unit_type="y",
                    faction="Red",
                    position=h0,
                    stack_index=1,
                    attributes={},
                ),
            },
        )
        turn = TurnState(
            current_faction="Red",
            current_phase="Movement",
            phase_actions_remaining=2,
            turn_number=1,
            schedule_index=0,
            global_tick=7,
        )
        original = GameState(board=board, turn=turn)
        wire = game_state_to_wire_dict(original)
        restored = game_state_from_wire_dict(wire)
        self.assertEqual(restored, original)

    def test_board_units_at_and_top_of_stack(self):
        h = Hex(2, -1, -1)
        b = BoardState(
            units={
                "low": UnitState(
                    unit_id="low",
                    unit_type="i",
                    faction="Blue",
                    position=h,
                    stack_index=0,
                ),
                "high": UnitState(
                    unit_id="high",
                    unit_type="j",
                    faction="Blue",
                    position=h,
                    stack_index=3,
                ),
            },
        )
        self.assertEqual(len(b.active_units_at_hex(h)), 2)
        self.assertEqual(b.get_unit_at(h).unit_id, "high")
        self.assertEqual(b.next_stack_index_at_hex(h), 4)

    def test_global_tick_increments_on_next_phase(self):
        state = GameState.create_empty()
        mgr = ActionManager(state)
        game = InterleavedTwoFactionGameDefinition()
        self.assertEqual(mgr.current_state.turn.global_tick, 0)
        mgr.execute(advance_turn_action_for_state(mgr.current_state, game))
        self.assertEqual(mgr.current_state.turn.global_tick, 1)

    def test_next_phase_undo_restores_global_tick(self):
        state = GameState.create_empty()
        mgr = ActionManager(state)
        game = InterleavedTwoFactionGameDefinition()
        act = advance_turn_action_for_state(mgr.current_state, game)
        mgr.execute(act)
        self.assertEqual(mgr.current_state.turn.global_tick, 1)
        mgr.undo()
        self.assertEqual(mgr.current_state.turn.global_tick, 0)

    def test_patch_unit_attributes_undo(self):
        h = Hex(0, 0, 0)
        u = UnitState(
            unit_id="u1",
            unit_type="t",
            faction="Red",
            position=h,
            attributes={"a": 1},
        )
        state = GameState(
            board=BoardState(units={"u1": u}),
            turn=TurnState(
                "Red",
                "Movement",
                2,
                schedule_index=0,
                global_tick=0,
            ),
        )
        mgr = ActionManager(state)
        mgr.execute(PatchUnitAttributes("u1", {"b": 2}))
        self.assertEqual(mgr.current_state.board.units["u1"].attributes["b"], 2)
        mgr.undo()
        self.assertEqual(mgr.current_state.board.units["u1"].attributes, {"a": 1})

    def test_move_unit_restores_stack_index_on_undo(self):
        h0 = Hex(0, 0, 0)
        h1 = Hex(1, 0, -1)
        u = UnitState(
            unit_id="m",
            unit_type="t",
            faction="Red",
            position=h0,
            stack_index=5,
        )
        state = GameState(
            board=BoardState(units={"m": u}),
            turn=TurnState("Red", "Movement", 2),
        )
        mgr = ActionManager(state)
        mgr.execute(MoveUnit(unit_id="m", from_hex=h0, to_hex=h1))
        self.assertNotEqual(mgr.current_state.board.units["m"].stack_index, 5)
        mgr.undo()
        self.assertEqual(mgr.current_state.board.units["m"].stack_index, 5)
        self.assertEqual(mgr.current_state.board.units["m"].position, h0)


if __name__ == "__main__":
    unittest.main()
