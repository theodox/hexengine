"""Headless tests for game definitions and turn schedules."""

from __future__ import annotations

import unittest
from dataclasses import replace

from hexengine.gamedef.builtin import (
    InterleavedTwoFactionGameDefinition,
    SequentialTwoFactionGameDefinition,
    StaticScheduleGameDefinition,
    advance_turn_action_for_state,
    default_game_definition,
)
from hexengine.gameroot import load_game_definition
from hexengine.hexes.types import Hex
from hexengine.state import BoardState, GameState, UnitState


class TestGameDefinitions(unittest.TestCase):
    def test_default_is_interleaved(self) -> None:
        g = default_game_definition()
        order = g.turn_order()
        self.assertEqual(order[0]["faction"], "Red")
        self.assertEqual(order[0]["phase"], "Movement")
        self.assertEqual(order[1]["faction"], "Blue")
        self.assertEqual(order[1]["phase"], "Movement")

    def test_sequential_differs_from_interleaved(self) -> None:
        inter = InterleavedTwoFactionGameDefinition().turn_order()
        seq = SequentialTwoFactionGameDefinition().turn_order()
        self.assertNotEqual(
            [x["faction"] + x["phase"] for x in inter],
            [x["faction"] + x["phase"] for x in seq],
        )
        self.assertEqual(seq[1]["faction"], "Red")
        self.assertEqual(seq[1]["phase"], "Attack")

    def test_get_next_phase_interleaved(self) -> None:
        g = InterleavedTwoFactionGameDefinition()
        st = GameState.create_empty(initial_faction="Red", initial_phase="Movement")
        nxt = g.get_next_phase(st)
        self.assertEqual(nxt["faction"], "Blue")
        self.assertEqual(nxt["phase"], "Movement")
        self.assertEqual(nxt["schedule_index"], 1)

    def test_get_next_phase_matches_lowercase_wire_phase(self) -> None:
        g = InterleavedTwoFactionGameDefinition(
            factions=("confederate", "union"),
        )
        st = GameState.create_empty(
            initial_faction="confederate",
            initial_phase="attack",
            schedule_index=2,
        )
        nxt = g.get_next_phase(st)
        self.assertEqual(nxt["faction"], "union")
        self.assertEqual(nxt["phase"], "Attack")
        self.assertEqual(nxt["schedule_index"], 3)

    def test_get_next_phase_sequential(self) -> None:
        g = SequentialTwoFactionGameDefinition()
        st = GameState.create_empty(initial_faction="Red", initial_phase="Movement")
        nxt = g.get_next_phase(st)
        self.assertEqual(nxt["faction"], "Red")
        self.assertEqual(nxt["phase"], "Attack")
        self.assertEqual(nxt["schedule_index"], 1)

    def test_advance_turn_action_for_state(self) -> None:
        st = GameState.create_empty(initial_faction="Red", initial_phase="Movement")
        np = advance_turn_action_for_state(st, InterleavedTwoFactionGameDefinition())
        self.assertEqual(np.new_faction, "Blue")
        self.assertEqual(np.new_phase, "Movement")
        self.assertEqual(np.new_schedule_index, 1)

    def test_load_game_definition_sequential(self) -> None:
        g = load_game_definition(schedule="sequential")
        self.assertIsInstance(g, SequentialTwoFactionGameDefinition)

    def test_per_unit_movement_attribute_budget(self) -> None:
        entries = (
            {"faction": "Red", "phase": "Movement", "max_actions": 2},
        )
        g = StaticScheduleGameDefinition(
            entries,
            movement_budget=4.0,
            per_unit_movement_attribute="movement",
        )
        st0 = GameState.create_empty(initial_faction="Red", initial_phase="Movement")
        st = replace(
            st0,
            board=BoardState(
                units={
                    "u1": UnitState(
                        unit_id="u1",
                        unit_type="t",
                        faction="Red",
                        position=Hex(0, 0, 0),
                        attributes={"movement": 9},
                    )
                }
            ),
        )
        self.assertEqual(g.movement_budget_for_unit(st, "u1"), 9.0)
        with self.assertRaises(ValueError):
            g.movement_budget_for_unit(st, "missing")


if __name__ == "__main__":
    unittest.main()
