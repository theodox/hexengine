"""Tests for wire snapshot serialization and ActionManager.replace_state."""

from __future__ import annotations

import unittest

from hexengine.hexes.types import Hex
from hexengine.state import ActionManager, GameState
from hexengine.state.actions import MoveUnit
from hexengine.state.game_state import BoardState, LocationState, TurnState, UnitState
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
        original = GameState(board=board, turn=turn)

        wire = game_state_to_wire_dict(original)
        restored = game_state_from_wire_dict(wire)

        self.assertEqual(restored, original)


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


if __name__ == "__main__":
    unittest.main()
