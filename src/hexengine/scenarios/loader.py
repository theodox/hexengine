"""
Map `hexengine.scenarios.schema.ScenarioData` onto `hexengine.state.GameState`.

When `hexengine.state.game_state.BoardState` / unit or location state types change,
update `scenario_to_initial_state` here.
"""

from __future__ import annotations

from ..hexes.types import Hex, HexColRow
from ..state import GameState
from ..state.game_state import (
    BoardState,
    LocationState,
    UnitState,
    UnsetTerrainDefaults,
)
from .schema import ScenarioData, TerrainTypeRow


def _hex(pos: tuple[int, int]) -> Hex:
    """Scenario `Position` is odd-q `(col, row)`."""
    return Hex.from_hex_col_row(HexColRow(col=pos[0], row=pos[1]))


def _unset_defaults_from_terrain_types(
    types: tuple[TerrainTypeRow, ...],
) -> UnsetTerrainDefaults:
    default = next(t for t in types if t.is_default)
    return UnsetTerrainDefaults(
        terrain_type=default.terrain_type,
        movement_cost=default.movement_cost,
        hex_color=default.hex_color,
        assault_modifier=default.assault_modifier,
        ranged_modifier=default.ranged_modifier,
        block_los=default.block_los,
    )


def scenario_to_initial_state(
    data: ScenarioData,
    *,
    initial_faction: str,
    initial_phase: str = "Movement",
    phase_actions_remaining: int = 2,
    schedule_index: int = 0,
) -> GameState:
    """
    Build an initial GameState from scenario data (server path).

    Does not use ActionManager — constructs state directly. When BoardState
    or UnitState/LocationState change, update only this function.

    `initial_faction` / `initial_phase` / `phase_actions_remaining` / `schedule_index`
    should match the first rota slot (see `hexengine.gameroot.initial_turn_slot_for_game_definition`).
    """
    from ..state.game_state import TurnState

    board = BoardState(
        unset_defaults=_unset_defaults_from_terrain_types(data.terrain_types)
    )
    turn = TurnState(
        current_faction=initial_faction,
        current_phase=initial_phase,
        phase_actions_remaining=phase_actions_remaining,
        turn_number=1,
        schedule_index=schedule_index,
    )

    for loc in data.locations:
        board = board.with_location(
            LocationState(
                position=_hex(loc.position),
                terrain_type=loc.terrain_type,
                movement_cost=loc.movement_cost,
                hex_color=loc.hex_color,
                assault_modifier=loc.assault_modifier,
                ranged_modifier=loc.ranged_modifier,
                block_los=loc.block_los,
            )
        )

    for u in data.units:
        board = board.with_unit(
            UnitState(
                unit_id=u.unit_id,
                unit_type=u.unit_type,
                faction=u.faction,
                position=_hex(u.position),
                health=u.health,
                active=u.active,
            )
        )

    return GameState(board=board, turn=turn, extension={}, rng_log=())
