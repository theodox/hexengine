"""
Map :class:`~hexengine.scenarios.schema.ScenarioData` onto :class:`~hexengine.state.GameState`.

When :class:`~hexengine.state.game_state.BoardState` / unit or location state types change,
update :func:`scenario_to_initial_state` here.
"""

from __future__ import annotations

from ..hexes.types import Hex, HexColRow
from ..state import GameState
from ..state.game_state import BoardState, LocationState, UnitState
from .schema import ScenarioData

def _hex(pos: tuple[int, int]) -> Hex:
    """Scenario ``Position`` is odd-q ``(col, row)``."""
    return Hex.from_hex_col_row(HexColRow(col=pos[0], row=pos[1]))


def scenario_to_initial_state(
    data: ScenarioData,
    initial_faction: str = "Red",
    initial_phase: str = "Movement",
    phase_actions_remaining: int = 2,
) -> GameState:
    """
    Build an initial GameState from scenario data (server path).

    Does not use ActionManager — constructs state directly. When BoardState
    or UnitState/LocationState change, update only this function.
    """
    from ..state.game_state import TurnState

    board = BoardState()
    turn = TurnState(
        current_faction=initial_faction,
        current_phase=initial_phase,
        phase_actions_remaining=phase_actions_remaining,
        turn_number=1,
    )

    for loc in data.locations:
        board = board.with_location(
            LocationState(
                position=_hex(loc.position),
                terrain_type=loc.terrain_type,
                movement_cost=loc.movement_cost,
                hex_color=loc.hex_color,
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

    return GameState(board=board, turn=turn)
